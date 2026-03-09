from unittest.mock import mock_open, patch

import pytest

from multi_ai_cli.parsers import (
    WRITE_MODE_CODE,
    WRITE_MODE_RAW,
    ParsedInput,
    _parse_sh_input,
    _parse_write_flag,
    build_ai_prompt,
    detect_parallel_block,
    normalize_step,
    parse_cli_input,
    parse_sequence_steps,
    smart_split_parallel,
    smart_split_steps,
)


class TestParseCliInput:
    def test_basic_flags(self):
        # parts[0] is always skipped (it's the @command itself)
        parts = ["@gpt", "hello", "world", "-r", "file1.txt", "-m", "my message", "-e"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.a1 == "hello world"
        assert result.read_files == ["file1.txt"]
        assert result.message == "my message"
        assert result.use_editor is True

    def test_no_flags_bare_tokens_only(self):
        parts = ["@gpt", "summarize", "this"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.a1 == "summarize this"
        assert result.read_files == []
        assert result.message == ""
        assert result.use_editor is False

    def test_multiple_read_files(self):
        parts = ["@gpt", "-r", "a.txt", "-r", "b.txt"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.read_files == ["a.txt", "b.txt"]

    def test_multiple_messages_concatenated(self):
        parts = ["@gpt", "-m", "first", "-m", "second"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.message == "first second"

    def test_write_flag_raw(self):
        parts = ["@gpt", "-w", "out.txt"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.write_file == "out.txt"
        assert result.write_mode == WRITE_MODE_RAW

    def test_write_flag_code(self):
        parts = ["@gpt", "-w:code", "out.py"]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.write_file == "out.py"
        assert result.write_mode == WRITE_MODE_CODE

    def test_missing_read_arg_returns_none(self):
        parts = ["@gpt", "-r"]
        result = parse_cli_input(parts)
        assert result is None

    def test_missing_write_arg_returns_none(self):
        parts = ["@gpt", "-w"]
        result = parse_cli_input(parts)
        assert result is None

    def test_missing_message_arg_returns_none(self):
        parts = ["@gpt", "-m"]
        result = parse_cli_input(parts)
        assert result is None

    def test_long_flags(self):
        parts = [
            "@gpt",
            "--read",
            "f.txt",
            "--write",
            "o.txt",
            "--message",
            "hi",
            "--edit",
        ]
        result = parse_cli_input(parts)

        assert result is not None
        assert result.read_files == ["f.txt"]
        assert result.write_file == "o.txt"
        assert result.message == "hi"
        assert result.use_editor is True


class TestParseWriteFlag:
    def test_dash_w(self):
        mode, is_write = _parse_write_flag("-w")
        assert is_write is True
        assert mode == WRITE_MODE_RAW

    def test_dash_w_raw(self):
        mode, is_write = _parse_write_flag("-w:raw")
        assert is_write is True
        assert mode == WRITE_MODE_RAW

    def test_dash_w_code(self):
        mode, is_write = _parse_write_flag("-w:code")
        assert is_write is True
        assert mode == WRITE_MODE_CODE

    def test_unknown_modifier(self):
        mode, is_write = _parse_write_flag("-w:unknown")
        assert is_write is False
        assert mode is None

    def test_not_write_flag(self):
        mode, is_write = _parse_write_flag("-r")
        assert is_write is False


class TestBuildAiPrompt:
    @patch(
        "multi_ai_cli.parsers.secure_resolve_path", return_value="/fake/path/test.txt"
    )
    def test_all_sections(self, mock_resolve):
        parsed = ParsedInput(
            a1="Title text",
            message="Message text",
            read_files=["test.txt"],
        )
        file_content = "File Content Here"
        with patch("builtins.open", mock_open(read_data=file_content)):
            result = build_ai_prompt(parsed, editor_content="Editor text")

        assert "Title text" in result
        assert "Message text" in result
        assert "Editor text" in result
        assert "File Content Here" in result
        assert "--- [File: test.txt] ---" in result

    def test_a1_only(self):
        parsed = ParsedInput(a1="Just title")
        result = build_ai_prompt(parsed)
        assert result == "Just title"

    def test_empty_input(self):
        parsed = ParsedInput()
        result = build_ai_prompt(parsed)
        assert result == ""

    @patch(
        "multi_ai_cli.parsers.secure_resolve_path", side_effect=Exception("not found")
    )
    def test_file_read_error_raises(self, mock_resolve):
        parsed = ParsedInput(read_files=["missing.txt"])
        with pytest.raises(RuntimeError, match="Error reading input file"):
            build_ai_prompt(parsed)


class TestParseSequenceSteps:
    def test_two_sequential_steps(self):
        content = "@grok some command -> @gpt another command"
        result = parse_sequence_steps(content)

        assert result is not None
        assert len(result) == 2
        assert result[0] == [["@grok", "some", "command"]]
        assert result[1] == [["@gpt", "another", "command"]]

    def test_unknown_command_returns_none(self):
        content = "@unknown_command"
        result = parse_sequence_steps(content)
        assert result is None

    def test_parallel_block(self):
        content = "[@gpt task1 || @claude task2]"
        result = parse_sequence_steps(content)

        assert result is not None
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0] == ["@gpt", "task1"]
        assert result[0][1] == ["@claude", "task2"]

    def test_empty_content(self):
        content = ""
        result = parse_sequence_steps(content)
        assert result == []

    def test_command_without_at_prefix_gets_added(self):
        content = "gpt hello"
        result = parse_sequence_steps(content)

        assert result is not None
        assert result[0] == [["@gpt", "hello"]]


class TestParseShInput:
    def test_basic_command(self):
        parts = ["@sh", "echo", "hello"]
        result = _parse_sh_input(parts)

        assert result is not None
        assert result.command == "echo hello"
        assert result.run_file is None
        assert result.write_file is None
        assert result.use_shell is False

    def test_with_run_file(self):
        parts = ["@sh", "-r", "script.sh"]
        result = _parse_sh_input(parts)

        assert result is not None
        assert result.run_file == "script.sh"
        assert result.command is None

    def test_with_write_file(self):
        parts = ["@sh", "ls", "-w", "output.txt"]
        result = _parse_sh_input(parts)

        assert result is not None
        assert result.command == "ls"
        assert result.write_file == "output.txt"

    def test_with_shell_flag(self):
        parts = ["@sh", "--shell", "echo", "hi"]
        result = _parse_sh_input(parts)

        assert result is not None
        assert result.use_shell is True
        assert result.command == "echo hi"

    def test_no_command_or_file_returns_none(self):
        parts = ["@sh"]
        result = _parse_sh_input(parts)
        assert result is None

    def test_missing_read_arg_returns_none(self):
        parts = ["@sh", "-r"]
        result = _parse_sh_input(parts)
        assert result is None

    def test_missing_write_arg_returns_none(self):
        parts = ["@sh", "-w"]
        result = _parse_sh_input(parts)
        assert result is None


class TestSmartSplitSteps:
    def test_basic_split(self):
        result = smart_split_steps("step1 -> step2")
        assert result == ["step1", "step2"]

    def test_quoted_arrow_not_split(self):
        result = smart_split_steps('"step -> inside" -> step2')
        assert len(result) == 2
        assert result[0] == '"step -> inside"'


class TestSmartSplitParallel:
    def test_basic_split(self):
        result = smart_split_parallel("task1 || task2")
        assert result == ["task1", "task2"]


class TestNormalizeStep:
    def test_removes_comments_and_collapses_spaces(self):
        text = "  # comment\n  hello   world  \n"
        result = normalize_step(text)
        assert result == "hello world"

    def test_empty_input(self):
        assert normalize_step("") == ""


class TestDetectParallelBlock:
    def test_parallel_block(self):
        is_parallel, inner = detect_parallel_block("[task1 || task2]")
        assert is_parallel is True
        assert inner == "task1 || task2"

    def test_not_parallel(self):
        is_parallel, inner = detect_parallel_block("@gpt hello")
        assert is_parallel is False
        assert inner == "@gpt hello"


if __name__ == "__main__":
    pytest.main()
