import os
import shlex
import sys

from .config import engines, is_log_enabled, logger, setup_config, setup_logger
from .handlers import dispatch_command
from .utils import print_welcome_banner


def main():
    """
    Main entry point for the Multi-AI CLI application.
    Loads configuration, initializes engines, and starts the interactive command loop.
    """
    # Check for required configuration file
    ini_path = "multi_ai_cli.ini"
    if not os.path.exists(ini_path):
        print(f"[!] Error: '{ini_path}' not found in the current directory.")
        sys.exit(1)

    # Load configuration and setup logging
    setup_config(ini_path)
    setup_logger()

    # Initialize AI clients and engines
    from .engines import initialize_engines

    initialize_engines()

    # Show startup information
    print_welcome_banner(engines, is_log_enabled)

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

            dispatch_command(parts)

        except KeyboardInterrupt:
            print("\n[!] Session interrupted. Type 'exit' to quit.")
        except Exception as e:
            print(f"[!] An unexpected error occurred: {e}")
            logger.error(f"Main loop critical error: {e}")


if __name__ == "__main__":
    main()
