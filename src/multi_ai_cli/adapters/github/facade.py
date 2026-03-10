"""
GitHub adapter facade (CLI entry points).

Provides handle_github_* functions invoked by dispatch_command in handlers.py.
Each function parses CLI arguments, calls the adapter, formats output,
and handles errors.
"""

from __future__ import annotations

import os
import re

from ...config import config, get_github_api_base_url, get_github_token, logger
from ...utils import secure_resolve_path
from .adapter import GitHubAdapter
from .backends.rest_backend import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRESTBackend,
)
from .models import (
    FileContent,
    IssueDetail,
    IssueSummary,
    ParsedGitHubInput,
    RepoInfo,
    TreeListing,
)

# ── Helpers ──


def _create_adapter() -> GitHubAdapter:
    """
    Create a GitHubAdapter from config-derived token and base URL.

    Returns:
        GitHubAdapter: Initialized adapter instance.

    Raises:
        ValueError: If token cannot be retrieved.
    """
    token = get_github_token()
    api_base_url = get_github_api_base_url()
    backend = GitHubRESTBackend(token=token, api_base_url=api_base_url)
    return GitHubAdapter(backend=backend)


def _parse_repo(repo_str: str) -> tuple[str, str]:
    """
    Split "owner/name" into (owner, name) tuple.

    Validates format: exactly one slash, non-empty parts, and characters
    roughly matching GitHub naming rules.

    Args:
        repo_str: Repository string in "owner/name" format.

    Returns:
        Tuple of (owner, name).

    Raises:
        ValueError: If format is invalid.
    """
    parts = repo_str.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid repository format: '{repo_str}'. Expected 'owner/name'."
        )

    owner, name = parts[0].strip(), parts[1].strip()

    if not owner or not name:
        raise ValueError(
            f"Invalid repository format: '{repo_str}'. Expected 'owner/name'."
        )

    # Basic character validation (alphanumeric, hyphen, underscore, dot)
    pattern = re.compile(r"^[a-zA-Z0-9._-]+$")
    if not pattern.match(owner) or not pattern.match(name):
        raise ValueError(
            f"Invalid repository format: '{repo_str}'. Expected 'owner/name'."
        )

    return owner, name


def _parse_github_args(parts: list[str], command_name: str) -> ParsedGitHubInput:
    """
    Parse @github.* command arguments into ParsedGitHubInput.

    Supported flags:
      --repo <owner/name>    (required for all commands)
      --path <path>          (tree, file)
      --ref <ref>            (tree, file: optional)
      --number <int>         (issue)
      --state <state>        (issues: optional, default "open")
      --limit <int>          (issues: optional, default 30)
      --label <label>        (issues: optional)
      --assignee <user>      (issues: optional)
      -w / --write <file>    (all commands: optional)
      -w:raw / -w:code       (all commands: optional, code treated as raw)

    Args:
        parts: Command token list (parts[0] is the command name).
        command_name: Command name ("repo", "tree", "file", "issue", "issues").

    Returns:
        ParsedGitHubInput instance.

    Raises:
        ValueError: If required arguments are missing or invalid.
    """
    parsed = ParsedGitHubInput()
    i = 1

    while i < len(parts):
        token = parts[i]

        if token == "--repo":
            if i + 1 >= len(parts):
                raise ValueError(
                    f"--repo requires a value. "
                    f"Usage: @github.{command_name} --repo owner/name"
                )
            parsed.repo = parts[i + 1]
            i += 2
            continue

        if token == "--path":
            if i + 1 >= len(parts):
                raise ValueError("--path requires a value.")
            parsed.path = parts[i + 1]
            i += 2
            continue

        if token == "--ref":
            if i + 1 >= len(parts):
                raise ValueError("--ref requires a value.")
            parsed.ref = parts[i + 1]
            i += 2
            continue

        if token == "--number":
            if i + 1 >= len(parts):
                raise ValueError("--number requires a value.")
            try:
                num = int(parts[i + 1])
            except ValueError:
                raise ValueError("--number must be a positive integer.")
            if num <= 0:
                raise ValueError("--number must be a positive integer.")
            parsed.number = num
            i += 2
            continue

        if token == "--state":
            if i + 1 >= len(parts):
                raise ValueError("--state requires a value.")
            state_val = parts[i + 1].lower()
            if state_val not in ("open", "closed", "all"):
                raise ValueError("--state must be 'open', 'closed', or 'all'.")
            parsed.state = state_val
            i += 2
            continue

        if token == "--limit":
            if i + 1 >= len(parts):
                raise ValueError("--limit requires a value.")
            try:
                limit_val = int(parts[i + 1])
            except ValueError:
                raise ValueError("--limit must be between 1 and 100.")
            if limit_val < 1 or limit_val > 100:
                raise ValueError("--limit must be between 1 and 100.")
            parsed.limit = limit_val
            i += 2
            continue

        if token == "--label":
            if i + 1 >= len(parts):
                raise ValueError("--label requires a value.")
            parsed.label = parts[i + 1]
            i += 2
            continue

        if token == "--assignee":
            if i + 1 >= len(parts):
                raise ValueError("--assignee requires a value.")
            parsed.assignee = parts[i + 1]
            i += 2
            continue

        # Write flag handling: -w, --write, -w:raw, -w:code, --write:raw, --write:code
        if token in ("-w", "--write"):
            if i + 1 >= len(parts):
                raise ValueError(f"Flag '{token}' requires a filename argument.")
            parsed.write_file = parts[i + 1]
            parsed.write_mode = "raw"
            i += 2
            continue

        if token in ("-w:raw", "--write:raw"):
            if i + 1 >= len(parts):
                raise ValueError(f"Flag '{token}' requires a filename argument.")
            parsed.write_file = parts[i + 1]
            parsed.write_mode = "raw"
            i += 2
            continue

        if token in ("-w:code", "--write:code"):
            # For GitHub adapter, code mode is treated as raw
            if i + 1 >= len(parts):
                raise ValueError(f"Flag '{token}' requires a filename argument.")
            parsed.write_file = parts[i + 1]
            parsed.write_mode = "raw"
            i += 2
            continue

        # Unknown flag — skip
        i += 1

    return parsed


