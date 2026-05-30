"""
Tests for GitHub API authentication and authorization.
All tests in this module use unauthenticated or intentionally-bad credentials.
"""

import pytest
import requests


class TestAuthentication:
    """Authentication & authorization edge-case tests."""

    # ---- Negative / security tests ----------------------------------------

    @pytest.mark.smoke
    @pytest.mark.negative
    def test_invalid_token_returns_401(self, base_url):
        """A request with a garbage token should be rejected."""
        response = requests.get(
            f"{base_url}/user",
            headers={
                "Authorization": "Bearer invalid_token_xyz",
                "Accept": "application/vnd.github+json",
            },
        )
        assert response.status_code == 401

    @pytest.mark.smoke
    @pytest.mark.negative
    def test_no_auth_returns_401_for_private_endpoint(self, base_url):
        """GET /user without any credentials returns 401."""
        response = requests.get(
            f"{base_url}/user",
            headers={"Accept": "application/vnd.github+json"},
        )
        assert response.status_code == 401

    @pytest.mark.negative
    def test_401_response_has_message(self, base_url):
        """Unauthorized responses include a human-readable message."""
        response = requests.get(
            f"{base_url}/user",
            headers={"Accept": "application/vnd.github+json"},
        )
        body = response.json()
        assert "message" in body
        assert len(body["message"]) > 0

    @pytest.mark.negative
    def test_401_response_has_documentation_url(self, base_url):
        """Unauthorized responses include a documentation_url for debugging."""
        response = requests.get(
            f"{base_url}/user",
            headers={"Accept": "application/vnd.github+json"},
        )
        body = response.json()
        assert "documentation_url" in body

    @pytest.mark.smoke
    def test_valid_token_returns_200(self, session, base_url):
        """Sanity check — a valid token should succeed."""
        response = session.get(f"{base_url}/user")
        assert response.status_code == 200

    @pytest.mark.negative
    def test_malformed_auth_header_returns_401(self, base_url):
        """A completely malformed Authorization header should be rejected."""
        response = requests.get(
            f"{base_url}/user",
            headers={
                "Authorization": "NotAScheme abc123",
                "Accept": "application/vnd.github+json",
            },
        )
        assert response.status_code == 401

    @pytest.mark.regression
    def test_unauthenticated_public_endpoint_returns_200(self, base_url):
        """Public endpoints like /zen work without auth."""
        response = requests.get(
            f"{base_url}/zen",
            headers={"Accept": "application/vnd.github+json"},
        )
        assert response.status_code == 200

    @pytest.mark.regression
    def test_rate_limit_headers_on_unauthenticated_request(self, base_url):
        """Even unauthenticated requests include rate-limit headers."""
        response = requests.get(
            f"{base_url}/zen",
            headers={"Accept": "application/vnd.github+json"},
        )
        assert "X-RateLimit-Limit" in response.headers
