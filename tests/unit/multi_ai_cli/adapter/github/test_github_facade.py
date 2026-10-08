"""Tests for multi_ai_cli.adapters.github.facade module."""

import pytest

from multi_ai_cli.adapters.github.facade import (
    _parse_github_args,
    _parse_repo,
    format_file_content,
    format_issue_detail,
    format_issues_list,
    format_repo_info,
    format_tree_listing,
)
from multi_ai_cli.adapters.github.models import (
    FileContent,
    IssueDetail,
    IssueLabel,
    IssueSummary,
    IssueUser,
    RepoInfo,
    TreeEntry,
    TreeEntryType,
    TreeListing,
)


class TestParseRepo:
    def test_valid(self):
        owner, name = _parse_repo("owner/repo")
        assert owner == "owner"
        assert name == "repo"

    def test_with_special_chars(self):
        owner, name = _parse_repo("my-org/my_repo.js")
        assert owner == "my-org"
        assert name == "my_repo.js"

    def test_no_slash(self):
        with pytest.raises(ValueError, match="Invalid repository format"):
            _parse_repo("noslash")

    def test_too_many_slashes(self):
        with pytest.raises(ValueError, match="Invalid repository format"):
            _parse_repo("a/b/c")

    def test_empty_parts(self):
        with pytest.raises(ValueError, match="Invalid repository format"):
            _parse_repo("/repo")

    def test_invalid_chars(self):
        with pytest.raises(ValueError, match="Invalid repository format"):
            _parse_repo("owner/repo name")

    def test_boundary_chars(self):
        # GitHub allows dots and hyphens, but leading/trailing ones might be restrictive
        # depending on the regex. The regex is ^[a-zA-Z0-9._-]+$
        # Test that these specific characters are accepted.
        owner, name = _parse_repo("-o./r._-")
        assert owner == "-o." and name == "/r._-".lstrip("/")  # wait, split by /
        # Re-testing carefully based on current _parse_repo logic
        # _parse_repo("-o./r._-") -> parts = ["-o.", "r._-"] -> passes regex.
        owner, name = _parse_repo("-o./r._-")
        assert owner == "-o."
        assert name == "r._-"


class TestParseGitHubArgs:
    def test_repo_only(self):
        parsed = _parse_github_args(["@github.repo", "--repo", "o/r"], "repo")
        assert parsed.repo == "o/r"

    def test_path(self):
        parsed = _parse_github_args(
            ["@github.tree", "--repo", "o/r", "--path", "src/"], "tree"
        )
        assert parsed.path == "src/"

    def test_ref(self):
        parsed = _parse_github_args(
            ["@github.file", "--repo", "o/r", "--path", "f", "--ref", "v1.0"], "file"
        )
        assert parsed.ref == "v1.0"

    def test_number(self):
        parsed = _parse_github_args(
            ["@github.issue", "--repo", "o/r", "--number", "42"], "issue"
        )
        assert parsed.number == 42

    def test_invalid_number(self):
        with pytest.raises(ValueError, match="positive integer"):
            _parse_github_args(
                ["@github.issue", "--repo", "o/r", "--number", "abc"], "issue"
            )

    def test_negative_number(self):
        with pytest.raises(ValueError, match="positive integer"):
            _parse_github_args(
                ["@github.issue", "--repo", "o/r", "--number", "-1"], "issue"
            )

    def test_state(self):
        parsed = _parse_github_args(
            ["@github.issues", "--repo", "o/r", "--state", "closed"], "issues"
        )
        assert parsed.state == "closed"

    def test_invalid_state(self):
        with pytest.raises(ValueError, match="must be"):
            _parse_github_args(
                ["@github.issues", "--repo", "o/r", "--state", "invalid"], "issues"
            )

    def test_limit(self):
        parsed = _parse_github_args(
            ["@github.issues", "--repo", "o/r", "--limit", "50"], "issues"
        )
        assert parsed.limit == 50

    def test_limit_out_of_range(self):
        with pytest.raises(ValueError, match="between 1 and 100"):
            _parse_github_args(
                ["@github.issues", "--repo", "o/r", "--limit", "0"], "issues"
            )

    def test_limit_too_high(self):
        with pytest.raises(ValueError, match="between 1 and 100"):
            _parse_github_args(
                ["@github.issues", "--repo", "o/r", "--limit", "101"], "issues"
            )

    def test_label(self):
        parsed = _parse_github_args(
            ["@github.issues", "--repo", "o/r", "--label", "bug"], "issues"
        )
        assert parsed.label == "bug"

    def test_assignee(self):
        parsed = _parse_github_args(
            ["@github.issues", "--repo", "o/r", "--assignee", "dev1"], "issues"
        )
        assert parsed.assignee == "dev1"

    def test_write_flag(self):
        parsed = _parse_github_args(
            ["@github.repo", "--repo", "o/r", "-w", "out.txt"], "repo"
        )
        assert parsed.write_file == "out.txt"
        assert parsed.write_mode == "raw"

    def test_write_raw(self):
        parsed = _parse_github_args(
            ["@github.repo", "--repo", "o/r", "-w:raw", "out.txt"], "repo"
        )
        assert parsed.write_file == "out.txt"
        assert parsed.write_mode == "raw"

    def test_write_code(self):
        parsed = _parse_github_args(
            ["@github.repo", "--repo", "o/r", "-w:code", "out.txt"], "repo"
        )
        assert parsed.write_file == "out.txt"
        assert parsed.write_mode == "raw"  # code treated as raw for GitHub

    def test_missing_repo_value(self):
        with pytest.raises(ValueError, match="requires a value"):
            _parse_github_args(["@github.repo", "--repo"], "repo")

    def test_missing_path_value(self):
        with pytest.raises(ValueError, match="requires a value"):
            _parse_github_args(["@github.tree", "--repo", "o/r", "--path"], "tree")

    def test_missing_write_value(self):
        with pytest.raises(ValueError, match="requires a filename"):
            _parse_github_args(["@github.repo", "--repo", "o/r", "-w"], "repo")

    def test_unknown_flag(self):
        # Currently, unknown flags are silently ignored by _parse_github_args
        parsed = _parse_github_args(
            ["@github.repo", "--repo", "o/r", "--unknown", "val"], "repo"
        )
        assert parsed.repo == "o/r"

    def test_missing_repo_required(self):
        # The current implementation of _parse_github_args does not explicitly validate
        # that --repo is present; it simply returns the ParsedGitHubInput object.
        # This test documents current behavior.
        parsed = _parse_github_args(["@github.tree", "--path", "src/"], "tree")
        assert parsed.repo is None
        assert parsed.path == "src/"


