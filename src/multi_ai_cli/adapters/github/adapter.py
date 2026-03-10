"""
GitHub adapter layer.

High-level read-only GitHub adapter that converts raw API responses
from the REST backend into typed dataclass models.
"""

from __future__ import annotations

import base64
from typing import Any

from .backends.rest_backend import GitHubAPIError, GitHubRESTBackend
from .models import (
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

# Mapping from GitHub API type string to TreeEntryType enum
_TYPE_MAP: dict[str, TreeEntryType] = {
    "file": TreeEntryType.FILE,
    "dir": TreeEntryType.DIR,
    "submodule": TreeEntryType.SUBMODULE,
    "symlink": TreeEntryType.SYMLINK,
}


class GitHubAdapter:
    """High-level read-only GitHub adapter."""

    def __init__(self, backend: GitHubRESTBackend) -> None:
        """
        Initialize the adapter with a backend instance.

        Args:
            backend: Initialized GitHubRESTBackend instance.
        """
        self._backend = backend

    def get_repo_info(self, owner: str, repo: str) -> RepoInfo:
        """
        Fetch repository metadata and convert to RepoInfo.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            RepoInfo dataclass instance.
        """
        data = self._backend.get_repository(owner, repo)
        return RepoInfo(
            full_name=data["full_name"],
            description=data.get("description") or "",
            private=data["private"],
            default_branch=data["default_branch"],
            stars=data["stargazers_count"],
            forks=data["forks_count"],
            open_issues_count=data["open_issues_count"],
            url=data["html_url"],
            language=data.get("language") or "",
            archived=data["archived"],
        )

    def get_tree(
        self, owner: str, repo: str, path: str = "", ref: str | None = None
    ) -> TreeListing:
        """
        Fetch directory listing and convert to TreeListing.

        If the response is a list (directory), each element is converted to
        a TreeEntry. If the response is a dict (single file/resource), it
        is wrapped as a single-entry TreeListing.

        Entries are sorted: directories first, then files, alphabetically.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: Directory path within the repository (default: root).
            ref: Branch/tag/SHA (optional).

        Returns:
            TreeListing dataclass instance.
        """
        data = self._backend.get_contents(owner, repo, path, ref)
        repo_full = f"{owner}/{repo}"

        entries: list[TreeEntry] = []

        items: list[dict[str, Any]]
        if isinstance(data, list):
            items = data
        else:
            # Single file/resource returned as dict
            items = [data]

        for item in items:
            entry_type = _TYPE_MAP.get(item.get("type", ""), TreeEntryType.FILE)
            entries.append(
                TreeEntry(
                    name=item["name"],
                    path=item["path"],
                    entry_type=entry_type,
                    size=item.get("size") if entry_type == TreeEntryType.FILE else None,
                    sha=item.get("sha", ""),
                )
            )

        # Sort: directories first, then alphabetically by name
        entries.sort(
            key=lambda e: (
                0 if e.entry_type == TreeEntryType.DIR else 1,
                e.name.lower(),
            )
        )

        return TreeListing(
            repo=repo_full,
            path=path,
            ref=ref,
            entries=entries,
        )

    def get_file_content(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> FileContent:
        """
        Fetch file content, decode it, and return as FileContent.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: File path within the repository.
            ref: Branch/tag/SHA (optional).

        Returns:
            FileContent dataclass instance.

        Raises:
            GitHubAPIError: If the path is a directory.
            ValueError: If the file is binary or has unsupported encoding.
        """
        data = self._backend.get_contents(owner, repo, path, ref)

        # If response is a list, it means the path is a directory
        if isinstance(data, list):
            raise GitHubAPIError(
                status_code=400,
                message=(
                    f"Path '{path}' is a directory, not a file. "
                    f"Use @github.tree instead."
                ),
            )

        file_type = data.get("type", "")
        if file_type != "file":
            raise GitHubAPIError(
                status_code=400,
                message=(
                    f"Path '{path}' is a {file_type}, not a file. "
                    f"Use @github.tree instead."
                ),
            )

        encoding = data.get("encoding", "")
        raw_content = data.get("content", "")
        repo_full = f"{owner}/{repo}"

        if encoding == "base64":
            try:
                decoded_bytes = base64.b64decode(raw_content)
            except Exception as e:
                raise ValueError(
                    f"Failed to decode Base64 content for file '{path}': {e}"
                )
            try:
                decoded_text = decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError(
                    f"File '{path}' appears to be binary. "
                    f"Binary files are not supported in v1."
                )
        elif encoding == "none" or encoding == "":
            # Empty file or no encoding
            decoded_text = ""
        else:
            raise ValueError(f"Unsupported encoding '{encoding}' for file '{path}'.")

        return FileContent(
            repo=repo_full,
            path=path,
            ref=ref,
            content=decoded_text,
            size=data.get("size", 0),
            sha=data.get("sha", ""),
            encoding=encoding,
        )

    def get_issue_detail(self, owner: str, repo: str, issue_number: int) -> IssueDetail:
        """
        Fetch a single issue detail and convert to IssueDetail.

        Args:
            owner: Repository owner.
            repo: Repository name.
            issue_number: Issue number.

        Returns:
            IssueDetail dataclass instance.

        Raises:
            ValueError: If the fetched item is a pull request.
        """
        data = self._backend.get_issue(owner, repo, issue_number)

        # Check if this is actually a PR
        if "pull_request" in data:
            raise ValueError(
                f"#{issue_number} is a Pull Request, not an Issue. "
                f"PR support is not included in v1."
            )

        return IssueDetail(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            author=IssueUser(login=data["user"]["login"]),
            labels=[
                IssueLabel(name=lbl["name"], color=lbl.get("color", ""))
                for lbl in data.get("labels", [])
            ],
            assignees=[IssueUser(login=a["login"]) for a in data.get("assignees", [])],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            body=data.get("body") or "",
            url=data.get("html_url", ""),
            comments_count=data.get("comments", 0),
        )

    def get_issues_list(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        label: str | None = None,
        assignee: str | None = None,
        limit: int = 30,
    ) -> list[IssueSummary]:
        """
        Fetch issue list and convert to a list of IssueSummary.

        Pull requests are filtered out. Pagination is handled automatically
        until the limit is reached.

        Args:
            owner: Repository owner.
            repo: Repository name.
            state: "open", "closed", or "all".
            label: Label filter (single label).
            assignee: Assignee filter.
            limit: Maximum number of issues to return.

        Returns:
            List of IssueSummary dataclass instances.
        """
        results: list[IssueSummary] = []
        page = 1
        per_page = min(limit, 100)

        while len(results) < limit:
            items = self._backend.get_issues(
                owner=owner,
                repo=repo,
                state=state,
                labels=label,
                assignee=assignee,
                per_page=per_page,
                page=page,
            )

            # Empty page means no more results
            if not items:
                break

            for item in items:
                # Filter out pull requests
                if "pull_request" in item:
                    continue

                results.append(
                    IssueSummary(
                        number=item["number"],
                        title=item["title"],
                        state=item["state"],
                        author=IssueUser(login=item["user"]["login"]),
                        labels=[
                            IssueLabel(name=lbl["name"], color=lbl.get("color", ""))
                            for lbl in item.get("labels", [])
                        ],
                        assignees=[
                            IssueUser(login=a["login"])
                            for a in item.get("assignees", [])
                        ],
                        created_at=item.get("created_at", ""),
                        updated_at=item.get("updated_at", ""),
                        url=item.get("html_url", ""),
                    )
                )

                if len(results) >= limit:
                    break

            page += 1

        return results[:limit]
