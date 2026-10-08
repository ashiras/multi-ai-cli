"""Tests for multi_ai_cli.adapters.github.models module."""

from multi_ai_cli.adapters.github.models import (
    FileContent,
    IssueDetail,
    IssueLabel,
    IssueSummary,
    IssueUser,
    ParsedGitHubInput,
    RepoInfo,
    TreeEntry,
    TreeEntryType,
)


def test_repo_info_instantiation():
    info = RepoInfo(
        full_name="o/r",
        description="desc",
        private=False,
        default_branch="main",
        stars=0,
        forks=0,
        open_issues_count=0,
        url="https://github.com/o/r",
        language="Python",
        archived=False,
    )
    assert info.full_name == "o/r"
    assert info.description == "desc"
    assert info.stars == 0


def test_tree_entry_instantiation():
    entry = TreeEntry(
        name="test.py",
        path="src/test.py",
        entry_type=TreeEntryType.FILE,
        size=1024,
        sha="abc1234567890abcdef",
    )
    assert entry.name == "test.py"
    assert entry.entry_type == TreeEntryType.FILE


def test_file_content_instantiation():
    content = FileContent(
        repo="o/r",
        path="README.md",
        ref="main",
        content="Hello",
        size=5,
        sha="xyz123",
        encoding="utf-8",
    )
    assert content.path == "README.md"
    assert content.content == "Hello"


def test_issue_models_instantiation():
    user = IssueUser(login="octocat")
    label = IssueLabel(name="bug", color="d73a4a")

    summary = IssueSummary(
        number=1, title="Fix bug", state="open", author=user, labels=[label]
    )
    assert summary.number == 1
    assert summary.labels[0].name == "bug"
    assert summary.assignees == []

    detail = IssueDetail(
        number=1,
        title="Fix bug",
        state="open",
        author=user,
        body="Detailed description",
        comments_count=2,
    )
    assert detail.body == "Detailed description"
    assert detail.comments_count == 2
    assert detail.created_at == ""


def test_parsed_github_input_instantiation():
    # Test defaults
    default_input = ParsedGitHubInput()
    assert default_input.limit == 30
    assert default_input.repo is None
    assert default_input.write_mode == "raw"

    # Test custom values
    custom_input = ParsedGitHubInput(
        repo="owner/repo", number=10, limit=50, write_mode="code"
    )
    assert custom_input.repo == "owner/repo"
    assert custom_input.number == 10
    assert custom_input.limit == 50
    assert custom_input.write_mode == "code"
