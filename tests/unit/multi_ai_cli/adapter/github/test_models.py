"""Tests for multi_ai_cli.adapters.github.models module."""

from multi_ai_cli.adapters.github.models import (
    FileContent,
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
