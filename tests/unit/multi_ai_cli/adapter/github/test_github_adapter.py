"""Tests for multi_ai_cli.adapters.github.adapter module."""

import base64
from unittest.mock import MagicMock

import pytest

from multi_ai_cli.adapters.github.adapter import GitHubAdapter
from multi_ai_cli.adapters.github.backends.rest_backend import GitHubAPIError
from multi_ai_cli.adapters.github.models import (
    FileContent,
    IssueDetail,
    IssueSummary,
    RepoInfo,
    TreeEntryType,
    TreeListing,
)


class TestGitHubAdapterGetRepoInfo:
    def test_basic(self):
        mock_backend = MagicMock()
        mock_backend.get_repository.return_value = {
            "full_name": "owner/repo",
            "description": "A repo",
            "private": False,
            "default_branch": "main",
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 5,
            "html_url": "https://github.com/owner/repo",
            "language": "Python",
            "archived": False,
        }
        adapter = GitHubAdapter(backend=mock_backend)
        info = adapter.get_repo_info("owner", "repo")
        assert isinstance(info, RepoInfo)
        assert info.full_name == "owner/repo"
        assert info.stars == 100

    def test_null_description(self):
        mock_backend = MagicMock()
        mock_backend.get_repository.return_value = {
            "full_name": "o/r",
            "description": None,
            "private": True,
            "default_branch": "main",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 0,
            "html_url": "",
            "language": None,
            "archived": False,
        }
        adapter = GitHubAdapter(backend=mock_backend)
        info = adapter.get_repo_info("o", "r")
        assert info.description == ""
        assert info.language == ""


