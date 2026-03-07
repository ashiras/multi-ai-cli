"""
Parsing utilities for Multi-AI CLI.
Handles CLI argument parsing, prompt building, and @sequence step parsing.
"""

import re
import shlex
from dataclasses import dataclass

from .config import config
from .utils import secure_resolve_path

WRITE_MODE_RAW = "raw"
WRITE_MODE_CODE = "code"


@dataclass
class ParsedInput:
    """
    Structured result of CLI input parsing.

    Attributes:
        a1: Context / title text (bare words, no flags)
        message: Text from -m flags (concatenated)
        read_files: List of filenames from -r flags
        write_file: Output filename from -w / -w:code / -w:raw
        write_mode: "raw" or "code"
        use_editor: Whether -e / --edit was used
    """

    a1: str = ""
    message: str = ""
    read_files: list[str] = None
    write_file: str | None = None
    write_mode: str = WRITE_MODE_RAW
    use_editor: bool = False

    def __post_init__(self):
        if self.read_files is None:
            self.read_files = []


@dataclass
class ParsedShInput:
    """
    Structured result of @sh command parsing.

    Attributes:
        command: Raw command string (direct execution)
        run_file: Filename to execute (-r flag)
        write_file: Output artifact filename (-w flag)
        use_shell: Whether --shell was specified
    """

    command: str | None = None
    run_file: str | None = None
    write_file: str | None = None
    use_shell: bool = False


def _parse_write_flag(token: str) -> tuple[str | None, bool]:
    """
    Parse write flag variants and return (mode, is_write_flag).

    Supported:
    -w, --write          → raw
    -w:raw, --write:raw  → raw
    -w:code, --write:code → code
    """
    pattern = r"^(?:-w|--write)(?::(\w+))?$"
    m = re.match(pattern, token)
    if not m:
        return None, False

    modifier = m.group(1)

    if modifier is None or modifier == "raw":
        return WRITE_MODE_RAW, True
    elif modifier == "code":
        return WRITE_MODE_CODE, True
    else:
        print(f"[!] Unknown write modifier ':{modifier}'. Valid: :raw, :code")
        return None, False


