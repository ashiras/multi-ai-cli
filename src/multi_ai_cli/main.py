"""
Main entry point for the Multi-AI CLI application.

This module handles the application's lifecycle, including configuration
loading, AI engine initialization, mode detection (interactive REPL vs
filter mode), and command dispatch.

Uses AgentSession for instance lifecycle management, ensuring that
each REPL session maintains independent agent state while sharing
immutable AgentDefinitions from the registry.
"""

import os
import shlex
import sys
from typing import TYPE_CHECKING

from . import __version__
from .config import is_log_enabled, legacy_sdk_map, logger, setup_config, setup_logger
from .handlers import dispatch_command
from .registry import agent_registry
from .utils import print_welcome_banner

if TYPE_CHECKING:
    from .session import AgentSession

# Valid values for the --mode flag
_VALID_MODES = {"repl", "filter"}

# ==============================================================================
# Workspace initialization
# ==============================================================================

_DEFAULT_INI_CONTENT = """\
[API_KEYS]
# API keys may also be provided via environment variables.
# Environment variables should override these values when present.
GEMINI_API_KEY =
OPENAI_API_KEY =
anthropic_api_key =
grok_api_key =

# ==============================================================================
# Runtime
# ==============================================================================
#
# Global application/runtime behavior.
# These values are independent of individual Agent definitions.
# ==============================================================================

[RUNTIME]

# Maximum number of conversation turns
# (user + assistant pairs) retained by each Agent instance.
max_history_turns = 30

# Auto-continue behavior for responses that hit an output limit.
auto_continue_max_rounds = 5
auto_continue_tail_chars = 1200

# ==============================================================================
# Agents
# ==============================================================================
#
# Agent names are logical aliases.
#
# The Agent name does NOT imply:
#
#   - Provider
#   - Local / Cloud
#   - Model
#   - Adapter
#
# Required:
#
#   adapter
#   server
#   engine
#
# Optional:
#
#   api_key_ref
#   role
#   max_output_tokens
#
# Currently supported adapter:
#
#   openai-compatible
#
# Example:
#
#   [AGENT.reviewer]
#   adapter = openai-compatible
#   server = https://api.openai.com/v1
#   engine = <model-name>
#   api_key_ref = openai_api_key
#   role = review
#   max_output_tokens = 8192
#
# Agent aliases may contain:
#
#   a-z
#   0-9
#   _
#   -
#
# ==============================================================================


# ------------------------------------------------------------------------------
# OpenAI
# ------------------------------------------------------------------------------

[AGENT.gpt]
adapter = openai-compatible
server = https://api.openai.com/v1
engine = gpt-5.4
api_key_ref = openai_api_key
max_output_tokens = 8192

# ==============================================================================
# Application Paths
# ==============================================================================

[Paths]

# Folder for prompt/persona assets used by commands such as @efficient.
work_efficient = prompts

# Blackboard directory for read/write artifacts (-r / -w).
work_data = work_data

# ==============================================================================
# Logging
# ==============================================================================

[logging]

enabled = true
log_dir = logs
base_filename = chat.log
max_bytes = 10485760
backup_count = 5
log_level = INFO
"""


_DEFAULT_GITIGNORE_ENTRIES = (
    "multi_ai_cli.ini",
    "work_data/",
    "logs/",
)


def _create_file_if_missing(path: str, content: str) -> None:
    """
    Create a file only when it does not already exist.

    Existing files are never overwritten.
    """
    if os.path.exists(path):
        print(f"  skip     {path} (already exists)")
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  created  {path}")


def _ensure_directory(path: str) -> None:
    """
    Ensure that a workspace directory exists.
    """
    if os.path.isdir(path):
        print(f"  skip     {path}/ (already exists)")
        return

    if os.path.exists(path):
        print(
            f"[!] Error: cannot create directory '{path}': "
            f"a file with that name already exists.",
            file=sys.stderr,
        )
        raise RuntimeError(f"Path conflict: {path}")

    os.makedirs(path)
    print(f"  created  {path}/")


