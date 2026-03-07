"""
Parsing utilities for Multi-AI CLI.

Handles CLI argument parsing, prompt building, and @sequence step parsing logic.
"""

import os
import shlex
import sys

from . import __version__
from .config import engines, is_log_enabled, logger, setup_config, setup_logger
from .handlers import dispatch_command
from .utils import print_welcome_banner


def main() -> None:
    """
    Main entry point for the Multi-AI CLI application.

    Loads configuration, initializes engines, and starts the interactive command loop.
    It handles user input, command parsing, and command execution in a loop,
    allowing the user to interact with the AI engines.
    """
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"multi-ai version {__version__}")
        sys.exit(0)

    # Check for required configuration file
    ini_path = "multi_ai_cli.ini"
    if not os.path.exists(ini_path):
        print(f"[!] Error: '{ini_path}' not found in the current directory.")
        sys.exit(1)

    # Load configuration and setup logging
    setup_config(ini_path)  # Load settings from the INI file
    setup_logger()  # Configure the logger for the application

    # Initialize AI clients and engines
    from .engines import initialize_engines

    initialize_engines()  # Initialize the available AI engines

    # Show startup information, including available engines and logging status
    print_welcome_banner(engines, is_log_enabled)

    while True:
        try:
            user_input = input("% ").strip()  # Prompt user for input

            if not user_input:  # Skip empty input
                continue
            if user_input.lower() in ["exit", "quit"]:  # Allow user to exit the loop
                logger.info("--- Session Ended ---")
                break

            try:
                parts = shlex.split(user_input)  # Split user input into command parts
            except ValueError as e:
                print(f"[!] Parse error: {e}")  # Handle parsing errors
                continue

            if not parts:  # Skip if no parts found
                continue

            command_chain = []  # Prepare to hold command pipeline
            current_command: list[str] = []  # Temporary holder for the current command

            # Split user input into commands based on "->"
            for part in parts:
                if part == "->":  # Command delimiter
                    if current_command:  # If there is a command to save
                        command_chain.append(current_command)  # Save current command
                        current_command = []  # Reset for next command
                else:
                    current_command.append(part)  # Add part to the current command

            # Append the last command if it exists
            if current_command:
                command_chain.append(current_command)

            # Execute the commands in the pipeline sequentially
            for step_idx, cmd_parts in enumerate(command_chain):
                if len(command_chain) > 1:
                    print(
                        f"\n[*] Pipeline Step {step_idx + 1}/{len(command_chain)}: {' '.join(cmd_parts)}"
                    )

                success = dispatch_command(cmd_parts)  # Execute the command

                # Stop the pipeline if any command fails
                if not success and len(command_chain) > 1:
                    print("[!] Pipeline stopped due to an error in the current step.")
                    break

        except KeyboardInterrupt:
            print(
                "\n[!] Session interrupted. Type 'exit' to quit."
            )  # Handle keyboard interruption
        except Exception as e:
            print(f"[!] An unexpected error occurred: {e}")  # Handle unexpected errors
            logger.error(f"Main loop critical error: {e}")  # Log the error


if __name__ == "__main__":
    main()  # Execute the main function when the script is run
