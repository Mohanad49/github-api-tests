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
    def test_update_authenticated_user_bio(self, session, base_url):
        """PATCH /user can update the user's bio."""
        # Save current bio
        current = session.get(f"{base_url}/user").json()
        original_bio = current.get("bio")

        new_bio = "Updated bio from automated test"
        response = session.patch(f"{base_url}/user", json={"bio": new_bio})
        assert response.status_code == 200
        assert response.json()["bio"] == new_bio

        # Restore original bio
        session.patch(f"{base_url}/user", json={"bio": original_bio or ""})

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
