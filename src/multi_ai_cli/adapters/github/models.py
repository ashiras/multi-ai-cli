"""
Data models for the GitHub adapter.

All dataclasses used to represent normalized GitHub API responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TreeEntryType(Enum):
    """Type of entry in a repository tree."""

    FILE = "file"
    DIR = "dir"
    SUBMODULE = "submodule"
    SYMLINK = "symlink"


@dataclass
class RepoInfo:
    """Repository metadata."""

    full_name: str  # "owner/repo"
    description: str  # Repository description (may be empty string)
    private: bool  # Whether the repo is private
    default_branch: str  # Default branch name
    stars: int  # Star count
    forks: int  # Fork count
    open_issues_count: int  # Open issue count
    url: str  # html_url
    language: str  # Primary language (may be empty string)
    archived: bool  # Whether the repo is archived


@dataclass
class TreeEntry:
    """Single entry in a directory listing."""

    name: str  # File/directory name
    path: str  # Relative path from repository root
    entry_type: TreeEntryType  # file / dir / submodule / symlink
    size: int | None  # Byte size (file only, None for dir)
    sha: str  # Git SHA


@dataclass
class TreeListing:
    """Directory listing result."""

    repo: str  # "owner/repo"
    path: str  # Target directory path
    ref: str | None  # Branch/tag/SHA (if specified)
    entries: list[TreeEntry] = field(default_factory=list)


@dataclass
class FileContent:
    """Decoded file content from a repository."""

    repo: str  # "owner/repo"
    path: str  # File path
    ref: str | None  # Branch/tag/SHA
    content: str  # Decoded text content
    size: int  # Byte size
    sha: str  # Git SHA
    encoding: str  # Encoding returned by GitHub API (e.g. "base64")


@dataclass
class IssueLabel:
    """Issue label."""

    name: str
    color: str  # Hex color (e.g. "d73a4a")


@dataclass
class IssueUser:
    """Minimal user info for issue author/assignee."""

    login: str


@dataclass
class IssueSummary:
    """Issue list entry (compact)."""

    number: int
    title: str
    state: str  # "open" or "closed"
    author: IssueUser
    labels: list[IssueLabel] = field(default_factory=list)
    assignees: list[IssueUser] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    url: str = ""


@dataclass
class IssueDetail:
    """Full issue detail."""

    number: int
    title: str
    state: str  # "open" or "closed"
    author: IssueUser
    labels: list[IssueLabel] = field(default_factory=list)
    assignees: list[IssueUser] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    body: str = ""  # Markdown body
    url: str = ""
    comments_count: int = 0


@dataclass
class ParsedGitHubInput:
    """Parsed CLI input for @github.* commands."""

    repo: str | None = None  # "owner/name"
    path: str | None = None  # File/directory path
    ref: str | None = None  # Branch/tag/SHA
    number: int | None = None  # Issue number
    state: str | None = None  # "open", "closed", "all"
    limit: int = 30  # Issue list fetch limit
    label: str | None = None  # Label filter
    assignee: str | None = None  # Assignee filter
    write_file: str | None = None  # -w output destination
    write_mode: str = "raw"  # "raw" or "code"
