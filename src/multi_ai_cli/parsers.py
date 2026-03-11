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
    "pause",
    "figma.pull",
    "figma.push",
    "github.repo",
    "github.tree",
    "github.file",
    "github.issue",
    "github.issues",
}

# Known flags for @agent commands and whether they require a value
_AGENT_FLAGS: dict[str, bool] = {
    "-r": True,
    "--read": True,
    "-w": True,
    "--write": True,
    "-m": True,
    "--message": True,
    "-e": False,
    "--edit": False,
}

# Write-flag pattern: -w, --write, -w:raw, --write:raw, -w:code, --write:code
_WRITE_FLAG_PATTERN = re.compile(r"^(?:-w|--write)(?::(\w+))?$")

# Pattern that identifies tokens that look like flags (start with -)
_FLAG_LIKE_PATTERN = re.compile(r"^-")


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


def _is_known_flag(token: str) -> bool:
    """
    Checks if the token is a recognized @agent flag or a write-flag family token.
    """
    if token in _AGENT_FLAGS:
        return True

    _, is_write, _ = _parse_write_flag(token)
    return is_write


def _is_unknown_flag(token: str) -> bool:
    """
    Checks if the token looks like a flag (starts with -) but is not recognized.

    Args:
        token (str): The token to check.

    Returns:
        bool: True if the token appears to be an unknown flag.
    """
    if not _FLAG_LIKE_PATTERN.match(token):
        return False
    return not _is_known_flag(token)


def _parse_write_flag(token: str) -> tuple[str | None, bool, str | None]:
    """
    Parses write flag variants.

    Returns:
        tuple[str | None, bool, str | None]:
            (write_mode, is_write_flag, error_message)

        - If token is not a write flag:
            (None, False, None)
        - If token is a valid write flag:
            ("raw" | "code", True, None)
        - If token is a write flag with an invalid modifier:
            (None, True, "...")
    """
    if not (token.startswith("-w") or token.startswith("--write")):
        return None, False, None

    m = _WRITE_FLAG_PATTERN.match(token)
    if not m:
        return (
            None,
            True,
            f"[!] Unknown write modifier in '{token}'. Valid: :raw, :code",
        )

    modifier = m.group(1)

    if modifier is None or modifier == "raw":
        return WRITE_MODE_RAW, True, None
    if modifier == "code":
        return WRITE_MODE_CODE, True, None

    return None, True, f"[!] Unknown write modifier ':{modifier}'. Valid: :raw, :code"


def _tokenize_agent_input(parts: list[str]) -> list[str]:
    """
    Extracts the token list for agent parsing, skipping the command token at index 0.

    Args:
        parts (list[str]): Full command parts including the @agent token.

    Returns:
        list[str]: Tokens after the command token.
    """
    return parts[1:] if len(parts) > 1 else []


def _parse_agent_flags(tokens: list[str]) -> ParsedInput | None:
    """
    Parses agent command tokens into flags and bare prompt words.

    This implements a strict two-pass approach:
      1. Identify and consume known flags and their values.
      2. Collect remaining tokens as bare prompt text (a1).
      3. Reject any unknown flag-like tokens.

    Args:
        tokens (list[str]): Tokens after the @agent command name.

    Returns:
        ParsedInput | None: Parsed result, or None on validation failure.
    """
    parsed = ParsedInput()
    bare_tokens: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Check for unknown flags early
        if _is_unknown_flag(token):
            print(f"[!] Unknown flag: '{token}'")
            print(
                "[*] Valid flags: -r/--read, -w/--write, -w:raw, -w:code, "
                "-m/--message, -e/--edit"
            )
            return None

        # -r / --read (repeatable, requires value)
        if token in ("-r", "--read"):
            if i + 1 >= len(tokens):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            next_val = tokens[i + 1]
            if _is_known_flag(next_val) or _is_unknown_flag(next_val):
                print(
                    f"[!] Flag '{token}' requires a filename argument, got '{next_val}'."
                )
                return None
            parsed.read_files.append(next_val)
            i += 2
            continue

        # -w / --write / -w:raw / -w:code (requires value)
        write_mode, is_write, write_error = _parse_write_flag(token)
        if is_write:
            if write_error is not None:
                print(write_error)
                return None

            if write_mode is None:
                print(f"[!] Internal parser error for write flag '{token}'.")
                return None

            if i + 1 >= len(tokens):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None

            next_val = tokens[i + 1]
            if _is_known_flag(next_val) or _is_unknown_flag(next_val):
                print(
                    f"[!] Flag '{token}' requires a filename argument, got '{next_val}'."
                )
                return None

            if parsed.write_file is not None:
                print("[!] Warning: write flag specified multiple times. Overwriting.")

            parsed.write_file = next_val
            parsed.write_mode = write_mode
            i += 2
            continue

        # -m / --message (repeatable, requires value)
        if token in ("-m", "--message"):
            if i + 1 >= len(tokens):
                print(f"[!] Flag '{token}' requires a text argument.")
                return None
            next_val = tokens[i + 1]
            if _is_known_flag(next_val) or _is_unknown_flag(next_val):
                print(f"[!] Flag '{token}' requires a text argument, got '{next_val}'.")
                return None
            if parsed.message:
                parsed.message += " " + next_val
            else:
                parsed.message = next_val
            i += 2
            continue

        # -e / --edit (no value)
        if token in ("-e", "--edit"):
            parsed.use_editor = True
            i += 1
            continue

        # Bare token — collect as prompt text
        bare_tokens.append(token)
        i += 1

    parsed.a1 = " ".join(bare_tokens)
    return parsed


def _validate_parsed_input(parsed: ParsedInput) -> bool:
    """
    Performs final validation on the parsed agent input.

    Currently checks:
      - At least one prompt source exists (a1, message, editor, or read files).
        (Note: this is a soft check; the caller may add editor content later.)

    Args:
        parsed (ParsedInput): The parsed input to validate.

    Returns:
        bool: True if validation passes.
    """
    # Validation is intentionally light here because editor content (-e)
    # is not yet available at parse time. The handler checks for empty prompts.
    return True


def parse_cli_input(parts: list[str]) -> ParsedInput | None:
    """
    Parses command-line tokens into a structured ``ParsedInput`` object.

    Flow:
      1. Tokenize (skip @agent command at index 0)
      2. Parse flags and values
      3. Collect remaining bare tokens as prompt text
      4. Validate the final structure

    Supports:
      - ``-r`` / ``--read`` <file> (repeatable)
      - ``-w`` / ``--write`` <file> [:raw|:code]
      - ``-m`` / ``--message`` <text> (repeatable)
      - ``-e`` / ``--edit``
      - Bare tokens → a1 (context/title)

    Rejects:
      - Unknown flags (tokens starting with ``-`` that are not recognized)
      - Missing flag values

    Args:
        parts (list[str]): List of command-line tokens.

    Returns:
        ParsedInput | None: A ``ParsedInput`` object if parsing succeeds,
            or ``None`` if it fails.
    """
    tokens = _tokenize_agent_input(parts)
    parsed = _parse_agent_flags(tokens)

    if parsed is None:
        return None

    if not _validate_parsed_input(parsed):
        return None

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
