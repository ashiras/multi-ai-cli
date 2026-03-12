"""
Filter mode runner for Multi-AI CLI.

Provides stateless Unix-style stdin -> AI -> stdout usage.
Reads from stdin, sends a single request to one agent, and writes
the result to stdout. All diagnostic output goes to stderr.
"""

import sys
from dataclasses import dataclass, field

from .config import agent_engines, logger
from .engines import AIError
from .parsers import BUILTIN_COMMANDS, load_reference_sections

# Flags and tokens that are explicitly rejected in filter mode
_REJECTED_FLAGS = {"-w", "--write", "-e", "--edit"}
_REJECTED_TOKENS = {"->", "||"}

_FILTER_USAGE = '    Usage: <stdin> | multi-ai @agent [-m "instruction"] [-r file ...]'
_FILTER_HINT = "    Hint: run `multi-ai` in a terminal for interactive mode."


@dataclass
class ParsedFilterInput:
    """
    Structured result of filter-mode argument parsing.

    Attributes:
        agent: The agent key (without '@' prefix).
        message: Instruction text from -m flag.
        read_files: List of reference filenames from -r flags.
    """

    agent: str = ""
    message: str = ""
    read_files: list[str] = field(default_factory=list)


def _eprint(*args: object) -> None:
    """Print to stderr for diagnostic output in filter mode."""
    print(*args, file=sys.stderr)


def parse_filter_cli_input(argv: list[str]) -> ParsedFilterInput | None:
    """
    Parses filter-mode command-line arguments.

    Accepts exactly one @<agent>, optional -m <text>, and repeatable -r <file>.
    Rejects -w, -e, ||, ->, multiple command tokens, bare words, and any
    non-agent @ command (e.g. @sh, @sequence, @figma.*).

    The first @-prefixed token is treated as the primary command target.
    Any subsequent @-prefixed tokens are rejected individually with a
    specific error message.

    Args:
        argv: Command-line arguments (sys.argv[1:]).

    Returns:
        ParsedFilterInput on success, or None on validation failure.
        Errors are printed to stderr.
    """
    if not argv:
        _eprint("[!] Filter mode requires at least one @agent argument.")
        _eprint(_FILTER_USAGE)
        _eprint(_FILTER_HINT)
        return None

    # Reject pipeline / parallel operator tokens early
    for token in argv:
        if token in _REJECTED_TOKENS:
            _eprint(f"[!] Filter mode does not support '{token}' syntax.")
            return None

    # Reject interactive-only flags early
    for token in argv:
        if token in _REJECTED_FLAGS:
            _eprint(f"[!] Filter mode does not support the '{token}' flag.")
            return None

    # --- Locate the primary command target (first @-prefixed token) ---
    primary_token: str | None = None
    primary_index: int = -1
    for idx, token in enumerate(argv):
        if token.startswith("@"):
            primary_token = token
            primary_index = idx
            break

    if primary_token is None:
        _eprint("[!] Filter mode requires at least one @agent argument.")
        _eprint(_FILTER_USAGE)
        _eprint(_FILTER_HINT)
        return None

    agent_key = primary_token[1:].lower()

    # Reject non-agent built-in commands (uses shared BUILTIN_COMMANDS)
    if agent_key in BUILTIN_COMMANDS:
        _eprint(
            f"[!] Filter mode does not support command '{primary_token}'. "
            f"Only AI agents are allowed."
        )
        return None

    # Validate that this agent actually exists (early check for better errors)
    if agent_key not in agent_engines:
        _eprint(f"[!] Unknown agent '{primary_token}'.")
        available = ", ".join("@" + k for k in sorted(agent_engines.keys()))
        _eprint(f"    Available agents: {available}")
        return None

    parsed = ParsedFilterInput(agent=agent_key)

    # --- Parse remaining tokens, skipping the primary command token ---
    i = 0
    while i < len(argv):
        # Skip the primary command token (already consumed above)
        if i == primary_index:
            i += 1
            continue

        token = argv[i]

        # Reject any additional @-prefixed tokens
        if token.startswith("@"):
            _eprint(
                f"[!] Unexpected extra command token '{token}' in filter mode. "
                f"Filter mode only supports one AI agent command."
            )
            return None

        # -r / --read (repeatable, requires value)
        if token in ("-r", "--read"):
            if i + 1 >= len(argv):
                _eprint(f"[!] Flag '{token}' requires a filename argument.")
                return None
            next_val = argv[i + 1]
            if next_val.startswith("-") or next_val.startswith("@"):
                _eprint(
                    f"[!] Flag '{token}' requires a filename argument, "
                    f"got '{next_val}'."
                )
                return None
            parsed.read_files.append(next_val)
            i += 2
            continue

        # -m / --message (repeatable, requires value)
        if token in ("-m", "--message"):
            if i + 1 >= len(argv):
                _eprint(f"[!] Flag '{token}' requires a text argument.")
                return None
            next_val = argv[i + 1]
            if next_val.startswith("-") or next_val.startswith("@"):
                _eprint(
                    f"[!] Flag '{token}' requires a text argument, got '{next_val}'."
                )
                return None
            if parsed.message:
                parsed.message += " " + next_val
            else:
                parsed.message = next_val
            i += 2
            continue

        # Unknown flag
        if token.startswith("-"):
            _eprint(f"[!] Filter mode does not support flag '{token}'.")
            _eprint("    Supported flags: -m/--message, -r/--read")
            return None

        # Bare tokens are not accepted in filter mode
        _eprint(f"[!] Unexpected argument '{token}' in filter mode.")
        _eprint("    Use -m for instruction text.")
        return None

    return parsed


