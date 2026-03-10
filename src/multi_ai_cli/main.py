"""
Main entry point for the Multi-AI CLI application.

This module handles the application's lifecycle, including configuration
loading, AI engine initialization, interactive command loop, and pipeline
execution.
"""

import os
import shlex
import sys

from . import __version__
from .config import agent_engines, is_log_enabled, logger, setup_config, setup_logger
from .handlers import dispatch_command
from .utils import print_welcome_banner


def main() -> None:
    """
    Main entry point for the Multi-AI CLI application.

    Loads configuration, initializes engines, and starts the interactive
    command loop. It handles user input, command parsing (including
    pipelining with ``->``), and command execution in a loop, allowing
    the user to interact with the AI engines.

    The application can exit early for ``--version`` or if
    ``multi_ai_cli.ini`` is not found. It gracefully handles
    ``KeyboardInterrupt`` and logs unexpected errors during the loop.

    Raises:
        SystemExit: If ``--version`` is passed or the INI configuration
            file is missing.
    """
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"multi-ai version {__version__}")
        sys.exit(0)

    ini_path = "multi_ai_cli.ini"
    if not os.path.exists(ini_path):
        print(f"[!] Error: '{ini_path}' not found in the current directory.")
        sys.exit(1)

    setup_config(ini_path)
    setup_logger()

    from .config import initialize_engines

    initialize_engines()

    print_welcome_banner(agent_engines, is_log_enabled)

    while True:
        try:
            user_input = input("% ").strip()

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
                        f"\n[*] Pipeline Step {step_idx + 1}/{len(command_chain)}: {' '.join(cmd_parts)}"
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


if __name__ == "__main__":
    main()
