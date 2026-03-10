"""
Parsing utilities for Multi-AI CLI.

Handles CLI argument parsing, prompt building, and @sequence step parsing.
"""

import re
import shlex
from dataclasses import dataclass, field

from .adapters.shell.models import ParsedShInput  # noqa: F401 — re-export
from .config import config
from .utils import secure_resolve_path

WRITE_MODE_RAW = "raw"
WRITE_MODE_CODE = "code"

# Non-agent commands (adapters, utilities)
BUILTIN_COMMANDS = {
    "sh",
    "scrub",
    "flush",
    "efficient",
    "figma.pull",
    "figma.push",
    "github.repo",
    "github.tree",
    "github.file",
    "github.issue",
    "github.issues",
}


def get_valid_commands() -> set[str]:
    """
    Returns the set of all currently valid command names.
    Agent keys + built-in commands.

    Returns:
        set[str]: Set of all valid command names.
    """
    from .registry import agent_registry

    return set(agent_registry.keys()) | BUILTIN_COMMANDS


@dataclass
class ParsedInput:
    """
    Structured result of CLI input parsing.

    Attributes:
        a1 (str): Context / title text (bare words, no flags).
        message (str): Text from -m flags (concatenated).
        read_files (list[str]): List of filenames from -r flags.
        write_file (str | None): Output filename from -w / -w:code / -w:raw.
        write_mode (str): "raw" or "code".
        use_editor (bool): Whether -e / --edit was used.
    """

    a1: str = ""
    message: str = ""
    read_files: list[str] = field(default_factory=list)
    write_file: str | None = None
    write_mode: str = WRITE_MODE_RAW
    use_editor: bool = False

    def __post_init__(self) -> None:
        """Initializes read_files to an empty list if None."""
        if self.read_files is None:
            self.read_files = []


def _parse_write_flag(token: str) -> tuple[str | None, bool]:
    """
    Parses write flag variants and returns (mode, is_write_flag).

    Supported:
      - ``-w``, ``--write``           → raw
      - ``-w:raw``, ``--write:raw``   → raw
      - ``-w:code``, ``--write:code`` → code

    Args:
        token (str): The token to parse.

    Returns:
        tuple[str | None, bool]: A tuple containing the write mode and a
            flag indicating if it is a write flag.
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
    Parses command-line tokens into a structured ``ParsedInput`` object.

    Supports:
      - ``-r`` / ``--read`` <file> (repeatable)
      - ``-w`` / ``--write`` <file> [:raw|:code]
      - ``-m`` / ``--message`` <text> (repeatable)
      - ``-e`` / ``--edit``
      - Bare tokens → a1 (context/title)

    Args:
        parts (list[str]): List of command-line tokens.

    Returns:
        ParsedInput | None: A ``ParsedInput`` object if parsing succeeds,
            or ``None`` if it fails.
    """
    parsed = ParsedInput()
    indices_to_skip = {0}

    i = 1
    while i < len(parts):
        token = parts[i]

        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            parsed.read_files.append(parts[i + 1])
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

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

        if token in ("-e", "--edit"):
            parsed.use_editor = True
            indices_to_skip.add(i)
            i += 1
            continue

        i += 1

    a1_tokens = [parts[j] for j in range(len(parts)) if j not in indices_to_skip]
    parsed.a1 = " ".join(a1_tokens)

    return parsed


def build_ai_prompt(parsed: ParsedInput, editor_content: str | None = None) -> str:
    """
    Assembles the final prompt from different sources in fixed priority order.

    The priority order is as follows:

      1. a1 (bare context/title)
      2. message (-m flags)
      3. editor_content (from -e/--edit)
      4. contents of files from -r flags.

    Args:
        parsed (ParsedInput): The parsed input object containing relevant data.
        editor_content (str | None): The content from the editor, if provided.

    Returns:
        str: The assembled prompt.

    Raises:
        RuntimeError: If reading any file specified by ``-r`` fails.
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
    Splits editor content into sequential steps using ``->`` delimiter,
    while respecting quoted strings and escapes.

    Args:
        text (str): The text content to split into steps.

    Returns:
        list[str]: A list of split steps.
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
    Splits parallel tasks using ``||`` while respecting quotes and escapes.

    Args:
        text (str): The text content to split into parallel tasks.

    Returns:
        list[str]: A list of split parallel tasks.
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
    Normalizes raw step text by removing comments, stripping whitespace,
    and collapsing consecutive spaces.

    Args:
        step_text (str): The raw text of the step to normalize.

    Returns:
        str: The normalized step text.
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
    Checks if normalized text is a parallel block wrapped in ``[`` ... ``]``.

    Args:
        normalized_text (str): The normalized text to check.

    Returns:
        tuple[bool, str]: A tuple where the first element indicates if it
            is a parallel block and the second element is the inner text.
    """
    stripped = normalized_text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return True, stripped[1:-1].strip()
    return False, stripped


def parse_sequence_steps(editor_content: str) -> list[list[list[str]]] | None:
    """
    Parses full editor content into a nested list of tokenized commands.

    Args:
        editor_content (str): The raw editor content defining the sequence.

    Returns:
        list[list[list[str]]] | None: An outer list of sequential steps,
            each containing middle lists of parallel tasks, and inner lists
            of tokens, or ``None`` if parsing/validation fails.
    """
    raw_steps = smart_split_steps(editor_content)

    parsed_steps = []
    global_step_idx = 0

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
                valid = get_valid_commands()
                if cmd_key not in valid:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Unknown command '{tokens[0]}'"
                    )
                    print(f"    Available: {', '.join('@' + c for c in sorted(valid))}")
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
            valid = get_valid_commands()
            if cmd_key not in valid:
                print(f"[!] Step {global_step_idx}: Unknown command '{tokens[0]}'")
                print(f"    Available: {', '.join('@' + c for c in sorted(valid))}")
                return None

            if not tokens[0].startswith("@"):
                tokens[0] = "@" + tokens[0]

            parsed_steps.append([tokens])

    return parsed_steps


def _parse_sh_input(parts: list[str]) -> ParsedShInput | None:
    """
    Parses @sh command tokens into ``ParsedShInput``.

    Syntax: ``@sh ["command"] [-r file] [-w output] [--shell]``

    Args:
        parts (list[str]): The list of command tokens.

    Returns:
        ParsedShInput | None: A ``ParsedShInput`` object if parsing
            succeeds, or ``None`` if it fails.
    """
    parsed = ParsedShInput()
    bare_tokens = []

    i = 1
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
