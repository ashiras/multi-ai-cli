"""
GitHub REST API backend.

Low-level HTTP client for GitHub REST API with authentication,
error mapping, and JSON parsing.
"""

from __future__ import annotations

from typing import Any

import requests

# ── Exception classes ──


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, status_code: int, message: str, url: str = "") -> None:
        """Initialize a GitHub API error.

        Args:
            status_code: HTTP status code returned by GitHub API
            message: Error message from the API
            url: The URL that caused the error (optional)
        """
        self.status_code = status_code
        self.message = message
        self.url = url
        super().__init__(f"GitHub API Error ({status_code}): {message}")


class GitHubNotFoundError(GitHubAPIError):
    """404 Not Found."""

    def __init__(self, message: str = "Resource not found", url: str = "") -> None:
        """Initialize a 404 Not Found error from GitHub API.

        Args:
            message: Custom error message (default: "Resource not found")
            url: The URL that was not found (optional)
        """
        super().__init__(404, message, url)


class GitHubAuthError(GitHubAPIError):
    """401 Unauthorized."""

    def __init__(self, message: str = "Authentication failed", url: str = "") -> None:
        """Initialize a 401 Unauthorized error from GitHub API.

        Args:
            message: Custom error message (default: "Authentication failed")
            url: The URL that caused the authentication error (optional)
        """
        super().__init__(401, message, url)


class GitHubForbiddenError(GitHubAPIError):
    """403 Forbidden (permission or rate limit)."""

    def __init__(self, message: str = "Forbidden", url: str = "") -> None:
        """Initialize a 403 Forbidden error from GitHub API.

        Args:
            message: Custom error message (default: "Forbidden")
            url: The URL that returned forbidden response (optional)
        """
        super().__init__(403, message, url)


class GitHubRateLimitError(GitHubAPIError):
    """403 Forbidden - Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", url: str = "") -> None:
        """Initialize a 403 Rate Limit Exceeded error from GitHub API.

        Args:
            message: Custom error message (default: "Rate limit exceeded")
            url: The URL that hit the rate limit (optional)
        """
        super().__init__(403, message, url)


# ── Backend class ──


class GitHubRESTBackend:
    """Low-level GitHub REST API client."""

    def __init__(self, token: str, api_base_url: str) -> None:
        """
        Initialize the GitHub REST backend.

        Args:
            token: GitHub access token.
            api_base_url: API base URL (e.g. "https://api.github.com").
        """
        self._token = token
        self._api_base_url = api_base_url.rstrip("/")
        self._session = requests.Session()

        # Set default headers
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "multi-ai-cli",
            }
        )

        # Only set Authorization if token is non-empty (defensive for future
        # optional-token support; currently config raises ValueError if missing)
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"

    def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        """
        Common HTTP request method.

        Args:
            method: HTTP method (e.g. "GET").
            path: API path (e.g. "/repos/owner/repo").
            params: Query parameters.

        Returns:
            JSON response (dict or list).

        Raises:
            GitHubAPIError: On API errors.
        """
        url = f"{self._api_base_url}{path}"

        response = self._session.request(method, url, params=params, timeout=30)

        if response.ok:
            return response.json()

        # Extract error message from response body
        try:
            body = response.json()
            error_message = body.get("message", response.text)
        except Exception:
            error_message = response.text

        status_code = response.status_code

        # Map status codes to specific exceptions
        if status_code == 401:
            raise GitHubAuthError(message=error_message, url=url)

        if status_code == 403:
            # Check for rate limit: header or message content
            rate_remaining = response.headers.get("X-RateLimit-Remaining", "")
            is_rate_limit = (
                rate_remaining == "0" or "rate limit" in error_message.lower()
            )
            if is_rate_limit:
                raise GitHubRateLimitError(message=error_message, url=url)
            raise GitHubForbiddenError(message=error_message, url=url)

        if status_code == 404:
            raise GitHubNotFoundError(message=error_message, url=url)

        # Generic API error for all other non-2xx statuses
        raise GitHubAPIError(status_code=status_code, message=error_message, url=url)

    def get_repository(self, owner: str, repo: str) -> dict:
        """
        GET /repos/{owner}/{repo}.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Raw JSON dict from GitHub API.
        """
        return self._request("GET", f"/repos/{owner}/{repo}")

    def get_contents(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> dict | list:
        """
        GET /repos/{owner}/{repo}/contents/{path}.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: Path within the repository.
            ref: Branch/tag/SHA (optional).

        Returns:
            dict (file) or list[dict] (directory) — raw JSON.
        """
        params: dict[str, str] = {}
        if ref:
            params["ref"] = ref

        return self._request(
            "GET", f"/repos/{owner}/{repo}/contents/{path}", params=params or None
        )

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """
        GET /repos/{owner}/{repo}/issues/{issue_number}.

        Args:
            owner: Repository owner.
            repo: Repository name.
            issue_number: Issue number.

        Returns:
            Raw JSON dict.
        """
        return self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")

    def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str | None = None,
        assignee: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict]:
        """
        GET /repos/{owner}/{repo}/issues.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: "open", "closed", "all".
            labels: Comma-separated label names.
            assignee: Assignee login name.
            per_page: Items per page (max 100).
            page: Page number.

        Returns:
            list of raw JSON dicts.
        """
        params: dict[str, str | int] = {
            "state": state,
            "per_page": per_page,
            "page": page,
        }
        if labels:
            params["labels"] = labels
        if assignee:
            params["assignee"] = assignee

        return self._request("GET", f"/repos/{owner}/{repo}/issues", params=params)
