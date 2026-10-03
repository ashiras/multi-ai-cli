"""CLI entry point for the portable chat application."""

import argparse
from collections.abc import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from multi_ai_cli.main import startup
from multi_ai_cli.utils import clear_thinking_line
from portable_agent_chat.chat import ChatSession
from portable_agent_chat.commands import CommandType, parse_command


class ChatCompleter(Completer):
    """Complete colon commands and file paths after :r, :w, and :o."""

    def __init__(self) -> None:
        """Initialize the command and path completer."""
        self.paths = PathCompleter(expanduser=True)

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        """Yield completions for colon commands and file paths."""
        line = document.text_before_cursor.split("\n")[-1]

        if line.startswith(":") and " " not in line:
            for cmd in (":r ", ":w ", ":o "):
                if cmd.startswith(line):
                    yield Completion(cmd[len(line) :], display=cmd.strip())
            return

        for prefix in (":r ", ":w ", ":o "):
            if line.startswith(prefix):
                rest = line[len(prefix) :]
                yield from self.paths.get_completions(
                    Document(rest, cursor_position=len(rest)),
                    complete_event,
                )
                return


bindings = KeyBindings()


@bindings.add("tab")
def _complete_or_indent(event: KeyPressEvent) -> None:
    """Complete colon commands; otherwise keep multiline indentation."""
    buf = event.app.current_buffer
    line = buf.document.current_line_before_cursor

    if line.startswith(":"):
        buf.start_completion(select_first=False)
    else:
        buf.insert_text("    ")


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

    prompt_session: PromptSession[str] = PromptSession(
        multiline=True,
        completer=ChatCompleter(),
        complete_while_typing=False,
        key_bindings=bindings,
    )

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
        print(f"── @{args.agent} " + "─" * 24)
        print()
        print(response)
        print()

        if output_path is not None:
            size = len(response.encode("utf-8"))
            print(f"wrote {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