class TestGitHubAdapterGetTree:
    def test_directory_listing(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = [
            {"name": "src", "path": "src", "type": "dir", "sha": "a1"},
            {
                "name": "README.md",
                "path": "README.md",
                "type": "file",
                "size": 500,
                "sha": "a2",
            },
        ]
        adapter = GitHubAdapter(backend=mock_backend)
        listing = adapter.get_tree("owner", "repo")
        assert isinstance(listing, TreeListing)
        assert len(listing.entries) == 2
        assert listing.entries[0].entry_type == TreeEntryType.DIR
        assert listing.entries[1].entry_type == TreeEntryType.FILE

    def test_single_file_response(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = {
            "name": "file.txt",
            "path": "file.txt",
            "type": "file",
            "size": 100,
            "sha": "abc",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        listing = adapter.get_tree("owner", "repo", "file.txt")
        assert len(listing.entries) == 1

    def test_sorting(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = [
            {
                "name": "zebra.txt",
                "path": "zebra.txt",
                "type": "file",
                "size": 1,
                "sha": "z",
            },
            {"name": "alpha", "path": "alpha", "type": "dir", "sha": "a"},
            {
                "name": "beta.txt",
                "path": "beta.txt",
                "type": "file",
                "size": 2,
                "sha": "b",
            },
            {"name": "aaa", "path": "aaa", "type": "dir", "sha": "d"},
        ]
        adapter = GitHubAdapter(backend=mock_backend)
        listing = adapter.get_tree("owner", "repo")
        names = [e.name for e in listing.entries]
        assert names == ["aaa", "alpha", "beta.txt", "zebra.txt"]


class TestGitHubAdapterGetFileContent:
    def test_base64_file(self):
        mock_backend = MagicMock()
        encoded = base64.b64encode(b"hello world").decode()
        mock_backend.get_contents.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": encoded,
            "size": 11,
            "sha": "abc",
            "name": "test.txt",
            "path": "test.txt",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        fc = adapter.get_file_content("owner", "repo", "test.txt")
        assert isinstance(fc, FileContent)
        assert fc.content == "hello world"
        assert fc.size == 11

    def test_empty_file(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = {
            "type": "file",
            "encoding": "none",
            "content": "",
            "size": 0,
            "sha": "abc",
            "name": "empty.txt",
            "path": "empty.txt",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        fc = adapter.get_file_content("owner", "repo", "empty.txt")
        assert fc.content == ""

    def test_directory_raises(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = [{"name": "a"}, {"name": "b"}]
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(GitHubAPIError, match="directory"):
            adapter.get_file_content("owner", "repo", "src")

    def test_non_file_type_raises(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = {
            "type": "submodule",
            "name": "sub",
            "path": "sub",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(GitHubAPIError, match="submodule"):
            adapter.get_file_content("owner", "repo", "sub")

    def test_unsupported_encoding_raises(self):
        mock_backend = MagicMock()
        mock_backend.get_contents.return_value = {
            "type": "file",
            "encoding": "utf-16",
            "content": "data",
            "size": 4,
            "sha": "abc",
            "name": "f",
            "path": "f",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(ValueError, match="Unsupported encoding"):
            adapter.get_file_content("owner", "repo", "f")

    def test_binary_file_raises(self):
        mock_backend = MagicMock()
        encoded = base64.b64encode(b"\x80\x81\x82\x83").decode()
        mock_backend.get_contents.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": encoded,
            "size": 4,
            "sha": "abc",
            "name": "bin",
            "path": "bin",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(ValueError, match="binary"):
            adapter.get_file_content("owner", "repo", "bin")

    def test_corrupted_base64_raises(self):
        mock_backend = MagicMock()
        # Invalid base64 characters
        mock_backend.get_contents.return_value = {
            "type": "file",
            "encoding": "base64",
            "content": "!!!NotBase64!!!",
            "size": 10,
            "sha": "abc",
            "name": "corrupt.txt",
            "path": "corrupt.txt",
        }
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(ValueError, match="Failed to decode Base64"):
            adapter.get_file_content("owner", "repo", "corrupt.txt")


class TestGitHubAdapterGetIssueDetail:
    def test_basic_issue(self):
        mock_backend = MagicMock()
        mock_backend.get_issue.return_value = {
            "number": 42,
            "title": "Bug fix",
            "state": "open",
            "user": {"login": "author1"},
            "labels": [{"name": "bug", "color": "d73a4a"}],
            "assignees": [{"login": "dev1"}],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "body": "Fix the bug",
            "html_url": "https://github.com/o/r/issues/42",
            "comments": 3,
        }
        adapter = GitHubAdapter(backend=mock_backend)
        detail = adapter.get_issue_detail("o", "r", 42)
        assert isinstance(detail, IssueDetail)
        assert detail.number == 42
        assert detail.author.login == "author1"
        assert len(detail.labels) == 1
        assert detail.comments_count == 3

    def test_pull_request_raises(self):
        mock_backend = MagicMock()
        mock_backend.get_issue.return_value = {
            "number": 10,
            "title": "PR",
            "state": "open",
            "user": {"login": "u"},
            "pull_request": {"url": "..."},
        }
        adapter = GitHubAdapter(backend=mock_backend)
        with pytest.raises(ValueError, match="Pull Request"):
            adapter.get_issue_detail("o", "r", 10)

    def test_null_body(self):
        mock_backend = MagicMock()
        mock_backend.get_issue.return_value = {
            "number": 1,
            "title": "T",
            "state": "open",
            "user": {"login": "u"},
            "body": None,
        }
        adapter = GitHubAdapter(backend=mock_backend)
        detail = adapter.get_issue_detail("o", "r", 1)
        assert detail.body == ""


class TestGitHubAdapterGetIssuesList:
    def _make_issue(self, number, **kwargs):
        """Helper to create a minimal issue dict."""
        base = {
            "number": number,
            "title": f"Issue {number}",
            "state": "open",
            "user": {"login": "u"},
            "labels": [],
            "assignees": [],
            "created_at": "",
            "updated_at": "",
            "html_url": "",
        }
        base.update(kwargs)
        return base

    def test_basic_list(self):
        """Two issues returned on first page, empty second page stops pagination."""
        mock_backend = MagicMock()
        mock_backend.get_issues.side_effect = [
            [self._make_issue(1), self._make_issue(2)],
            [],  # second page empty → stops
        ]
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r", limit=10)
        assert len(issues) == 2
        assert all(isinstance(i, IssueSummary) for i in issues)

    def test_filters_pull_requests(self):
        """Pull requests (items with 'pull_request' key) are filtered out."""
        mock_backend = MagicMock()
        mock_backend.get_issues.side_effect = [
            [
                self._make_issue(1),
                {**self._make_issue(2), "pull_request": {"url": "..."}},
            ],
            [],  # stop pagination
        ]
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r", limit=30)
        assert len(issues) == 1
        assert issues[0].number == 1

    def test_limit_respected(self):
        """Limit should cap the number of returned issues."""
        mock_backend = MagicMock()
        # Return 10 issues but limit is 3
        page = [self._make_issue(i) for i in range(1, 11)]
        mock_backend.get_issues.side_effect = [page]
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r", limit=3)
        assert len(issues) == 3

    def test_empty_page_stops(self):
        """Empty first page should return no results."""
        mock_backend = MagicMock()
        mock_backend.get_issues.return_value = []
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r")
        assert issues == []

    def test_pagination_multiple_pages(self):
        """Multiple pages are fetched until limit or empty page."""
        mock_backend = MagicMock()
        page1 = [self._make_issue(i) for i in range(1, 4)]
        page2 = [self._make_issue(i) for i in range(4, 6)]
        mock_backend.get_issues.side_effect = [page1, page2, []]
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r", limit=10)
        assert len(issues) == 5

    def test_all_prs_filtered_pagination_continues(self):
        """If a page has only PRs, pagination should continue to next page."""
        mock_backend = MagicMock()
        # Page 1: only PRs
        page1 = [
            {**self._make_issue(i), "pull_request": {"url": "..."}} for i in range(1, 4)
        ]
        # Page 2: real issues
        page2 = [self._make_issue(10), self._make_issue(11)]
        mock_backend.get_issues.side_effect = [page1, page2, []]
        adapter = GitHubAdapter(backend=mock_backend)
        issues = adapter.get_issues_list("o", "r", limit=10)
        assert len(issues) == 2
        assert issues[0].number == 10