class TestFormatRepoInfo:
    def test_basic(self):
        info = RepoInfo(
            full_name="owner/repo",
            description="A test repo",
            private=False,
            default_branch="main",
            stars=100,
            forks=20,
            open_issues_count=5,
            url="https://github.com/owner/repo",
            language="Python",
            archived=False,
        )
        result = format_repo_info(info)
        assert "owner/repo" in result
        assert "Public" in result
        assert "main" in result
        assert "100" in result
        assert "Python" in result
        assert "No" in result  # archived

    def test_private_archived(self):
        info = RepoInfo(
            full_name="o/r",
            description="",
            private=True,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues_count=0,
            url="",
            language="",
            archived=True,
        )
        result = format_repo_info(info)
        assert "Private" in result
        assert "Yes" in result  # archived


class TestFormatTreeListing:
    def test_basic(self):
        listing = TreeListing(
            repo="o/r",
            path="src",
            ref="main",
            entries=[
                TreeEntry("dir1", "src/dir1", TreeEntryType.DIR, None, "sha1"),
                TreeEntry("file.py", "src/file.py", TreeEntryType.FILE, 500, "sha2"),
            ],
        )
        result = format_tree_listing(listing)
        assert "o/r" in result
        assert "dir1/" in result
        assert "file.py" in result
        assert "500 bytes" in result
        assert "2 entries" in result

    def test_default_ref(self):
        listing = TreeListing(repo="o/r", path="", ref=None, entries=[])
        result = format_tree_listing(listing)
        assert "default" in result

    def test_root_path(self):
        listing = TreeListing(repo="o/r", path="", ref=None, entries=[])
        result = format_tree_listing(listing)
        assert "/" in result


class TestFormatFileContent:
    def test_basic(self):
        fc = FileContent(
            repo="o/r",
            path="main.py",
            ref="main",
            content="print('hello')",
            size=14,
            sha="abc",
            encoding="base64",
        )
        result = format_file_content(fc)
        assert "main.py" in result
        assert "print('hello')" in result
        assert "End of File" in result

    def test_default_ref(self):
        fc = FileContent(
            repo="o/r", path="f", ref=None, content="", size=0, sha="a", encoding=""
        )
        result = format_file_content(fc)
        assert "default" in result


class TestFormatIssueDetail:
    def test_basic(self):
        issue = IssueDetail(
            number=42,
            title="Bug report",
            state="open",
            author=IssueUser(login="reporter"),
            labels=[IssueLabel(name="bug", color="red")],
            assignees=[IssueUser(login="dev1")],
            created_at="2024-01-01",
            updated_at="2024-01-02",
            body="Fix this bug",
            url="https://github.com/o/r/issues/42",
            comments_count=3,
        )
        result = format_issue_detail(issue)
        assert "#42" in result
        assert "Bug report" in result
        assert "reporter" in result
        assert "bug" in result
        assert "dev1" in result
        assert "Fix this bug" in result

    def test_no_labels_assignees(self):
        issue = IssueDetail(
            number=1,
            title="T",
            state="open",
            author=IssueUser(login="u"),
        )
        result = format_issue_detail(issue)
        assert "#1" in result


class TestFormatIssuesList:
    def test_basic(self):
        issues = [
            IssueSummary(
                number=1,
                title="Issue 1",
                state="open",
                author=IssueUser(login="u1"),
                labels=[IssueLabel(name="bug", color="red")],
            ),
            IssueSummary(
                number=2,
                title="Issue 2",
                state="closed",
                author=IssueUser(login="u2"),
            ),
        ]
        result = format_issues_list(issues, "o/r", "all")
        assert "o/r" in result
        assert "#1" in result
        assert "#2" in result
        assert "2 results" in result

    def test_empty_list(self):
        result = format_issues_list([], "o/r", "open")
        assert "No issues found" in result
        assert "0 results" in result

    def test_long_title_truncated(self):
        issues = [
            IssueSummary(
                number=1,
                title="A" * 100,
                state="open",
                author=IssueUser(login="u"),
            )
        ]
        result = format_issues_list(issues, "o/r", "open")
        assert "..." in result
