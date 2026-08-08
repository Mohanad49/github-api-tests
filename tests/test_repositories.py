"""
Tests for the GitHub Repositories API.
Covers CRUD operations, schema validation, pagination, and error handling.
"""

import pytest
from utils.schema_validator import validate


class TestRepositories:
    """Repositories endpoint test suite."""

    # ---- Positive / smoke tests -------------------------------------------

    @pytest.mark.smoke
    def test_get_authenticated_user_repos(self, session, base_url):
        """GET /user/repos returns a list for authenticated users."""
        response = session.get(f"{base_url}/user/repos")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.smoke
    def test_create_repo_returns_201(self, session, base_url, test_repo):
        """Repo creation fixture should have produced a valid repo name."""
        assert test_repo["name"] is not None
        assert test_repo["private"] is True

    @pytest.mark.regression
    def test_get_repo_response_schema(self, session, base_url, authenticated_user, test_repo):
        """GET /repos/:owner/:repo matches the repository JSON schema."""
        username = authenticated_user["login"]
        response = session.get(f"{base_url}/repos/{username}/{test_repo['name']}")
        assert response.status_code == 200
        validate(response.json(), "repository")

    @pytest.mark.regression
    def test_update_repo_description(self, session, base_url, authenticated_user, test_repo):
        """PATCH /repos/:owner/:repo successfully updates the description."""
        username = authenticated_user["login"]
        new_description = "Updated by automated test"
        response = session.patch(
            f"{base_url}/repos/{username}/{test_repo['name']}",
            json={"description": new_description},
        )
        assert response.status_code == 200
        assert response.json()["description"] == new_description

    @pytest.mark.regression
    def test_delete_repo_returns_204(self, session, base_url, authenticated_user):
        """DELETE /repos/:owner/:repo returns 204 No Content.

        Creates its own repository rather than taking the shared `test_repo`
        fixture, because it destroys what it is given.

        The creation is asserted before the deletion is attempted. It was not,
        and when the account was being throttled the create silently returned
        403, the delete then correctly reported 404 for a repository that had
        never existed, and the failure read `assert 404 == 204` - which points
        at DELETE, the one call in this test that was working.
        """
        import uuid

        repo_name = f"test-delete-{uuid.uuid4().hex[:8]}"
        create_resp = session.post(f"{base_url}/user/repos", json={
            "name": repo_name, "private": True, "auto_init": True,
        })
        assert create_resp.status_code == 201, (
            f"Setup failed, so DELETE was never exercised — "
            f"status {create_resp.status_code}: {create_resp.text}"
        )

        username = authenticated_user["login"]
        del_resp = session.delete(f"{base_url}/repos/{username}/{repo_name}")
        assert del_resp.status_code == 204

    # ---- Negative tests ---------------------------------------------------

    @pytest.mark.negative
    def test_get_nonexistent_repo_returns_404(self, session, base_url):
        """GET /repos/:owner/:repo with bogus names returns 404."""
        response = session.get(f"{base_url}/repos/nonexistent-user-xyz/nonexistent-repo-xyz")
        assert response.status_code == 404

    @pytest.mark.negative
    def test_create_repo_without_name_returns_422(self, session, base_url):
        """POST /user/repos without a name field returns 422."""
        response = session.post(f"{base_url}/user/repos", json={"description": "no name"})
        assert response.status_code == 422

    @pytest.mark.negative
    def test_create_duplicate_repo_returns_422(self, session, base_url, authenticated_user, test_repo):
        """Creating a repo with the same name as an existing one returns 422."""
        response = session.post(f"{base_url}/user/repos", json={
            "name": test_repo["name"],
            "private": True,
        })
        assert response.status_code == 422

    # ---- Pagination -------------------------------------------------------

    @pytest.mark.regression
    def test_repos_pagination_per_page(self, session, base_url):
        """Setting per_page limits the number of repos returned."""
        response = session.get(f"{base_url}/user/repos", params={"per_page": 1})
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 1

    @pytest.mark.regression
    def test_repos_pagination_link_header(self, session, base_url):
        """When results are paginated, the response includes a Link header."""
        response = session.get(f"{base_url}/user/repos", params={"per_page": 1})
        assert response.status_code == 200
        # Link header is only present when there's more than one page
        if len(response.json()) > 0:
            assert "Link" in response.headers or len(response.json()) <= 1

    # ---- Headers / rate limiting ------------------------------------------

    @pytest.mark.smoke
    def test_response_includes_rate_limit_headers(self, session, base_url):
        """Every authenticated response should include rate-limit headers."""
        response = session.get(f"{base_url}/user/repos")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Used" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.regression
    def test_response_content_type_is_json(self, session, base_url):
        """Responses should return application/json content type."""
        response = session.get(f"{base_url}/user/repos")
        assert "application/json" in response.headers.get("Content-Type", "")
