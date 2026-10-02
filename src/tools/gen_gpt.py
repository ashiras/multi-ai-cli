"""Tool to extract and write files from ChatGPT output."""

import argparse
import re
from pathlib import Path


def extract_files(text: str) -> list[tuple[str, str]]:
    r"""Extract files from ChatGPT output.

    Expected format: ```python\n# path/to/file.py\n(code)\n```
    Also supports variations like "# ===== path/to/file.py ====="
    """
    files = []

    pattern = r"```(?:\w+)?\n#\s*([^\n]+)\n([\s\S]*?)\n```"

    for match in re.finditer(pattern, text):
        raw_path = match.group(1).strip()
        # ===== や === などの装飾を除去してパスだけを抽出
        filepath = re.sub(r'^[=\s#]+|[=\s#]+$', '', raw_path).strip()
        content = match.group(2)
        if filepath:
            files.append((filepath, content))

    return files


def write_files(root_dir: Path, files: list[tuple[str, str]]) -> None:
    """Write extracted files to the specified directory."""
    root_dir.mkdir(parents=True, exist_ok=True)
    for filepath, content in files:
        full_path = root_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        print(f"Created: {full_path}")


def main() -> None:
    """Parse command-line arguments, extract files, and write them out."""
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("--out", default="./generated")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_root = Path(args.out)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return

    text = input_path.read_text(encoding="utf-8")
    extracted = extract_files(text)

    if not extracted:
        print("No files were extracted.")
        return

    write_files(output_root, extracted)
    print(f"\nDone: {len(extracted)} file(s) created.")


if __name__ == "__main__":
    main()
