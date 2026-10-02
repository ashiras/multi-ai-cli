"""CLI entry point for the portable chat application."""

import argparse

from prompt_toolkit import PromptSession

from multi_ai_cli.main import startup
from multi_ai_cli.utils import clear_thinking_line
from portable_agent_chat.chat import ChatSession
from portable_agent_chat.commands import CommandType, parse_command


def main() -> None:
    """Run the interactive portable chat command-line interface."""
    parser = argparse.ArgumentParser(
        prog="portable-chat",
        description="Minimal conversation CLI for Portable Agent / multi-ai",
    )

    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name to use for this chat session",
    )

    args = parser.parse_args()

    # Load multi-ai configuration and register agent definitions.
    startup()

    try:
        chat = ChatSession(args.agent)
    except ValueError as exc:
        parser.error(str(exc))

    prompt_session = PromptSession(multiline=True)

    print("portable-chat")
    print(f"agent: {args.agent}")
    print()

    while True:
        try:
            prompt = prompt_session.prompt("% ")

        except KeyboardInterrupt:
            continue

        except EOFError:
            print("bye")
            break

        if not prompt.strip():
            continue

        try:
            command = parse_command(prompt)
        except ValueError as exc:
            print(f"error: {exc}")
            continue

        if command is not None:
            if command.type is CommandType.WRITE:
                try:
                    size = chat.write_last_response(command.path)
                    print(f"wrote {command.path} ({size} bytes)")
                except (ValueError, FileExistsError) as exc:
                    print(f"error: {exc}")

            elif command.type is CommandType.READ:
                try:
                    paths = chat.add_pending_read(command.path)

                    if len(paths) == 1:
                        print(f"queued {paths[0]}")
                    else:
                        print(f"queued {len(paths)} files")

                except (FileNotFoundError, ValueError, OSError) as exc:
                    print(f"error: {exc}")

            elif command.type is CommandType.OUTPUT:
                try:
                    chat.set_pending_output(command.path)
                    print(f"queued output {command.path}")
                except FileExistsError as exc:
                    print(f"error: {exc}")

            continue

        try:
            print(f"[*] @{args.agent} is thinking...", end="\r", flush=True)

            output_path = chat.pending_output
            response = chat.send(prompt)

            clear_thinking_line()

        except Exception as exc:
            clear_thinking_line()
            print(f"error: {exc}")
            continue

        print()
        print(response)
        print()

        if output_path is not None:
            size = len(response.encode("utf-8"))
            print(f"wrote {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
