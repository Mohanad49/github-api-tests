"""
Reusable API client wrapper around requests.Session.
Provides logging, rate-limit awareness, and pagination helpers.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.github.com"


class GitHubAPIClient:
    """Thin wrapper for authenticated GitHub API calls."""

    def __init__(self, token: str | None = None):
        self.session = requests.Session()
        self.base_url = BASE_URL
        token = token or os.getenv("GITHUB_TOKEN")
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

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

    # ---- rate-limit awareness ---------------------------------------------

    @staticmethod
    def check_rate_limit(response: requests.Response) -> dict:
        """Extract rate-limit info from response headers."""
        return {
            "limit": response.headers.get("X-RateLimit-Limit"),
            "remaining": response.headers.get("X-RateLimit-Remaining"),
            "reset": response.headers.get("X-RateLimit-Reset"),
            "used": response.headers.get("X-RateLimit-Used"),
        }

    @staticmethod
    def wait_for_rate_limit_reset(response: requests.Response) -> None:
        """Sleep until the rate-limit window resets (if needed)."""
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining == 0:
            reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_ts - int(time.time()), 0) + 1
            time.sleep(wait)
