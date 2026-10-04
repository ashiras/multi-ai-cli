"""File utility helpers for reading and writing UTF-8 text files."""

from glob import glob
from pathlib import Path


def read_file(path: str) -> str:
    """Read and return the UTF-8 text content of a file."""
    target = Path(path)

    if not target.exists():
        raise FileNotFoundError(f"file not found: {path}")

    if not target.is_file():
        raise ValueError(f"not a file: {path}")

    return target.read_text(encoding="utf-8")


def resolve_read_paths(pattern: str) -> list[Path]:
    """Resolve a file path or glob pattern into matching regular files."""
    paths = [
        Path(p) for p in sorted(glob(pattern, recursive=True)) if Path(p).is_file()
    ]

    if not paths:
        raise FileNotFoundError(f"no files matched: {pattern}")

    return paths


def write_new_file(path: str, content: str) -> int:
    """Write UTF-8 text to a new file and return the byte length."""
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)

    data = content.encode("utf-8")
    target.write_bytes(data)

    return len(data)


def write_file(path: str, content: str) -> int:
    """Write UTF-8 text to a file and return the byte length."""
    target = Path(path)

    if target.exists() and not target.is_file():
        raise ValueError(f"not a file: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)

    data = content.encode("utf-8")
    target.write_bytes(data)

    return len(data)


def ensure_new_file(path: str) -> None:
    """Ensure that a file path does not already exist."""
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")
