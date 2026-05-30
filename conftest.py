"""
Shared pytest fixtures for the GitHub API test suite.
"""

import uuid
import time
import pytest
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.github.com"


@pytest.fixture(scope="session")
def session():
    """Authenticated requests.Session for the entire test run."""
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return s


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


@pytest.fixture
def test_repo(session, authenticated_user):
    """
    Creates a uniquely-named private test repo, yields it, then deletes it.
    Uses UUID to avoid name collisions across parallel runs.
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
