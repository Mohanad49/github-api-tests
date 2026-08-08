"""
Tests for the suite's own rate-limit handling.

Everything here is offline. No token, no network, no GitHub - these exercise
`utils/api_client.py` against constructed responses, which is the only way to
test the interesting cases: reproducing a real secondary-rate-limit block on
demand would mean deliberately abusing the API, and the resulting test would
take a minute to run and be unrunnable on a fork.

The case that earns this file is `test_plain_403_is_not_retried`. The retry
logic is the fix for a suite that used to throttle itself, and the way that fix
goes wrong is by being too eager: this suite deliberately provokes 403s that
mean "not allowed", and sleeping five minutes before re-asking a question that
was answered correctly the first time would trade a red build for a slow one.
"""

import time

import pytest
import requests

from utils.api_client import GitHubSession, is_rate_limited


SECONDARY_LIMIT_BODY = (
    '{"message":"You have exceeded a secondary rate limit and have been '
    'temporarily blocked from content creation. Please retry your request '
    'again later.","status":"403"}'
)


def make_response(status: int, body: str = "{}", **headers) -> requests.Response:
    """A requests.Response with the bits the rate-limit code reads."""
    response = requests.Response()
    response.status_code = status
    response._content = body.encode()
    response.headers.update(headers)
    return response


# ---- classification -------------------------------------------------------


class TestRateLimitDetection:
    """`is_rate_limited` has to separate throttling from refusal."""

    def test_secondary_limit_body_is_detected(self):
        assert is_rate_limited(make_response(403, SECONDARY_LIMIT_BODY))

    def test_retry_after_header_is_detected(self):
        assert is_rate_limited(make_response(429, "{}", **{"Retry-After": "30"}))

    def test_exhausted_primary_limit_is_detected(self):
        response = make_response(403, "{}", **{"x-ratelimit-remaining": "0"})
        assert is_rate_limited(response)

    def test_plain_403_is_not_a_rate_limit(self):
        """
        The one that matters. GitHub uses 403 for "too fast" and for "not
        allowed", and this suite asserts on the second kind.
        """
        body = '{"message":"Resource not accessible by integration"}'
        response = make_response(403, body, **{"x-ratelimit-remaining": "4837"})
        assert not is_rate_limited(response)

    @pytest.mark.parametrize("status", [200, 201, 204, 401, 404, 422])
    def test_ordinary_statuses_are_not_rate_limits(self, status):
        assert not is_rate_limited(make_response(status))


# ---- retry behaviour ------------------------------------------------------


class TestRetryBehaviour:

    @pytest.fixture
    def no_sleep(self, monkeypatch):
        """Record what would have been slept instead of sleeping it."""
        slept: list[float] = []
        monkeypatch.setattr(time, "sleep", slept.append)
        return slept

    def _session_returning(self, monkeypatch, responses):
        """A GitHubSession whose transport replays `responses` in order."""
        calls: list[tuple[str, str]] = []
        queue = list(responses)

        def fake_request(self, method, url, **kwargs):
            calls.append((method, url))
            return queue.pop(0) if queue else responses[-1]

        monkeypatch.setattr(requests.Session, "request", fake_request)
        return GitHubSession(token="not-a-real-token"), calls

    def test_throttled_request_is_retried_until_it_succeeds(self, monkeypatch, no_sleep):
        session, calls = self._session_returning(monkeypatch, [
            make_response(403, SECONDARY_LIMIT_BODY),
            make_response(201, '{"name":"repo"}'),
        ])

        response = session.post("https://api.github.com/user/repos")

        assert response.status_code == 201
        assert len(calls) == 2
        assert session.throttle_events == 1

    def test_retry_after_header_is_honoured(self, monkeypatch, no_sleep):
        session, _ = self._session_returning(monkeypatch, [
            make_response(429, "{}", **{"Retry-After": "7"}),
            make_response(200),
        ])

        session.get("https://api.github.com/user")

        assert 7 in no_sleep

    def test_plain_403_is_not_retried(self, monkeypatch, no_sleep):
        body = '{"message":"Resource not accessible by integration"}'
        session, calls = self._session_returning(monkeypatch, [
            make_response(403, body, **{"x-ratelimit-remaining": "4837"}),
        ])

        response = session.post("https://api.github.com/user/repos")

        assert response.status_code == 403
        assert len(calls) == 1, "a refusal on the merits must come back immediately"
        assert session.throttle_events == 0

    def test_gives_up_and_reports_the_throttled_response(self, monkeypatch, no_sleep):
        """
        Backing off forever is not more correct than failing. Past the budget
        the suite returns GitHub's own response so the failure message says why.
        """
        session, _ = self._session_returning(monkeypatch, [
            make_response(403, SECONDARY_LIMIT_BODY),
        ])

        response = session.post("https://api.github.com/user/repos")

        assert response.status_code == 403
        assert "secondary rate limit" in response.text
        assert sum(no_sleep) <= 300.0

    def test_writes_are_paced_but_reads_are_not(self, monkeypatch, no_sleep):
        session, _ = self._session_returning(
            monkeypatch, [make_response(200), make_response(201), make_response(201)]
        )
        session.mutation_interval = 1.0

        session.get("https://api.github.com/user")
        session.post("https://api.github.com/user/repos")
        session.post("https://api.github.com/user/repos")

        # One pause, between the two writes. The read is not paced, and the
        # first write has nothing to wait behind.
        assert len(no_sleep) == 1
        assert no_sleep[0] == pytest.approx(1.0, abs=0.05)
