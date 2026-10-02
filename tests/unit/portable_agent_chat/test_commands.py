import pytest

from portable_agent_chat.commands import Command, CommandType, parse_command


def test_parse_command_valid():
    assert parse_command(":w output.md") == Command(CommandType.WRITE, "output.md")
    assert parse_command(":o next.md") == Command(CommandType.OUTPUT, "next.md")
    assert parse_command(":r input.py") == Command(CommandType.READ, "input.py")

    # 空白が多いケース
    assert parse_command("  :w   path/to/file.txt  ") == Command(
        CommandType.WRITE, "path/to/file.txt"
    )


def test_parse_command_not_a_command():
    assert parse_command("hello world") is None
    assert parse_command("what is :w ?") is None
    assert parse_command(":x foo") is None  # 未知のコマンド


def test_parse_command_missing_path():
    with pytest.raises(ValueError, match="path is required"):
        parse_command(":w")

    with pytest.raises(ValueError, match="path is required"):
        parse_command(":r   ")