def build_filter_prompt(
    stdin_text: str,
    message: str = "",
    read_files: list[str] | None = None,
) -> str:
    """
    Builds a prompt for filter mode with explicit semantic sections.

    The prompt structure is:
      [Instruction]    - from -m flag (if provided)
      [Primary Input]  - from stdin
      [Reference Files] - from -r flags (if provided)

    Args:
        stdin_text: The primary input read from stdin.
        message: Optional instruction text from -m flag.
        read_files: Optional list of reference filenames.

    Returns:
        The assembled prompt string.

    Raises:
        RuntimeError: If reading any reference file fails.
    """
    sections: list[str] = []

    if message.strip():
        sections.append(f"[Instruction]\n{message.strip()}")

    if stdin_text.strip():
        sections.append(f"[Primary Input]\n{stdin_text.strip()}")

    if read_files:
        ref_sections = load_reference_sections(read_files)
        if ref_sections:
            sections.append("[Reference Files]\n" + "\n\n".join(ref_sections))

    return "\n\n".join(sections)


def run_filter_mode(argv: list[str]) -> int:
    """
    Entry point for filter mode execution.

    Reads stdin, resolves one agent, builds a prompt, executes a single
    stateless request, and writes the result to stdout.

    Input contract:
      Filter mode accepts any combination that provides at least one
      input source:
        - stdin only
        - stdin + -m
        - stdin + -r
        - -m only
        - -r only
        - -m + -r
      But rejects the case where all three are empty/absent.

    Args:
        argv: Command-line arguments (sys.argv[1:]).

    Returns:
        Exit code: 0 for success, 1 for runtime error, 2 for usage/validation error.
    """
    # Parse and validate filter-mode arguments (exits with 2 on failure)
    parsed = parse_filter_cli_input(argv)
    if parsed is None:
        return 2

    # Agent existence is already validated in parse_filter_cli_input(),
    # but retrieve the engine instance here.
    engine = agent_engines.get(parsed.agent)
    if engine is None:
        # Defensive guard; should not normally be reached.
        _eprint(f"[!] Unknown agent '@{parsed.agent}'.")
        return 2

    # Read stdin
    try:
        stdin_text = sys.stdin.read()
    except Exception as e:
        _eprint(f"[!] Error reading stdin: {e}")
        logger.error(f"Filter mode: stdin read error: {e}")
        return 1

    # Reject completely empty input (no stdin, no -m, no -r)
    if not stdin_text.strip() and not parsed.message and not parsed.read_files:
        _eprint("[!] No input provided. Stdin is empty and no -m or -r specified.")
        return 2

    # Build prompt from stdin + flags
    try:
        prompt = build_filter_prompt(
            stdin_text=stdin_text,
            message=parsed.message,
            read_files=parsed.read_files,
        )
    except RuntimeError as e:
        _eprint(f"[!] {e}")
        logger.error(f"Filter mode: reference file error: {e}")
        return 1

    if not prompt.strip():
        _eprint("[!] No prompt content to send.")
        return 2

    logger.info(f"Filter mode: @{parsed.agent} prompt ({len(prompt)} chars)")

    # Execute AI request with progress output suppressed.
    # Temporary execution-scoped state on the shared engine instance,
    # used to suppress interactive progress output in filter mode.
    # This may later be replaced by per-call execution options
    # (e.g. engine.call(prompt, quiet=True)).
    _set_filter_mode(engine, True)
    try:
        result = engine.call(prompt)
    except AIError as e:
        _eprint(f"[!] AI engine error: {e}")
        logger.error(f"Filter mode: AI engine error: {e}")
        return 1
    except Exception as e:
        _eprint(f"[!] Unexpected execution error: {e}")
        logger.error(f"Filter mode: unexpected error: {e}")
        return 1
    finally:
        _set_filter_mode(engine, False)

    # Write result to stdout only
    sys.stdout.write(result)

    # Ensure output ends with newline for proper Unix behavior
    if result and not result.endswith("\n"):
        sys.stdout.write("\n")

    logger.info(f"Filter mode: completed successfully ({len(result)} chars)")
    return 0


def _set_filter_mode(engine: object, enabled: bool) -> None:
    """
    Sets or clears the filter_mode flag on an engine instance.

    This is a temporary execution-scoped flag that suppresses interactive
    progress/status output to stdout during auto-continue behavior.
    It does not change any other engine behavior.

    This approach may later be replaced by per-call execution options.

    Args:
        engine: The AI engine instance.
        enabled: Whether to suppress progress output.
    """
    engine.filter_mode = enabled  # type: ignore[attr-defined]
