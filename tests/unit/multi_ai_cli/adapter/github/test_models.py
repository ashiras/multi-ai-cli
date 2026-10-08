"""Tests for multi_ai_cli.adapters.github.models module."""

from multi_ai_cli.adapters.github.models import RepoInfo


def test_repo_info_minimal():
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
