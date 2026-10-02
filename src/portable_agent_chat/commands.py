"""Command parsing for chat session file-related shortcuts."""

from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Supported colon-prefixed command types."""

    WRITE = "w"
    OUTPUT = "o"
    READ = "r"


@dataclass
class Command:
    """Parsed command data."""

    type: CommandType
    path: str


def parse_command(text: str) -> Command | None:
    """Parse a colon-prefixed command string.

    Supported commands are:

    - ``:w <path>`` to write the last response
    - ``:o <path>`` to write the next response
    - ``:r <path>`` to include a file in the next prompt

    Args:
        text: Raw user input.

    Returns:
        A parsed command if the input is a supported command, otherwise ``None``.

    Raises:
        ValueError: If a command prefix is present but the path is missing.
    """
    text = text.strip()

    if not text.startswith(":"):
        return None

    parts = text.split(maxsplit=1)

    if len(parts) != 2:
        raise ValueError("path is required")

    command, path = parts
    path = path.strip()

    if not path:
        raise ValueError("path is required")

    match command:
        case ":w":
            return Command(CommandType.WRITE, path)
        case ":o":
            return Command(CommandType.OUTPUT, path)
        case ":r":
            return Command(CommandType.READ, path)
        case _:
            return None
