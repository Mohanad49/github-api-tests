"""
HTTP layer for the suite.

`GitHubSession` is a `requests.Session` that knows about GitHub's two rate
limits. The tests talk to it directly; `GitHubAPIClient` is a thin
path-relative wrapper over the same session for anyone who prefers that shape.

Why this exists at all is worth stating, because it is the whole reason this
suite went red every night for a fortnight.

GitHub enforces two different limits:

  * The **primary** limit is the familiar one - 5,000 requests an hour for a
    user token - and it announces itself in `x-ratelimit-remaining`. Nothing
    here has ever come close to it.
  * The **secondary** limits are undocumented in their exact numbers and
    concern *rates* rather than totals. One of them caps how fast an account
    may create content. Creating a repository is content. So is an issue, a
    comment, a label, and the initial commit that `auto_init` makes.

The suite used to create a fresh repository for every test that needed one -
nine repositories, nine initial commits and six issues, fired off as fast as
the network allowed - and then, on a nightly schedule, did it four times over
in parallel jobs sharing one token. GitHub answered `403 You have exceeded a
secondary rate limit`, which arrived at the assertions as `assert 403 == 201`,
and the suite blamed itself for a limit it was tripping on purpose.

Two fixes, and this file is the second half of the first one:

  1. Ask for less. `conftest.py` now shares one repository across the tests
     that only read from it.
  2. Ask politely. GitHub's own guidance for a client making many writes is to
     leave at least a second between them and to back off when told to. That is
     what this session does, and it is behaviour any API client hitting a real
     service needs - so the suite now demonstrates it rather than describing it
     in a README.
"""

import os
import random
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.github.com"

# GitHub asks for "at least one second" between requests that create or mutate
# content. It is the documented number, not a tuned one.
MUTATION_INTERVAL_SECONDS = 1.0

# When GitHub reports a secondary limit without a Retry-After header, its
# guidance is to wait at least a minute before retrying.
SECONDARY_BACKOFF_SECONDS = 60.0

# A bound on the whole thing. A CI job that sits in backoff for ten minutes has
# stopped being a test run, so past this the suite gives up and reports the
# rate-limit response as the result. That is the honest outcome: the limit was
# real and the suite could not get under it.
MAX_RETRIES = 4
MAX_TOTAL_BACKOFF_SECONDS = 300.0

_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
_SECONDARY_LIMIT_PATTERN = re.compile(
    r"secondary rate limit|abuse detection", re.IGNORECASE
)


