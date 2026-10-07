#!/usr/bin/env python3
"""Fail when the current task adds an AST-equivalent duplicate assert."""

from __future__ import annotations

import argparse
import ast
import collections
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Assertion:
    scope: str
    normalized: str
    line: int
    source: str


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def changed_python_tests(root: str) -> list[str]:
    tracked = run_git(
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        "HEAD",
        "--",
        root,
    ).stdout.splitlines()

    untracked = run_git(
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        root,
    ).stdout.splitlines()

    paths = {
        path.strip()
        for path in [*tracked, *untracked]
        if path.strip().endswith(".py")
    }
    return sorted(paths)


def read_head(path: str) -> str | None:
    result = run_git("show", f"HEAD:{path}", check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def scope_name(parts: list[str]) -> str:
    return "::".join(parts) if parts else "<module>"


def collect_assertions(source: str, filename: str) -> list[Assertion]:
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    found: list[Assertion] = []

    def visit_body(body: list[ast.stmt], scope: list[str]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Assert):
                text = ""
                if 1 <= stmt.lineno <= len(lines):
                    text = lines[stmt.lineno - 1].strip()
                found.append(
                    Assertion(
                        scope=scope_name(scope),
                        normalized=ast.dump(stmt, include_attributes=False),
                        line=stmt.lineno,
                        source=text,
                    )
                )

            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit_body(stmt.body, [*scope, f"function:{stmt.name}"])
            elif isinstance(stmt, ast.ClassDef):
                visit_body(stmt.body, [*scope, f"class:{stmt.name}"])

    visit_body(tree.body, [])
    return found


def find_new_duplicates(path: str) -> list[Assertion]:
    current_text = Path(path).read_text(encoding="utf-8")
    current = collect_assertions(current_text, path)

    base_text = read_head(path)
    base = collect_assertions(base_text, path) if base_text is not None else []

    base_counts = collections.Counter((item.scope, item.normalized) for item in base)
    current_seen: collections.Counter[tuple[str, str]] = collections.Counter()
    duplicates: list[Assertion] = []

    for item in current:
        key = (item.scope, item.normalized)
        current_seen[key] += 1

        if base_text is None:
            # New file: allow the first occurrence, reject exact repeats.
            if current_seen[key] > 1:
                duplicates.append(item)
            continue

        # Existing file: reject only occurrences added beyond the HEAD count.
        if base_counts[key] > 0 and current_seen[key] > base_counts[key]:
            duplicates.append(item)

    return duplicates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detect AST-equivalent duplicate assert statements introduced "
            "since HEAD in changed Python tests."
        )
    )
    parser.add_argument(
        "--root",
        default="tests",
        help="Git-relative test root to inspect (default: tests)",
    )
    args = parser.parse_args()

    paths = changed_python_tests(args.root)
    if not paths:
        print("duplicate-check: PASS (no changed Python tests)")
        return 0

    violations: list[tuple[str, Assertion]] = []
    for path in paths:
        try:
            for duplicate in find_new_duplicates(path):
                violations.append((path, duplicate))
        except (OSError, SyntaxError) as exc:
            print(f"duplicate-check: ERROR: {path}: {exc}", file=sys.stderr)
            return 2

    if not violations:
        print(
            f"duplicate-check: PASS "
            f"({len(paths)} changed Python test file(s) inspected)"
        )
        return 0

    print("duplicate-check: FAIL", file=sys.stderr)
    print(
        "New AST-equivalent duplicate assert statement(s) detected:",
        file=sys.stderr,
    )
    for path, item in violations:
        print(
            f"  {path}:{item.line}: scope={item.scope}: {item.source}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
