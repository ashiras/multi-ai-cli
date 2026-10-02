from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    WRITE = "w"
    OUTPUT = "o"
    READ = "r"


@dataclass
class Command:
    type: CommandType
    path: str


def parse_command(text: str) -> Command | None:
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