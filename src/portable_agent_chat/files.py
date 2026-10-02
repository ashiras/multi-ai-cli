"""File utility helpers for reading and writing UTF-8 text files."""

from pathlib import Path


def read_file(path: str) -> str:
    """Read and return the UTF-8 text content of a file.

    Args:
        path: Path to the file to read.

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the path is not a regular file.
    """
    target = Path(path)

    if not target.exists():
        raise FileNotFoundError(f"file not found: {path}")

    if not target.is_file():
        raise ValueError(f"not a file: {path}")

    return target.read_text(encoding="utf-8")


def write_new_file(path: str, content: str) -> int:
    """Write UTF-8 text to a new file and return the byte length.

    The file must not already exist.

    Args:
        path: Destination file path.
        content: Text content to write.

    Returns:
        The number of bytes written.

    Raises:
        FileExistsError: If the destination file already exists.
    """
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)

    data = content.encode("utf-8")
    target.write_bytes(data)

    return len(data)


def ensure_new_file(path: str) -> None:
    """Ensure that a file path does not already exist.

    Args:
        path: Path to validate.

    Raises:
        FileExistsError: If the path already exists.
    """
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")