def _output_result(
    formatted: str, parsed: ParsedGitHubInput, raw_content: str | None = None
) -> None:
    """
    Display result or write to file.

    Args:
        formatted: Formatted display string.
        parsed: Parsed input (write_file, write_mode referenced).
        raw_content: Content for file write (None → use formatted).
                     Used by @github.file to write decoded text only.
    """
    if parsed.write_file:
        out_path = secure_resolve_path(parsed.write_file, "data", config=config)
        content_to_write = raw_content if raw_content is not None else formatted
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content_to_write)
            f.flush()
            os.fsync(f.fileno())
        print(f"[*] Result saved to '{parsed.write_file}'.")
    else:
        print(f"\n{formatted}")


# ── Formatters ──


def format_repo_info(info: RepoInfo) -> str:
    """
    Format RepoInfo into a human-readable string.

    Args:
        info: RepoInfo dataclass instance.

    Returns:
        Formatted string.
    """
    visibility = "Private" if info.private else "Public"
    archived = "Yes" if info.archived else "No"
    lines = [
        f"--- Repository: {info.full_name} ---",
        f"Description:    {info.description}",
        f"Visibility:     {visibility}",
        f"Default Branch: {info.default_branch}",
        f"Language:       {info.language}",
        f"Stars:          {info.stars}",
        f"Forks:          {info.forks}",
        f"Open Issues:    {info.open_issues_count}",
        f"Archived:       {archived}",
        f"URL:            {info.url}",
        "--- End ---",
    ]
    return "\n".join(lines)


def format_tree_listing(listing: TreeListing) -> str:
    """
    Format TreeListing into a human-readable string.

    Args:
        listing: TreeListing dataclass instance.

    Returns:
        Formatted string.
    """
    ref_display = listing.ref if listing.ref else "default"
    path_display = listing.path if listing.path else "/"

    lines = [f"--- Tree: {listing.repo} @ {path_display} (ref: {ref_display}) ---"]

    for entry in listing.entries:
        if entry.entry_type.value == "dir":
            lines.append(f"  DIR  {entry.name}/")
        else:
            size_str = f" ({entry.size} bytes)" if entry.size is not None else ""
            type_label = entry.entry_type.value.upper()
            lines.append(f"  {type_label}  {entry.name}{size_str}")

    lines.append(f"--- {len(listing.entries)} entries ---")
    return "\n".join(lines)


