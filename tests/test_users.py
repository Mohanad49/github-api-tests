"""
Tests for the GitHub Users API.
Covers authenticated user info, public user lookup, schema validation, and error handling.
"""

import pytest
from utils.schema_validator import validate


class TestUsers:
    """Users endpoint test suite."""

    # ---- Positive / smoke tests -------------------------------------------

    @pytest.mark.smoke
    def test_get_authenticated_user_returns_200(self, session, base_url):
        """GET /user returns 200 for an authenticated user."""
        response = session.get(f"{base_url}/user")
        assert response.status_code == 200

    @pytest.mark.smoke
    def test_authenticated_user_has_login(self, authenticated_user):
        """The authenticated user payload must contain a login field."""
        assert "login" in authenticated_user
        assert isinstance(authenticated_user["login"], str)
        assert len(authenticated_user["login"]) > 0

    @pytest.mark.regression
    def test_authenticated_user_response_schema(self, session, base_url):
        """GET /user response matches the user JSON schema."""
        response = session.get(f"{base_url}/user")
        assert response.status_code == 200
        validate(response.json(), "user")

    @pytest.mark.regression
    def test_get_user_by_username(self, session, base_url, authenticated_user):
        """GET /users/:username returns the same user info."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/users/{username}")
        assert response.status_code == 200
        assert response.json()["login"] == username

    @pytest.mark.regression
    def test_public_user_response_schema(self, session, base_url, authenticated_user):
        """GET /users/:username also matches the user JSON schema."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/users/{username}")
        assert response.status_code == 200
        validate(response.json(), "user")

    @pytest.mark.regression
    def test_patch_authenticated_user_is_accepted(self, session, base_url):
        """PATCH /user accepts a write and echoes the stored value back.

        This deliberately writes the bio back to whatever it already is, rather
        than setting a test string and restoring it afterwards.

        The earlier version set the bio to "Updated bio from automated test" and
        restored it on the next line. That is safe right up until the process is
        killed between those two calls - a cancelled workflow, a runner timeout,
        a rate limit - and then a real, public GitHub profile is left advertising
        that it is being written to by a test suite. On a nightly schedule that
        is several chances a week to leave it that way.

        Writing the current value back is idempotent: it exercises the same
        endpoint, the same auth, the same status code and the same response
        shape, and there is no window in which the account is in a state anyone
        has to clean up. Please do not "improve" this back into a mutation.
        """
        current = session.get(f"{base_url}/user").json()
        # GitHub returns null for an unset bio and rejects null on write.
        unchanged = current.get("bio") or ""

        response = session.patch(f"{base_url}/user", json={"bio": unchanged})
        assert response.status_code == 200
        assert (response.json().get("bio") or "") == unchanged

        # And the account really is where it started.
        after = session.get(f"{base_url}/user").json()
        assert (after.get("bio") or "") == unchanged

    @pytest.mark.regression
    def test_list_user_repos(self, session, base_url, authenticated_user):
        """GET /users/:username/repos returns a list."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/users/{username}/repos")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.regression
    def test_list_user_followers(self, session, base_url, authenticated_user):
        """GET /users/:username/followers returns a list."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/users/{username}/followers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.regression
    def test_list_user_following(self, session, base_url, authenticated_user):
        """GET /users/:username/following returns a list."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/users/{username}/following")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    # ---- Negative tests ---------------------------------------------------

    @pytest.mark.negative
    def test_get_nonexistent_user_returns_404(self, session, base_url):
        """GET /users/:username with a bogus username returns 404."""
        response = session.get(f"{base_url}/users/this-user-does-not-exist-xyz-12345")
        assert response.status_code == 404

    @pytest.mark.negative
    def test_nonexistent_user_response_has_message(self, session, base_url):
        """404 responses include a message field in the body."""
        response = session.get(f"{base_url}/users/this-user-does-not-exist-xyz-12345")
        assert response.status_code == 404
        assert "message" in response.json()
