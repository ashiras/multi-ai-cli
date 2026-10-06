"""Extract code fences whose paths are listed in a prompt's File List.

Expected paths come from the ## File List section of a prompt file
(prompt_engineering.md). Each path is then searched for in the model output.
A fence is kept when that path appears immediately before it, on the first
non-empty line inside it, or immediately after it.

    ## File List
    src/problem/hello_world.py
    src/tests/test_hello_world.py

    # src/problem/hello_world.py
    ```python
    print("こんにちは世界")
    ```

    ```python
    # File: src/tests/test_hello_world.py
    def test_hello():
        ...
    ```

    ```python
    def test_hello():
        ...
    ```
    src/tests/test_hello_world.py

Heading marks, list marks, comment marks, and backticks around the path are
ignored. A label immediately before the fence wins. Otherwise the first
non-empty line inside is used, then the label immediately after. A label
used as the after-fence path is not reused for the next fence.

Without --prompt, the old File: marker scan is used.
"""

import argparse
import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^[ \t]*```([^`]*)[ \t]*$")
FILE_MARK_RE = re.compile(r"file\s*[:：]", re.IGNORECASE)
FILE_LIST_HEADING_RE = re.compile(r"^#{1,6}\s+File List\s*$", re.IGNORECASE)
HEADING_RE = re.compile(r"^#{1,6}\s+")


def canonical_filename(raw: str) -> str:
    """Normalize a declared path so bracketed and plain forms match."""
    name = raw.strip().strip("`").strip()
    while len(name) >= 2 and name.startswith("[") and name.endswith("]"):
        inner = name[1:-1].strip()
        if not inner or inner == name:
            break
        name = inner
    if name.startswith("./"):
        name = name[2:]
    return name.replace("\\", "/")


