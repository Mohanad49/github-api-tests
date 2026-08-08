"""
Shared pytest fixtures for the GitHub API test suite.
"""

import uuid
import pytest
import os
from dotenv import load_dotenv

from utils.api_client import BASE_URL, GitHubSession

load_dotenv()


@pytest.fixture(scope="session")
def session():
    """
    Authenticated session for the entire test run.

    A `GitHubSession` rather than a bare `requests.Session`: it paces writes and
    retries GitHub's throttling responses, so an assertion on a status code is
    asserting something about the API rather than about how fast the previous
    test happened to run. See `utils/api_client.py` for what that cost the suite
    before it was there.
    """
    s = GitHubSession(token=os.getenv("GITHUB_TOKEN"))
    yield s
    if s.throttle_events:
        print(
            f"\n[rate limit] backed off {s.throttle_events} time(s), "
            f"{s.total_backoff_seconds:.0f}s total"
        )


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def authenticated_user(session):
    """Fetch and cache the authenticated user for the session."""
    response = session.get(f"{BASE_URL}/user")
    assert response.status_code == 200, (
        f"Failed to authenticate — status {response.status_code}: {response.text}"
    )
    return response.json()


@pytest.fixture(scope="session")
def test_repo(session, authenticated_user):
    """
    One private repository, created once and deleted at the end of the run.

    This used to be function-scoped, which read better - every test got a repo
    nobody else had touched - and was the direct cause of the suite failing
    every night. Nine tests take this fixture, so a run created nine
    repositories and nine initial commits within a couple of seconds, and
    GitHub's secondary rate limit on content creation stopped it. The tests then
    reported `assert 403 == 201` and looked like a broken API client.

    Sharing one repository is a real trade and worth naming rather than
    presenting as a tidy-up. What is given up is isolation: these tests now run
    against a repository whose issue list grows as the run proceeds. What makes
    that acceptable here is that none of them asserts on the repository's
    aggregate state - the issue-filter test asserts that everything returned
    matches the filter, not how many things came back - so no test can be broken
    by another test's leftovers.

    Where isolation genuinely matters it is kept:
    `test_delete_repo_returns_204` destroys what it operates on, so it creates
    its own and does not touch this one.
    """
    username = authenticated_user["login"]
    repo_name = f"test-repo-{uuid.uuid4().hex[:8]}"

    create_resp = session.post(f"{BASE_URL}/user/repos", json={
        "name": repo_name,
        "private": True,
        "auto_init": True,
        "description": "Automated test repo — safe to delete",
    })
    assert create_resp.status_code == 201, (
        f"Repo creation failed — status {create_resp.status_code}: {create_resp.text}"
    )

    repo_data = create_resp.json()
    yield repo_data

    # Cleanup — delete the repo; ignore errors (it may already be gone)
    session.delete(f"{BASE_URL}/repos/{username}/{repo_name}")


@pytest.fixture
def test_issue(session, base_url, authenticated_user, test_repo):
    """
    Creates a test issue inside test_repo, yields it, then lets repo cleanup handle deletion.

    Function-scoped on purpose, unlike the repository above: several tests mutate
    the issue they are given - closing it, retitling it - so they each need one
    of their own. An issue is one content-creating request against a repository
    that already exists, which is cheap enough to keep the isolation.
    """
    username = authenticated_user["login"]
    repo_name = test_repo["name"]

    create_resp = session.post(
        f"{base_url}/repos/{username}/{repo_name}/issues",
        json={
            "title": f"Test issue {uuid.uuid4().hex[:8]}",
            "body": "Created by automated test suite",
            "labels": [],
        },
    )
    assert create_resp.status_code == 201, (
        f"Issue creation failed — status {create_resp.status_code}: {create_resp.text}"
    )

    yield create_resp.json()