def parse_cli_input(parts: list[str]) -> ParsedInput | None:
    """
    Parse command-line tokens into a structured ParsedInput object.

    Supports:
    -r / --read <file> (repeatable)
    -w / --write <file> [:raw|:code]
    -m / --message <text> (repeatable)
    -e / --edit
    Bare tokens → a1 (context/title)

    Returns None if parsing fails (error already printed).
    """
    parsed = ParsedInput()
    indices_to_skip = {0}  # Skip command itself (e.g. @gemini)

    i = 1
    while i < len(parts):
        token = parts[i]

        # -r / --read (repeatable)
        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            parsed.read_files.append(parts[i + 1])
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # -w / --write [:raw|:code]
        write_mode, is_write = _parse_write_flag(token)
        if is_write:
            if write_mode is None:
                return None
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            if parsed.write_file is not None:
                print("[!] Warning: write flag specified multiple times. Overwriting.")
            parsed.write_file = parts[i + 1]
            parsed.write_mode = write_mode
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # -m / --message (repeatable)
        if token in ("-m", "--message"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a text argument.")
                return None
            msg_val = parts[i + 1]
            if parsed.message:
                parsed.message += " " + msg_val
            else:
                parsed.message = msg_val
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # -e / --edit
        if token in ("-e", "--edit"):
            parsed.use_editor = True
            indices_to_skip.add(i)
            i += 1
            continue

        # Bare token → part of a1
        i += 1

    # Collect remaining tokens as a1 (context)
    a1_tokens = [parts[j] for j in range(len(parts)) if j not in indices_to_skip]
    parsed.a1 = " ".join(a1_tokens)

    return parsed


def build_ai_prompt(parsed: ParsedInput, editor_content: str | None = None) -> str:
    """
    Assemble the final prompt from different sources in fixed priority order:
      1. a1 (bare context/title)
      2. message (-m flags)
      3. editor_content (from -e/--edit)
      4. contents of files from -r flags

    Raises AIError if file reading fails.
    """
    sections = []

    if parsed.a1.strip():
        sections.append(parsed.a1.strip())

    if parsed.message.strip():
        sections.append(parsed.message.strip())

    if editor_content and editor_content.strip():
        sections.append(editor_content.strip())

    if parsed.read_files:
        file_sections = []
        for filename in parsed.read_files:
            try:
                filepath = secure_resolve_path(
                    filename,
                    "data",
                    config=config,
                )
                with open(filepath, encoding="utf-8") as f:
                    file_content = f.read()
                file_sections.append(
                    f"--- [File: {filename}] ---\n"
                    f"{file_content}\n"
                    f"--- [End of File: {filename}] ---"
                )
            except Exception as e:
                raise RuntimeError(f"Error reading input file '{filename}': {e}")

        if file_sections:
            sections.append("\n\n".join(file_sections))

    return "\n\n".join(sections)


def smart_split_steps(text: str) -> list[str]:
    """
    Split editor content into sequential steps using '->' delimiter,
    while respecting quoted strings and escapes.
    """
    steps = []
    current = []
    in_quote = None
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch == "\\" and i + 1 < length:
            current.append(ch)
            current.append(text[i + 1])
            i += 2
            continue

        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
            i += 1
            continue

        if in_quote is None and ch == "-" and i + 1 < length and text[i + 1] == ">":
            steps.append("".join(current).strip())
            current = []
            i += 2
            continue

        current.append(ch)
        i += 1

    if current:
        steps.append("".join(current).strip())

    return [s for s in steps if s]


def smart_split_parallel(text: str) -> list[str]:
    """
    Split parallel tasks using '||' while respecting quotes and escapes.
    """
    segments = []
    current = []
    in_quote = None
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch == "\\" and i + 1 < length:
            current.append(ch)
            current.append(text[i + 1])
            i += 2
            continue

        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
            i += 1
            continue

        if in_quote is None and ch == "|" and i + 1 < length and text[i + 1] == "|":
            segments.append("".join(current).strip())
            current = []
            i += 2
            continue

        current.append(ch)
        i += 1

    if current:
        segments.append("".join(current).strip())

    return [s for s in segments if s]


def normalize_step(step_text: str) -> str:
    """
    Normalize raw step text: remove comments, strip whitespace, collapse spaces.
    """
    lines = step_text.splitlines()
    filtered = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        filtered.append(stripped)

    normalized = " ".join(filtered)
    while "  " in normalized:
        normalized = normalized.replace("  ", " ")
    return normalized.strip()


def detect_parallel_block(normalized_text: str) -> tuple[bool, str]:
    """
    Check if normalized text is a parallel block wrapped in [ ... ].
    Returns (is_parallel, inner_text)
    """
    stripped = normalized_text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return True, stripped[1:-1].strip()
    return False, stripped


def parse_sequence_steps(editor_content: str) -> list[list[list[str]]] | None:
    """
    Parse full editor content into nested list of tokenized commands.

    Returns:
        list[list[list[str]]]   # outer: sequential steps, middle: parallel tasks, inner: tokens
        or None if parsing/validation fails
    """
    raw_steps = smart_split_steps(editor_content)

    parsed_steps = []
    global_step_idx = 0

    VALID_COMMANDS = {
        "gemini",
        "gpt",
        "claude",
        "grok",
        "local",
        "sh",
        "scrub",
        "flush",
        "efficient",
    }

    for raw in raw_steps:
        normalized = normalize_step(raw)
        if not normalized:
            continue

        global_step_idx += 1

        is_parallel, inner_text = detect_parallel_block(normalized)

        if is_parallel:
            parallel_segments = smart_split_parallel(inner_text)
            parallel_tasks = []

            for seg_idx, segment in enumerate(parallel_segments, 1):
                seg_normalized = normalize_step(segment)
                if not seg_normalized:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Empty task."
                    )
                    return None

                try:
                    tokens = shlex.split(seg_normalized)
                except ValueError as e:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Parse error: {e}"
                    )
                    return None

                if not tokens:
                    continue

                cmd_key = tokens[0].lower().replace("@", "")
                if cmd_key not in VALID_COMMANDS:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Unknown command '{tokens[0]}'"
                    )
                    print(
                        f"    Available: {', '.join('@' + c for c in sorted(VALID_COMMANDS))}"
                    )
                    return None

                if not tokens[0].startswith("@"):
                    tokens[0] = "@" + tokens[0]

                parallel_tasks.append(tokens)

            if not parallel_tasks:
                print(f"[!] Step {global_step_idx}: No valid tasks in parallel block.")
                return None

            parsed_steps.append(parallel_tasks)

        else:
            try:
                tokens = shlex.split(normalized)
            except ValueError as e:
                print(f"[!] Step {global_step_idx}: Parse error: {e}")
                return None

            if not tokens:
                continue

            cmd_key = tokens[0].lower().replace("@", "")
            if cmd_key not in VALID_COMMANDS:
                print(f"[!] Step {global_step_idx}: Unknown command '{tokens[0]}'")
                print(
                    f"    Available: {', '.join('@' + c for c in sorted(VALID_COMMANDS))}"
                )
                return None

            if not tokens[0].startswith("@"):
                tokens[0] = "@" + tokens[0]

            parsed_steps.append([tokens])

    return parsed_steps


def _parse_sh_input(parts: list[str]) -> ParsedShInput | None:
    """
    Parse @sh command tokens into ParsedShInput.

    Syntax: @sh ["command"] [-r file] [-w output] [--shell]
    """
    parsed = ParsedShInput()
    bare_tokens = []

    i = 1  # Skip '@sh'
    while i < len(parts):
        token = parts[i]

        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None
            if parsed.run_file is not None:
                print("[!] @sh: -r specified more than once.")
            parsed.run_file = parts[i + 1]
            i += 2
            continue

        if token in ("-w", "--write"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None
            if parsed.write_file is not None:
                print("[!] @sh: -w specified more than once.")
            parsed.write_file = parts[i + 1]
            i += 2
            continue

        if token == "--shell":
            parsed.use_shell = True
            i += 1
            continue

        bare_tokens.append(token)
        i += 1

    if bare_tokens:
        parsed.command = " ".join(bare_tokens)

    if not parsed.command and not parsed.run_file:
        print("[!] @sh: No command or file specified.")
        return None

    return parsed