def format_file_content(fc: FileContent) -> str:
    """
    Format FileContent into a human-readable string with header/footer.

    Args:
        fc: FileContent dataclass instance.

    Returns:
        Formatted string.
    """
    ref_display = fc.ref if fc.ref else "default"
    lines = [
        f"--- File: {fc.repo} {fc.path} (ref: {ref_display}, {fc.size} bytes) ---",
        fc.content,
        "--- End of File ---",
    ]
    return "\n".join(lines)


def format_issue_detail(issue: IssueDetail) -> str:
    """
    Format IssueDetail into a human-readable string.

    Args:
        issue: IssueDetail dataclass instance.

    Returns:
        Formatted string.
    """
    labels_str = ", ".join(lbl.name for lbl in issue.labels) if issue.labels else ""
    assignees_str = (
        ", ".join(a.login for a in issue.assignees) if issue.assignees else ""
    )

    lines = [
        f"--- Issue #{issue.number}: {issue.title} ---",
        f"State:      {issue.state}",
        f"Author:     {issue.author.login}",
        f"Labels:     {labels_str}",
        f"Assignees:  {assignees_str}",
        f"Created:    {issue.created_at}",
        f"Updated:    {issue.updated_at}",
        f"Comments:   {issue.comments_count}",
        f"URL:        {issue.url}",
        "",
        "Body:",
        issue.body,
        f"--- End of Issue #{issue.number} ---",
    ]
    return "\n".join(lines)


def format_issues_list(issues: list[IssueSummary], repo: str, state: str) -> str:
    """
    Format a list of IssueSummary into a human-readable string.

    Args:
        issues: List of IssueSummary instances.
        repo: Repository full name ("owner/name").
        state: Filter state used.

    Returns:
        Formatted string.
    """
    lines = [f"--- Issues: {repo} (state: {state}, {len(issues)} results) ---"]

    if not issues:
        lines.append("  No issues found.")
    else:
        for issue in issues:
            # Truncate title to 60 chars
            title = issue.title
            if len(title) > 60:
                title = title[:57] + "..."

            labels_str = (
                "[" + ", ".join(lbl.name for lbl in issue.labels) + "]"
                if issue.labels
                else "[]"
            )

            lines.append(
                f"  #{issue.number:<5} {issue.state:<7} "
                f"{title:<60} {labels_str:<30} @{issue.author.login}"
            )

    lines.append("--- End of Issues ---")
    return "\n".join(lines)


# ── Public handler functions ──


def handle_github_repo(parts: list[str]) -> bool:
    """
    Handle @github.repo command.

    Args:
        parts: Command token list.

    Returns:
        True on success, False on failure.
    """
    try:
        parsed = _parse_github_args(parts, "repo")

        if parsed.repo is None:
            print(
                "[!] @github.repo: --repo is required. "
                "Usage: @github.repo --repo owner/name"
            )
            return False

        owner, name = _parse_repo(parsed.repo)
        adapter = _create_adapter()
        result = adapter.get_repo_info(owner, name)
        formatted = format_repo_info(result)
        _output_result(formatted, parsed)
        return True

    except ValueError as e:
        print(f"[!] @github.repo: {e}")
        logger.error(f"@github.repo: {e}")
        return False
    except GitHubNotFoundError:
        print(f"[!] @github.repo: Repository '{parsed.repo}' not found.")
        logger.error(f"@github.repo: 404 for '{parsed.repo}'")
        return False
    except GitHubAuthError:
        print("[!] @github.repo: Authentication failed. Check your GitHub token.")
        logger.error("@github.repo: 401 Unauthorized")
        return False
    except GitHubRateLimitError:
        print("[!] @github.repo: GitHub API rate limit exceeded. Try again later.")
        logger.error("@github.repo: Rate limit exceeded")
        return False
    except GitHubForbiddenError:
        print(
            "[!] @github.repo: Access denied. "
            "Token may lack required permissions for this repository."
        )
        logger.error("@github.repo: 403 Forbidden")
        return False
    except GitHubAPIError as e:
        print(f"[!] @github.repo: GitHub API error ({e.status_code}): {e.message}")
        logger.error(f"@github.repo: API error: {e}")
        return False
    except Exception as e:
        print(f"[!] @github.repo: Unexpected error: {e}")
        logger.error(f"@github.repo: Unexpected error: {e}")
        return False