def _update_gitignore() -> None:
    """
    Create or update .gitignore with Multi-AI local/runtime files.

    Existing .gitignore content is preserved.
    Missing Multi-AI entries are appended.
    """
    path = ".gitignore"

    if os.path.exists(path):
        if not os.path.isfile(path):
            raise RuntimeError("'.gitignore' exists but is not a file.")

        with open(path, encoding="utf-8") as f:
            current_content = f.read()

        existing_entries = {
            line.strip()
            for line in current_content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

        missing_entries = [
            entry
            for entry in _DEFAULT_GITIGNORE_ENTRIES
            if entry not in existing_entries
        ]

        if not missing_entries:
            print("  skip     .gitignore (already configured)")
            return

        with open(path, "a", encoding="utf-8") as f:
            if current_content and not current_content.endswith("\n"):
                f.write("\n")

            f.write("\n# Multi-AI local/runtime files\n")
            for entry in missing_entries:
                f.write(f"{entry}\n")

        print("  updated  .gitignore")
        return

    content = (
        "# Multi-AI local/runtime files\n"
        + "\n".join(_DEFAULT_GITIGNORE_ENTRIES)
        + "\n"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print("  created  .gitignore")


def run_init_command() -> int:
    """
    Initialize a Multi-AI workspace in the current directory.

    Creates:

        multi_ai_cli.ini
        .gitignore
        prompts/
        work_data/

    Existing files are preserved and never overwritten.

    Returns:
        int: Process exit code.
    """
    workspace = os.getcwd()

    print("Initializing Multi-AI workspace in:")
    print(f"  {workspace}")
    print()

    try:
        _create_file_if_missing(
            "multi_ai_cli.ini",
            _DEFAULT_INI_CONTENT,
        )

        _update_gitignore()

        _ensure_directory("prompts")
        _ensure_directory("work_data")

    except (OSError, RuntimeError) as e:
        print(f"[!] Initialization failed: {e}", file=sys.stderr)
        return 1

    print()
    print("[✓] Multi-AI workspace initialized.")

    return 0


def _extract_mode_arg(argv: list[str]) -> tuple[str | None, list[str]]:
    remaining: list[str] = []
    mode: str | None = None
    i = 0

    while i < len(argv):
        arg = argv[i]

        if arg.startswith("--mode="):
            if mode is not None:
                print("[!] Error: --mode specified more than once.", file=sys.stderr)
                sys.exit(2)

            value = arg[len("--mode=") :].strip().lower()
            if not value:
                print(
                    f"[!] Error: --mode requires a value. Valid: {', '.join(sorted(_VALID_MODES))}",
                    file=sys.stderr,
                )
                sys.exit(2)
            if value not in _VALID_MODES:
                print(
                    f"[!] Error: invalid mode '{value}'. Valid: {', '.join(sorted(_VALID_MODES))}",
                    file=sys.stderr,
                )
                sys.exit(2)

            mode = value
            i += 1
            continue

        if arg == "--mode":
            if mode is not None:
                print("[!] Error: --mode specified more than once.", file=sys.stderr)
                sys.exit(2)

            if i + 1 >= len(argv):
                print(
                    f"[!] Error: --mode requires a value. Valid: {', '.join(sorted(_VALID_MODES))}",
                    file=sys.stderr,
                )
                sys.exit(2)

            value = argv[i + 1].strip().lower()
            if value not in _VALID_MODES:
                print(
                    f"[!] Error: invalid mode '{value}'. Valid: {', '.join(sorted(_VALID_MODES))}",
                    file=sys.stderr,
                )
                sys.exit(2)

            mode = value
            i += 2
            continue

        remaining.append(arg)
        i += 1

    return mode, remaining


def _create_session() -> "AgentSession":  # noqa: F821
    """
    Create an AgentSession with the current registry and a fresh factory.

    For legacy config format, passes the legacy_sdk_map so that
    the session can create engines with the correct SDK type.

    Returns:
        A new AgentSession instance.
    """
    from .agent_factory import AgentFactory
    from .session import AgentSession

    factory = AgentFactory()
    return AgentSession(
        registry=agent_registry,
        factory=factory,
        legacy_sdk_map=legacy_sdk_map,
    )


def _run_legacy_auto_detection(argv: list[str]) -> int:
    """
    Selects execution mode using the legacy stdin TTY detection heuristic.

    When stdin is a TTY, runs the interactive REPL. Otherwise, runs
    filter mode with the provided arguments.

    Args:
        argv: The argument list to pass to filter mode (unused for REPL).

    Returns:
        Exit code from the selected mode.
    """
    if sys.stdin.isatty():
        return run_interactive_mode()

    from .filter_mode import run_filter_mode

    return run_filter_mode(argv)


def _read_interactive_input() -> str | None:
    r"""
    Reads a single logical command from interactive input, supporting
    line continuation with trailing backslash.

    If a line ends with ``\\``, the backslash is stripped and the next
    line is read and appended. Lines are joined with a single space.
    The continuation prompt changes to ``> `` for subsequent lines.

    Returns:
        str | None: The joined input string (stripped), or None if
            EOF is encountered on the first line.
    """
    try:
        first_line = input("% ")
    except EOFError:
        return None

    lines = [first_line]

    while lines[-1].rstrip().endswith("\\"):
        # Strip the trailing backslash from the current last line
        stripped = lines[-1].rstrip()
        lines[-1] = stripped[:-1]
        try:
            continuation = input("> ")
        except EOFError:
            print("[!] Incomplete continued input.")
            return None
        lines.append(continuation)

    # Join continuation lines with a space and strip outer whitespace
    return " ".join(lines).strip()


def startup() -> None:
    """
    Performs shared startup tasks for both interactive and filter modes.

    Loads the INI configuration, sets up logging, and initializes
    agent definitions in the registry. Exits early for --version flag
    or if the INI file is missing.
    """
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"multi-ai version {__version__}")
        sys.exit(0)

    ini_path = "multi_ai_cli.ini"
    if not os.path.exists(ini_path):
        print(
            f"[!] Error: '{ini_path}' not found in the current directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    setup_config(ini_path)
    setup_logger()

    from .config import initialize_engines

    initialize_engines()


def setup_readline() -> None:
    """
    Initialize readline support for the interactive CLI.

    This enables basic line editing and command history navigation,
    making arrow-key input more convenient in REPL-style usage.
    If available, it also configures Tab completion behavior and
    loads/saves persistent history across sessions.

    The setup is optional and safely skipped on environments where
    readline is not available.
    """
    try:
        import atexit
        import os
        import readline

        histfile = os.path.expanduser("~/.multi_ai_history")

        if os.path.exists(histfile):
            readline.read_history_file(histfile)

        atexit.register(readline.write_history_file, histfile)

        if "libedit" in getattr(readline, "__doc__", ""):
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    except ImportError:
        pass


def run_interactive_mode() -> int:
    """
    Runs the interactive REPL mode.

    Creates a single AgentSession for the REPL lifetime. Within this
    session, the same agent key always returns the same engine instance,
    preserving conversation history across commands.

    Displays the welcome banner and enters the command loop, processing
    user input including pipeline chaining with '->'.

    Returns:
        int: Exit code (always 0 for normal termination).
    """
    agent_defs = agent_registry.all_agents()
    print_welcome_banner(agent_defs, is_log_enabled)

    session = _create_session()

    while True:
        try:
            user_input = _read_interactive_input()

            if user_input is None:
                # EOF reached
                logger.info("--- Session Ended (EOF) ---")
                break

            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                logger.info("--- Session Ended ---")
                break

            try:
                parts = shlex.split(user_input)
            except ValueError as e:
                print(f"[!] Parse error: {e}")
                continue

            if not parts:
                continue

            command_chain = []
            current_command: list[str] = []

            for part in parts:
                if part == "->":
                    if current_command:
                        command_chain.append(current_command)
                        current_command = []
                else:
                    current_command.append(part)

            if current_command:
                command_chain.append(current_command)

            for step_idx, cmd_parts in enumerate(command_chain):
                if len(command_chain) > 1:
                    print(
                        f"\n[*] Pipeline Step {step_idx + 1}/{len(command_chain)}: "
                        f"{' '.join(cmd_parts)}"
                    )

                success = dispatch_command(cmd_parts, session)

                if not success and len(command_chain) > 1:
                    print("[!] Pipeline stopped due to an error in the current step.")
                    break
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n[!] Session interrupted. Type 'exit' to quit.")
        except Exception as e:
            print(f"[!] An unexpected error occurred: {e}")
            logger.error(f"Main loop critical error: {e}")

    return 0


def main() -> None:
    """
    Main entry point for the Multi-AI CLI application.

    Supported commands:

    - ``multi-ai init``   -> Initialize a Multi-AI workspace

    Runtime modes:

    - ``--mode repl``     -> Always starts interactive REPL, regardless of TTY
    - ``--mode filter``   -> Always runs single-shot filter mode
    - (omitted)           -> Legacy auto-detection via ``sys.stdin.isatty()``

    Explicit ``--mode`` selection overrides TTY-based auto-detection.
    """
    raw_argv = sys.argv[1:]

    # ---------------------------------------------------------
    # Workspace commands
    #
    # init must run before startup(), because startup() requires
    # multi_ai_cli.ini to already exist.
    # ---------------------------------------------------------

    if raw_argv and raw_argv[0].lower() == "init":
        if len(raw_argv) != 1:
            print("[!] Usage: multi-ai init", file=sys.stderr)
            sys.exit(2)

        sys.exit(run_init_command())

    # ---------------------------------------------------------
    # Normal runtime startup
    # ---------------------------------------------------------

    mode, remaining_argv = _extract_mode_arg(raw_argv)

    startup()
    setup_readline()

    if mode == "repl":
        code = run_interactive_mode()

    elif mode == "filter":
        from .filter_mode import run_filter_mode

        code = run_filter_mode(remaining_argv)

    else:
        code = _run_legacy_auto_detection(raw_argv)

    sys.exit(code)


if __name__ == "__main__":
    main()