def _retry_after_seconds(response: requests.Response) -> float | None:
    """Seconds to wait per the `Retry-After` header, if GitHub sent one."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return max(float(raw), 0.0)
    except ValueError:
        # The header may also be an HTTP date. GitHub sends the delta form, so
        # rather than parse a date we did not ask for, fall through to the
        # caller's default.
        return None


def _primary_limit_exhausted(response: requests.Response) -> bool:
    return response.headers.get("x-ratelimit-remaining") == "0"


def _seconds_until_primary_reset(response: requests.Response) -> float:
    try:
        reset_at = int(response.headers.get("x-ratelimit-reset", "0"))
    except ValueError:
        return 0.0
    return max(reset_at - time.time(), 0.0) + 1.0


def is_rate_limited(response: requests.Response) -> bool:
    """
    True when a response is GitHub refusing on rate grounds rather than on the
    merits of the request.

    The distinction matters more than it looks. GitHub returns `403` both for
    "you are going too fast" and for "you may not do that", and this suite
    contains tests that *want* the second one. Retrying a genuine authorisation
    failure would turn a fast, correct negative test into a five-minute sleep
    ending in the same answer, so the check is deliberately narrow: a status
    GitHub uses for throttling, plus positive evidence of throttling in the
    headers or the body.
    """
    if response.status_code not in (403, 429):
        return False
    if response.headers.get("Retry-After") is not None:
        return True
    if _primary_limit_exhausted(response):
        return True
    return bool(_SECONDARY_LIMIT_PATTERN.search(response.text or ""))


class GitHubSession(requests.Session):
    """
    An authenticated session that paces its writes and backs off when throttled.

    Every response the tests see has already survived this, which means an
    assertion that reads `assert response.status_code == 201` is asserting
    something about the GitHub API rather than about how fast the previous test
    happened to run.
    """

    def __init__(self, token: str | None = None,
                 mutation_interval: float = MUTATION_INTERVAL_SECONDS):
        super().__init__()
        self.mutation_interval = mutation_interval
        self._last_mutation_at: float | None = None
        # Recorded so a test run can report what the pacing actually cost.
        self.total_backoff_seconds = 0.0
        self.throttle_events = 0

        token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    # ---- pacing -----------------------------------------------------------

    def _pace_mutation(self, method: str) -> None:
        """Keep consecutive content-creating requests at least a second apart."""
        if method.upper() not in _MUTATING_METHODS:
            return
        now = time.monotonic()
        if self._last_mutation_at is not None:
            elapsed = now - self._last_mutation_at
            if elapsed < self.mutation_interval:
                time.sleep(self.mutation_interval - elapsed)
        self._last_mutation_at = time.monotonic()

    def _wait_for(self, response: requests.Response, attempt: int) -> float:
        """How long to sleep before retrying a throttled request."""
        explicit = _retry_after_seconds(response)
        if explicit is not None:
            return explicit
        if _primary_limit_exhausted(response):
            return _seconds_until_primary_reset(response)
        # Secondary limit with no header: GitHub's floor is a minute, and the
        # jitter keeps three parallel jobs from waking up together and tripping
        # the same limit again in lockstep.
        return SECONDARY_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 5)

    # ---- the one override -------------------------------------------------

    def request(self, method, url, **kwargs) -> requests.Response:  # type: ignore[override]
        self._pace_mutation(method)
        response = super().request(method, url, **kwargs)

        for attempt in range(MAX_RETRIES):
            if not is_rate_limited(response):
                return response

            wait = self._wait_for(response, attempt)
            if self.total_backoff_seconds + wait > MAX_TOTAL_BACKOFF_SECONDS:
                # Out of patience. Hand back the throttled response so the
                # failure message carries GitHub's own explanation.
                return response

            self.throttle_events += 1
            self.total_backoff_seconds += wait
            time.sleep(wait)

            self._pace_mutation(method)
            response = super().request(method, url, **kwargs)

        return response


class GitHubAPIClient:
    """Path-relative wrapper over `GitHubSession` for callers that want one."""

    def __init__(self, token: str | None = None):
        self.session = GitHubSession(token)
        self.base_url = BASE_URL

    # ---- convenience verbs ------------------------------------------------

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self.session.patch(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.session.delete(f"{self.base_url}{path}", **kwargs)

    # ---- pagination -------------------------------------------------------

    def get_all_pages(self, path: str, per_page: int = 30, max_pages: int = 5,
                      **kwargs) -> list[dict]:
        """Follow GitHub's Link-header pagination and collect results."""
        items: list[dict] = []
        params = kwargs.pop("params", {})
        params["per_page"] = per_page

        url = f"{self.base_url}{path}"
        for _ in range(max_pages):
            resp = self.session.get(url, params=params, **kwargs)
            resp.raise_for_status()
            items.extend(resp.json())

            next_url = resp.links.get("next", {}).get("url")
            if not next_url:
                break
            url = next_url
            params = {}  # params are baked into the next URL

        return items

    # ---- rate-limit reporting ---------------------------------------------

    @staticmethod
    def check_rate_limit(response: requests.Response) -> dict:
        """Extract rate-limit info from response headers."""
        return {
            "limit": response.headers.get("X-RateLimit-Limit"),
            "remaining": response.headers.get("X-RateLimit-Remaining"),
            "reset": response.headers.get("X-RateLimit-Reset"),
            "used": response.headers.get("X-RateLimit-Used"),
        }