def handle_github_tree(parts: list[str]) -> bool:
    """
    Handle @github.tree command.

    Args:
        parts: Command token list.

    Returns:
        True on success, False on failure.
    """
    try:
        parsed = _parse_github_args(parts, "tree")

        if parsed.repo is None:
            print(
                "[!] @github.tree: --repo is required. "
                "Usage: @github.tree --repo owner/name"
            )
            return False

        path = parsed.path if parsed.path is not None else ""

        owner, name = _parse_repo(parsed.repo)
        adapter = _create_adapter()
        result = adapter.get_tree(owner, name, path, parsed.ref)
        formatted = format_tree_listing(result)
        _output_result(formatted, parsed)
        return True

    except ValueError as e:
        print(f"[!] @github.tree: {e}")
        logger.error(f"@github.tree: {e}")
        return False
    except GitHubNotFoundError:
        path_display = parsed.path or "/"
        print(
            f"[!] @github.tree: Path '{path_display}' not found "
            f"in repository '{parsed.repo}'."
        )
        logger.error(f"@github.tree: 404 for path '{path_display}' in '{parsed.repo}'")
        return False
    except GitHubAuthError:
        print("[!] @github.tree: Authentication failed. Check your GitHub token.")
        logger.error("@github.tree: 401 Unauthorized")
        return False
    except GitHubRateLimitError:
        print("[!] @github.tree: GitHub API rate limit exceeded. Try again later.")
        logger.error("@github.tree: Rate limit exceeded")
        return False
    except GitHubForbiddenError:
        print(
            "[!] @github.tree: Access denied. "
            "Token may lack required permissions for this repository."
        )
        logger.error("@github.tree: 403 Forbidden")
        return False
    except GitHubAPIError as e:
        print(f"[!] @github.tree: GitHub API error ({e.status_code}): {e.message}")
        logger.error(f"@github.tree: API error: {e}")
        return False
    except Exception as e:
        print(f"[!] @github.tree: Unexpected error: {e}")
        logger.error(f"@github.tree: Unexpected error: {e}")
        return False


def handle_github_file(parts: list[str]) -> bool:
    """
    Handle @github.file command.

    Args:
        parts: Command token list.

    Returns:
        True on success, False on failure.
    """
    try:
        parsed = _parse_github_args(parts, "file")

        if parsed.repo is None:
            print(
                "[!] @github.file: --repo is required. "
                "Usage: @github.file --repo owner/name --path <file>"
            )
            return False

        if parsed.path is None:
            print("[!] @github.file: --path is required.")
            return False

        owner, name = _parse_repo(parsed.repo)
        adapter = _create_adapter()
        result = adapter.get_file_content(owner, name, parsed.path, parsed.ref)
        formatted = format_file_content(result)

        # For -w, write raw decoded content only (no header/footer)
        _output_result(formatted, parsed, raw_content=result.content)
        return True

    except ValueError as e:
        print(f"[!] @github.file: {e}")
        logger.error(f"@github.file: {e}")
        return False
    except GitHubNotFoundError:
        print(
            f"[!] @github.file: File '{parsed.path}' not found "
            f"in repository '{parsed.repo}'."
        )
        logger.error(f"@github.file: 404 for file '{parsed.path}' in '{parsed.repo}'")
        return False
    except GitHubAuthError:
        print("[!] @github.file: Authentication failed. Check your GitHub token.")
        logger.error("@github.file: 401 Unauthorized")
        return False
    except GitHubRateLimitError:
        print("[!] @github.file: GitHub API rate limit exceeded. Try again later.")
        logger.error("@github.file: Rate limit exceeded")
        return False
    except GitHubForbiddenError:
        print(
            "[!] @github.file: Access denied. "
            "Token may lack required permissions for this repository."
        )
        logger.error("@github.file: 403 Forbidden")
        return False
    except GitHubAPIError as e:
        print(f"[!] @github.file: GitHub API error ({e.status_code}): {e.message}")
        logger.error(f"@github.file: API error: {e}")
        return False
    except Exception as e:
        print(f"[!] @github.file: Unexpected error: {e}")
        logger.error(f"@github.file: Unexpected error: {e}")
        return False


