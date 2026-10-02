from pathlib import Path


def read_file(path: str) -> str:
    target = Path(path)

    if not target.exists():
        raise FileNotFoundError(f"file not found: {path}")

    if not target.is_file():
        raise ValueError(f"not a file: {path}")

    return target.read_text(encoding="utf-8")


def write_new_file(path: str, content: str) -> int:
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")

    target.parent.mkdir(parents=True, exist_ok=True)

    data = content.encode("utf-8")
    target.write_bytes(data)

    return len(data)

def ensure_new_file(path: str) -> None:
    target = Path(path)

    if target.exists():
        raise FileExistsError(f"file already exists: {path}")