def safe_relative_path(raw: str) -> str | None:
    """Return a relative path that stays inside the output root, or None."""
    name = canonical_filename(raw)
    if not name or name.endswith("/"):
        return None
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return None
    parts = [part for part in name.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def strip_label_decorations(line: str) -> str:
    """Drop heading, list, comment, and emphasis marks around a label line."""
    text = line.strip()
    text = re.sub(r"^#{1,6}\s+", "", text)
    text = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", text)
    text = re.sub(r"^(?:#|//|--|;)\s*", "", text)
    text = text.strip().strip("*_")
    text = text.replace("\u00a0", " ")
    return text.strip()


def file_path_from_line(line: str) -> str | None:
    """Pull a path from a line when it contains a File: marker.

    Heading level, bullets, bold, and backticks are stripped first so that
    '## File: path', 'File: path', and '`File: path`' all match.
    """
    text = line.strip()
    if not text or text.startswith("```"):
        return None
    text = strip_label_decorations(text)
    match = FILE_MARK_RE.search(text)
    if match is None:
        return None
    raw = text[match.end() :].strip()
    raw = raw.strip("`*_\"'")
    raw = re.sub(r"\s+#.*$", "", raw).strip()
    raw = raw.strip("`*_\"'")
    if not raw or raw.lower() in {"filepath", "path", "file"}:
        return None
    return safe_relative_path(raw)


def parse_file_list(text: str) -> list[str]:
    """Return relative paths under the first ## File List section."""
    paths: list[str] = []
    seen: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if FILE_LIST_HEADING_RE.fullmatch(stripped):
            in_section = True
            continue
        if not in_section:
            continue
        if HEADING_RE.match(stripped):
            break
        if not stripped or stripped.startswith("```"):
            continue
        candidate = strip_label_decorations(stripped).strip("`*_\"'")
        candidate = re.sub(r"\s+#.*$", "", candidate).strip().strip("`*_\"'")
        path = safe_relative_path(candidate)
        if path and path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def listed_path_from_line(line: str, listed: list[str]) -> str | None:
    """Return a File List path when this line names it.

    - 完全パス一致を優先
    - 次に basename（ファイル名のみ）で一致し、**一意**であれば採用
    - ファイルパスを付けないケースでも対応できるようにする
    """
    text = line.strip()
    if not text or text.startswith("```"):
        return None

    marked = file_path_from_line(line)
    if marked is not None and marked in listed:
        return marked

    decorated = strip_label_decorations(text).replace("\\", "/")

    # 1. 完全パス一致（長いパスを優先）
    for path in sorted(listed, key=len, reverse=True):
        if re.search(rf"(?<![\w.-]){re.escape(path)}(?![\w.-])", decorated):
            return path

    # 2. ファイル名（basename）だけでマッチング（一意の場合のみ採用）
    basename_map = {}
    for path in listed:
        base = path.rsplit("/", 1)[-1]
        if re.search(rf"(?<![\w.-]){re.escape(base)}(?![\w.-])", decorated):
            basename_map.setdefault(base, []).append(path)

    # basename が一意に1つだけヒットした場合のみ返す
    single_matches = [paths[0] for paths in basename_map.values() if len(paths) == 1]
    if len(single_matches) == 1:
        return single_matches[0]

    return None


def fence_info_path(line: str, listed: list[str] | None) -> str | None:
    """Return a File List path when it is the opening fence info string."""
    match = FENCE_RE.fullmatch(line)
    if match is None or not listed:
        return None
    info = match.group(1).strip().strip("`")
    path = safe_relative_path(info)
    if path in listed:
        return path
    return None


def strip_leading_path(
    body: list[str], path: str, listed: list[str] | None
) -> list[str]:
    """Drop a leading path label so it is not written into the file."""
    for offset, line in enumerate(body):
        if not line.strip():
            continue
        labeled = (
            listed_path_from_line(line, listed) if listed else file_path_from_line(line)
        )
        plain = safe_relative_path(strip_label_decorations(line).strip("`*_\"'"))
        base = path.rsplit("/", 1)[-1]
        if labeled == path or plain in {path, base}:
            return body[:offset] + body[offset + 1 :]
        return body
    return body


def extract_files(text: str, listed: list[str] | None = None) -> list[tuple[str, str]]:
    lines = text.splitlines()
    files: list[tuple[str, str]] = []
    seen: set[str] = set()
    pending: str | None = None
    index = 0
    allow = set(listed) if listed else None

    while index < len(lines):
        line = lines[index]

        if FENCE_RE.fullmatch(line):
            body: list[str] = []
            fence_line = index
            index += 1
            while index < len(lines) and not FENCE_RE.fullmatch(lines[index]):
                body.append(lines[index])
                index += 1

            # pending が無ければ、直前の非空行をラベルとして確認
            candidate = pending
            if candidate is None:
                # フェンスの直前を逆方向に探す
                j = fence_line - 1
                while j >= 0 and not lines[j].strip():
                    j -= 1
                if j >= 0:
                    candidate = (
                        listed_path_from_line(lines[j], listed)
                        if listed else file_path_from_line(lines[j])
                    )

            path, body = label_from_body(candidate, body, listed)

            if path is None:
                path, index = label_after_fence(lines, index + 1, listed)
            else:
                index += 1

            if allow is not None and path not in allow:
                path = None

            if path:
                body = strip_leading_path(body, path, listed)

            if path and path not in seen and any(part.strip() for part in body):
                seen.add(path)
                files.append((path, "\n".join(body)))

            pending = None
            continue

        # 通常行の処理
        labeled = (
            listed_path_from_line(line, listed) if listed else file_path_from_line(line)
        )
        if labeled is not None:
            pending = labeled
        index += 1

    return files

def label_after_fence(
    lines: list[str],
    start: int,
    listed: list[str] | None,
) -> tuple[str | None, int]:
    """Return a path label before the next fence, and the index after it."""
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or FENCE_RE.fullmatch(lines[index]):
        return None, start
    labeled = (
        listed_path_from_line(lines[index], listed)
        if listed
        else file_path_from_line(lines[index])
    )
    if labeled is None:
        return None, start
    # A heading immediately before the next fence belongs to that fence.
    look = index + 1
    while look < len(lines) and not lines[look].strip():
        look += 1
    if look < len(lines) and FENCE_RE.fullmatch(lines[look]):
        return None, start
    return labeled, index + 1


def label_from_body(
    pending: str | None,
    body: list[str],
    listed: list[str] | None,
) -> tuple[str | None, list[str]]:
    """Use a leading path comment when the fence itself has no outside label."""
    if pending:
        return pending, body
    for offset, line in enumerate(body):
        if not line.strip():
            continue
        labeled = (
            listed_path_from_line(line, listed) if listed else file_path_from_line(line)
        )
        if labeled is None:
            return None, body
        rest = body[:offset] + body[offset + 1 :]
        return labeled, rest
    return None, body


def is_test_path(path: str) -> bool:
    """Treat tests/ directories and test_* / *_test filenames as tests."""
    parts = path.split("/")
    name = parts[-1]
    if "tests" in parts or "test" in parts[:-1]:
        return True
    stem = name.rsplit(".", 1)[0]
    return stem.startswith("test_") or stem.endswith("_test")


def output_relative(path: str, test: bool) -> str:
    """Drop the kind prefix so each file lands under the chosen root."""
    parts = path.split("/")
    if test and "tests" in parts:
        rest = parts[parts.index("tests") + 1 :]
        return "/".join(rest) if rest else parts[-1]
    if not test and parts[0] == "src":
        return "/".join(parts[1:])
    return path


def write_files(
    files: list[tuple[str, str]],
    output_root: Path | None,
    src_out: Path | None,
    test_out: Path | None,
) -> None:
    """Write extracted files, splitting tests when both destinations are set."""
    split = src_out is not None or test_out is not None
    for filepath, content in files:
        test = is_test_path(filepath)
        if split:
            root = (test_out if test else src_out) or output_root
            if root is None:
                print(f"Skipped (no output dir): {filepath}", file=sys.stderr)
                continue
            relative = output_relative(filepath, test)
        else:
            if output_root is None:
                print(f"Skipped (no output dir): {filepath}", file=sys.stderr)
                continue
            root = output_root
            relative = filepath
        root.mkdir(parents=True, exist_ok=True)
        full_path = (root / relative).resolve()
        root_resolved = root.resolve()
        if root_resolved not in full_path.parents and full_path != root_resolved:
            print(f"Skipped (outside output root): {filepath}", file=sys.stderr)
            continue
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if content and not content.endswith("\n"):
            content += "\n"
        full_path.write_text(content, encoding="utf-8")
        kind = "test" if test else "src"
        print(f"Created ({kind}): {full_path}")


def main() -> None:
    """Extract listed code fences and write them out."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract code fences named in a prompt's ## File List and write them."
        ),
    )
    parser.add_argument("input_file", help="Model output file (code.md)")
    parser.add_argument(
        "--prompt",
        metavar="PATH",
        help="prompt_engineering.md。## File List のパスだけを出力から拾う",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="単一の出力先。--src-out / --test-out が無いときの相対パスの根",
    )
    parser.add_argument(
        "--src-out",
        metavar="DIR",
        help="実装コードの出力先。tests 以外をここに書く",
    )
    parser.add_argument(
        "--test-out",
        metavar="DIR",
        help="テストコードの出力先。ファイル名 test_* / *_test、または tests/ をここに書く",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_root = Path(args.out) if args.out else None
    src_out = Path(args.src_out) if args.src_out else None
    test_out = Path(args.test_out) if args.test_out else None
    if output_root is None and src_out is None and test_out is None:
        output_root = Path("./generated")

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        raise SystemExit(1)

    listed: list[str] | None = None
    if args.prompt:
        prompt_path = Path(args.prompt)
        if not prompt_path.exists():
            print(f"Error: File not found: {prompt_path}", file=sys.stderr)
            raise SystemExit(1)
        listed = parse_file_list(prompt_path.read_text(encoding="utf-8"))
        if not listed:
            print(
                "No paths found under ## File List.\n"
                "prompt_engineering.md に ## File List と相対パスが必要です。",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print("File List:")
        for path in listed:
            print(f"  {path}")

    extracted = extract_files(input_path.read_text(encoding="utf-8"), listed)
    if not extracted:
        if listed:
            print(
                "No files were extracted.\n"
                "出力中のコードフェンス直前・先頭行・直後に、"
                "File List のパスが必要です。",
                file=sys.stderr,
            )
        else:
            print(
                "No files were extracted.\n"
                "コードフェンスの直前か直後に File: path/to/file.ext が必要です。\n"
                "見出しやバッククォートはあってもなくても構いません。\n"
                "File List 方式にするには --prompt prompt_engineering.md を付けてください。",
                file=sys.stderr,
            )
        raise SystemExit(1)

    write_files(extracted, output_root, src_out, test_out)
    if listed:
        missing = [
            path for path in listed if path not in {item[0] for item in extracted}
        ]
        if missing:
            print("\nMissing from output:", file=sys.stderr)
            for path in missing:
                print(f"  {path}", file=sys.stderr)
    print(f"\nDone: {len(extracted)} file(s) created.")


if __name__ == "__main__":
    main()
