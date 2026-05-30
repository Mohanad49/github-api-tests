"""
Tests for the GitHub Issues API.
Covers CRUD operations, schema validation, filtering, and error handling.
"""

import pytest
from utils.schema_validator import validate


class TestIssues:
    """Issues endpoint test suite."""

    # ---- Positive / smoke tests -------------------------------------------

    @pytest.mark.smoke
    def test_create_issue_returns_201(self, test_issue):
        """The test_issue fixture should have created an issue successfully."""
        assert test_issue["id"] is not None
        assert test_issue["number"] is not None
        assert test_issue["state"] == "open"

    @pytest.mark.regression
    def test_get_issue_response_schema(self, session, base_url, authenticated_user,
                                       test_repo, test_issue):
        """GET /repos/:owner/:repo/issues/:number matches the issue JSON schema."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]
        issue_number = test_issue["number"]

        response = session.get(
            f"{base_url}/repos/{username}/{repo_name}/issues/{issue_number}"
        )
        assert response.status_code == 200
        validate(response.json(), "issue")

    @pytest.mark.regression
    def test_update_issue_title(self, session, base_url, authenticated_user,
                                test_repo, test_issue):
        """PATCH /repos/:owner/:repo/issues/:number can update the title."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]
        issue_number = test_issue["number"]
        new_title = "Updated title by automated test"

        response = session.patch(
            f"{base_url}/repos/{username}/{repo_name}/issues/{issue_number}",
            json={"title": new_title},
        )
        assert response.status_code == 200
        assert response.json()["title"] == new_title

    @pytest.mark.regression
    def test_close_issue(self, session, base_url, authenticated_user,
                         test_repo, test_issue):
        """PATCH /repos/:owner/:repo/issues/:number can close an issue."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]
        issue_number = test_issue["number"]

        response = session.patch(
            f"{base_url}/repos/{username}/{repo_name}/issues/{issue_number}",
            json={"state": "closed"},
        )
        assert response.status_code == 200
        assert response.json()["state"] == "closed"

    @pytest.mark.regression
    def test_add_label_to_issue(self, session, base_url, authenticated_user,
                                test_repo, test_issue):
        """POST /repos/:owner/:repo/issues/:number/labels adds labels."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]
        issue_number = test_issue["number"]

        # First create a label in the repo
        session.post(
            f"{base_url}/repos/{username}/{repo_name}/labels",
            json={"name": "bug", "color": "d73a4a"},
        )

        response = session.post(
            f"{base_url}/repos/{username}/{repo_name}/issues/{issue_number}/labels",
            json={"labels": ["bug"]},
        )
        assert response.status_code == 200
        label_names = [label["name"] for label in response.json()]
        assert "bug" in label_names

    @pytest.mark.regression
    def test_add_comment_to_issue(self, session, base_url, authenticated_user,
                                  test_repo, test_issue):
        """POST /repos/:owner/:repo/issues/:number/comments adds a comment."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]
        issue_number = test_issue["number"]

        response = session.post(
            f"{base_url}/repos/{username}/{repo_name}/issues/{issue_number}/comments",
            json={"body": "Automated test comment"},
        )
        assert response.status_code == 201
        assert response.json()["body"] == "Automated test comment"

    # ---- Filtering --------------------------------------------------------

    @pytest.mark.regression
    def test_list_issues_filter_by_state(self, session, base_url, authenticated_user, test_repo):
        """GET /repos/:owner/:repo/issues?state=closed returns only closed issues."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]

        response = session.get(
            f"{base_url}/repos/{username}/{repo_name}/issues",
            params={"state": "closed"},
        )
        assert response.status_code == 200
        for issue in response.json():
            assert issue["state"] == "closed"

    # ---- Negative tests ---------------------------------------------------

    @pytest.mark.negative
    def test_create_issue_without_title_returns_422(self, session, base_url,
                                                     authenticated_user, test_repo):
        """POST /repos/:owner/:repo/issues without a title returns 422."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]

        response = session.post(
            f"{base_url}/repos/{username}/{repo_name}/issues",
            json={"body": "no title provided"},
        )
        assert response.status_code == 422

    @pytest.mark.negative
    def test_get_nonexistent_issue_returns_404(self, session, base_url,
                                                authenticated_user, test_repo):
        """GET /repos/:owner/:repo/issues/99999 returns 404."""
        username = authenticated_user["login"]
        repo_name = test_repo["name"]

        response = session.get(
            f"{base_url}/repos/{username}/{repo_name}/issues/99999"
        )
        assert response.status_code == 404

    @pytest.mark.negative
    def test_create_issue_on_nonexistent_repo_returns_404(self, session, base_url):
        """POST /repos/bad-user/bad-repo/issues returns 404."""
        response = session.post(
            f"{base_url}/repos/nonexistent-user-xyz/nonexistent-repo-xyz/issues",
            json={"title": "should fail"},
        )
        assert response.status_code == 404
