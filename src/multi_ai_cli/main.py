"""
Main entry point for the Multi-AI CLI application.

This module handles the application's lifecycle, including configuration
loading, AI engine initialization, mode detection (interactive REPL vs
filter mode), and command dispatch.
"""

import os
import shlex
import sys

from . import __version__
from .config import agent_engines, is_log_enabled, logger, setup_config, setup_logger
from .handlers import dispatch_command
from .utils import print_welcome_banner


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
    all AI engine instances. Exits early for --version flag or if
    the INI file is missing.
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

    Displays the welcome banner and enters the command loop, processing
    user input including pipeline chaining with '->'.

    Returns:
        int: Exit code (always 0 for normal termination).
    """
    print_welcome_banner(agent_engines, is_log_enabled)

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

                success = dispatch_command(cmd_parts)

                if not success and len(command_chain) > 1:
                    print("[!] Pipeline stopped due to an error in the current step.")
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

    Performs shared startup, then dispatches to either interactive REPL
    mode or filter mode based on whether stdin is a TTY.

    - sys.stdin.isatty() == True  -> Interactive REPL mode
    - sys.stdin.isatty() == False -> Filter mode (stdin -> AI -> stdout)
    """
    startup()
    setup_readline()

    if sys.stdin.isatty():
        code = run_interactive_mode()
    else:
        from .filter_mode import run_filter_mode

        code = run_filter_mode(sys.argv[1:])

    sys.exit(code)


if __name__ == "__main__":
    main()
