"""Command parsing for chat session file-related shortcuts."""

from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Supported colon-prefixed command types."""

    WRITE = "w"
    WRITE_FORCE = "W"
    OUTPUT = "o"
    OUTPUT_FORCE = "O"
    READ = "r"


@dataclass
class Command:
    """Parsed command data."""

    type: CommandType
    path: str


def parse_command(text: str) -> Command | None:
    """Parse a colon-prefixed command string."""
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
        case ":W":
            return Command(CommandType.WRITE_FORCE, path)
        case ":o":
            return Command(CommandType.OUTPUT, path)
        case ":O":
            return Command(CommandType.OUTPUT_FORCE, path)
        case ":r":
            return Command(CommandType.READ, path)
        case _:
            return None