def handle_github_issue(parts: list[str]) -> bool:
    """
    Handle @github.issue command.

    Args:
        parts: Command token list.

    Returns:
        True on success, False on failure.
    """
    try:
        parsed = _parse_github_args(parts, "issue")

        if parsed.repo is None:
            print(
                "[!] @github.issue: --repo is required. "
                "Usage: @github.issue --repo owner/name --number <int>"
            )
            return False

        if parsed.number is None:
            print("[!] @github.issue: --number is required.")
            return False

        owner, name = _parse_repo(parsed.repo)
        adapter = _create_adapter()
        result = adapter.get_issue_detail(owner, name, parsed.number)
        formatted = format_issue_detail(result)
        _output_result(formatted, parsed)
        return True

    except ValueError as e:
        print(f"[!] @github.issue: {e}")
        logger.error(f"@github.issue: {e}")
        return False
    except GitHubNotFoundError:
        print(
            f"[!] @github.issue: Issue #{parsed.number} not found "
            f"in repository '{parsed.repo}'."
        )
        logger.error(
            f"@github.issue: 404 for issue #{parsed.number} in '{parsed.repo}'"
        )
        return False
    except GitHubAuthError:
        print("[!] @github.issue: Authentication failed. Check your GitHub token.")
        logger.error("@github.issue: 401 Unauthorized")
        return False
    except GitHubRateLimitError:
        print("[!] @github.issue: GitHub API rate limit exceeded. Try again later.")
        logger.error("@github.issue: Rate limit exceeded")
        return False
    except GitHubForbiddenError:
        print(
            "[!] @github.issue: Access denied. "
            "Token may lack required permissions for this repository."
        )
        logger.error("@github.issue: 403 Forbidden")
        return False
    except GitHubAPIError as e:
        print(f"[!] @github.issue: GitHub API error ({e.status_code}): {e.message}")
        logger.error(f"@github.issue: API error: {e}")
        return False
    except Exception as e:
        print(f"[!] @github.issue: Unexpected error: {e}")
        logger.error(f"@github.issue: Unexpected error: {e}")
        return False


def handle_github_issues(parts: list[str]) -> bool:
    """
    Handle @github.issues command.

    Args:
        parts: Command token list.

    Returns:
        True on success, False on failure.
    """
    try:
        parsed = _parse_github_args(parts, "issues")

        if parsed.repo is None:
            print(
                "[!] @github.issues: --repo is required. "
                "Usage: @github.issues --repo owner/name"
            )
            return False

        owner, name = _parse_repo(parsed.repo)
        state = parsed.state if parsed.state else "open"

        adapter = _create_adapter()
        result = adapter.get_issues_list(
            owner=owner,
            repo=name,
            state=state,
            label=parsed.label,
            assignee=parsed.assignee,
            limit=parsed.limit,
        )
        formatted = format_issues_list(result, parsed.repo, state)
        _output_result(formatted, parsed)
        return True

    except ValueError as e:
        print(f"[!] @github.issues: {e}")
        logger.error(f"@github.issues: {e}")
        return False
    except GitHubNotFoundError:
        print(f"[!] @github.issues: Repository '{parsed.repo}' not found.")
        logger.error(f"@github.issues: 404 for '{parsed.repo}'")
        return False
    except GitHubAuthError:
        print("[!] @github.issues: Authentication failed. Check your GitHub token.")
        logger.error("@github.issues: 401 Unauthorized")
        return False
    except GitHubRateLimitError:
        print("[!] @github.issues: GitHub API rate limit exceeded. Try again later.")
        logger.error("@github.issues: Rate limit exceeded")
        return False
    except GitHubForbiddenError:
        print(
            "[!] @github.issues: Access denied. "
            "Token may lack required permissions for this repository."
        )
        logger.error("@github.issues: 403 Forbidden")
        return False
    except GitHubAPIError as e:
        print(f"[!] @github.issues: GitHub API error ({e.status_code}): {e.message}")
        logger.error(f"@github.issues: API error: {e}")
        return False
    except Exception as e:
        print(f"[!] @github.issues: Unexpected error: {e}")
        logger.error(f"@github.issues: Unexpected error: {e}")
        return False
