"""Tests for multi_ai_cli.adapters.github.backends.rest_backend module."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from multi_ai_cli.adapters.github.backends.rest_backend import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRESTBackend,
)


class TestGitHubAPIError:
    def test_base_error(self):
        err = GitHubAPIError(500, "Server Error", "http://example.com")
        assert err.status_code == 500
        assert err.message == "Server Error"
        assert err.url == "http://example.com"
        assert "500" in str(err)

    def test_not_found(self):
        err = GitHubNotFoundError()
        assert err.status_code == 404
        assert isinstance(err, GitHubAPIError)

    def test_auth_error(self):
        err = GitHubAuthError("Bad token")
        assert err.status_code == 401
        assert err.message == "Bad token"

    def test_forbidden_error(self):
        err = GitHubForbiddenError()
        assert err.status_code == 403

    def test_rate_limit_error(self):
        err = GitHubRateLimitError()
        assert err.status_code == 403
        assert isinstance(err, GitHubAPIError)


class TestGitHubRESTBackend:
    def setup_method(self):
        self.backend = GitHubRESTBackend(
            token="test_token",
            api_base_url="https://api.github.com",
        )

    def test_init_sets_headers(self):
        assert "Authorization" in self.backend._session.headers
        assert self.backend._session.headers["Authorization"] == "Bearer test_token"
        assert "application/vnd.github+json" in self.backend._session.headers["Accept"]

    def test_init_strips_trailing_slash(self):
        backend = GitHubRESTBackend(token="t", api_base_url="https://api.github.com/")
        assert backend._api_base_url == "https://api.github.com"

    def test_init_empty_token(self):
        backend = GitHubRESTBackend(token="", api_base_url="https://api.github.com")
        assert "Authorization" not in backend._session.headers

    @patch.object(GitHubRESTBackend, "_request")
    def test_get_repository(self, mock_req):
        mock_req.return_value = {"full_name": "owner/repo"}
        result = self.backend.get_repository("owner", "repo")
        mock_req.assert_called_once_with("GET", "/repos/owner/repo")
        assert result["full_name"] == "owner/repo"

    @patch.object(GitHubRESTBackend, "_request")
    def test_get_contents_no_ref(self, mock_req):
        mock_req.return_value = [{"name": "file.txt"}]
        result = self.backend.get_contents("owner", "repo", "src", None)
        mock_req.assert_called_once_with(
            "GET", "/repos/owner/repo/contents/src", params=None
        )

    @patch.object(GitHubRESTBackend, "_request")
    def test_get_contents_with_ref(self, mock_req):
        mock_req.return_value = {"name": "file.txt"}
        result = self.backend.get_contents("owner", "repo", "src/file.txt", "v1.0")
        mock_req.assert_called_once_with(
            "GET", "/repos/owner/repo/contents/src/file.txt", params={"ref": "v1.0"}
        )

    @patch.object(GitHubRESTBackend, "_request")
    def test_get_issue(self, mock_req):
        mock_req.return_value = {"number": 42, "title": "Bug"}
        result = self.backend.get_issue("owner", "repo", 42)
        mock_req.assert_called_once_with("GET", "/repos/owner/repo/issues/42")
        assert result["number"] == 42

    @patch.object(GitHubRESTBackend, "_request")
    def test_get_issues(self, mock_req):
        mock_req.return_value = [{"number": 1}]
        result = self.backend.get_issues(
            "owner", "repo", state="open", labels="bug", assignee="user1"
        )
        mock_req.assert_called_once()
        _, kwargs = mock_req.call_args
        assert kwargs["params"]["state"] == "open"
        assert kwargs["params"]["labels"] == "bug"
        assert kwargs["params"]["assignee"] == "user1"


class TestGitHubRESTBackendRequest:
    """Test the _request method's error handling with mocked session."""

    def setup_method(self):
        self.backend = GitHubRESTBackend(
            token="test", api_base_url="https://api.github.com"
        )

    def _mock_response(self, status_code, json_data=None, text="", headers=None):
        resp = MagicMock()
        resp.ok = 200 <= status_code < 300
        resp.status_code = status_code
        resp.text = text
        resp.headers = headers or {}
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = Exception("No JSON")
        return resp

    def test_success(self):
        resp = self._mock_response(200, {"key": "value"})
        self.backend._session.request = MagicMock(return_value=resp)
        result = self.backend._request("GET", "/test")
        assert result == {"key": "value"}

    def test_401_raises_auth_error(self):
        resp = self._mock_response(401, {"message": "Bad credentials"})
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubAuthError):
            self.backend._request("GET", "/test")

    def test_403_rate_limit_via_header(self):
        resp = self._mock_response(
            403,
            {"message": "rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0"},
        )
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubRateLimitError):
            self.backend._request("GET", "/test")

    def test_403_rate_limit_via_message(self):
        resp = self._mock_response(403, {"message": "API rate limit exceeded"})
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubRateLimitError):
            self.backend._request("GET", "/test")

    def test_403_forbidden(self):
        resp = self._mock_response(403, {"message": "Forbidden resource"})
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubForbiddenError):
            self.backend._request("GET", "/test")

    def test_404_raises_not_found(self):
        resp = self._mock_response(404, {"message": "Not Found"})
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubNotFoundError):
            self.backend._request("GET", "/test")

    def test_500_raises_generic(self):
        resp = self._mock_response(500, {"message": "Internal Server Error"})
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubAPIError) as exc_info:
            self.backend._request("GET", "/test")
        assert exc_info.value.status_code == 500

    def test_error_without_json_body(self):
        resp = self._mock_response(502, text="Bad Gateway")
        self.backend._session.request = MagicMock(return_value=resp)
        with pytest.raises(GitHubAPIError) as exc_info:
            self.backend._request("GET", "/test")
        assert exc_info.value.status_code == 502