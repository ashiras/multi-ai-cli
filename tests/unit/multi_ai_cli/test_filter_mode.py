"""Tests for multi_ai_cli.filter_mode module."""

from unittest.mock import patch

import pytest

from multi_ai_cli.filter_mode import (
    ParsedFilterInput,
    build_filter_prompt,
    parse_filter_cli_input,
)
from multi_ai_cli.registry import (
    AgentDefinition,
    agent_registry,
    reset_registries,
)


@pytest.fixture(autouse=True)
def setup_registry():
    """Ensure registry has test agents for filter mode tests."""
    reset_registries()
    agent_registry.register(
        AgentDefinition(
            agent_key="gpt",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
    )
    agent_registry.register(
        AgentDefinition(
            agent_key="claude",
            adapter="openai-compatible",
            server="http://localhost",
            engine="claude-3",
        )
    )
    yield
    reset_registries()


class TestParsedFilterInput:
    def test_defaults(self):
        p = ParsedFilterInput()
        assert p.agent == ""
        assert p.message == ""
        assert p.read_files == []


class TestParseFilterCliInput:
    def test_basic_agent(self, capsys):
        result = parse_filter_cli_input(["@gpt"])
        assert result is not None
        assert result.agent == "gpt"

    def test_with_message(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-m", "summarize this"])
        assert result is not None
        assert result.message == "summarize this"

    def test_with_read_file(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-r", "ref.txt"])
        assert result is not None
        assert result.read_files == ["ref.txt"]

    def test_multiple_read_files(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-r", "a.txt", "-r", "b.txt"])
        assert result is not None
        assert result.read_files == ["a.txt", "b.txt"]

    def test_multiple_messages(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-m", "first", "-m", "second"])
        assert result is not None
        assert result.message == "first second"

    def test_interleaved_flags(self):
        result = parse_filter_cli_input(
            ["@gpt", "-m", "msg1", "-r", "file1", "-m", "msg2", "-r", "file2"]
        )
        assert result is not None
        assert result.message == "msg1 msg2"
        assert result.read_files == ["file1", "file2"]

    def test_empty_argv(self, capsys):
        result = parse_filter_cli_input([])
        assert result is None

    def test_no_agent(self, capsys):
        result = parse_filter_cli_input(["-m", "hello"])
        assert result is None

    def test_unknown_agent(self, capsys):
        result = parse_filter_cli_input(["@nonexistent"])
        assert result is None

    def test_builtin_command_rejected(self, capsys):
        result = parse_filter_cli_input(["@sh"])
        assert result is None

    def test_write_flag_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-w", "out.txt"])
        assert result is None

    def test_edit_flag_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-e"])
        assert result is None

    def test_pipeline_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "->", "@claude"])
        assert result is None

    def test_parallel_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "||", "@claude"])
        assert result is None

    def test_multiple_agents_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "@claude"])
        assert result is None

    def test_bare_token_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "bare_word"])
        assert result is None

    def test_unknown_flag_rejected(self, capsys):
        result = parse_filter_cli_input(["@gpt", "--verbose"])
        assert result is None

    def test_missing_m_value(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-m"])
        assert result is None

    def test_missing_r_value(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-r"])
        assert result is None

    def test_r_value_is_flag(self, capsys):
        result = parse_filter_cli_input(["@gpt", "-r", "-m"])
        assert result is None


class TestBuildFilterPrompt:
    def test_stdin_only(self):
        result = build_filter_prompt("hello world")
        assert "[Primary Input]" in result
        assert "hello world" in result

    def test_message_only(self):
        result = build_filter_prompt("", message="instruction")
        assert "[Instruction]" in result
        assert "instruction" in result

    def test_stdin_and_message(self):
        result = build_filter_prompt("input text", message="do this")
        assert "[Instruction]" in result
        assert "[Primary Input]" in result
        assert "do this" in result
        assert "input text" in result

    def test_empty_stdin_and_message(self):
        result = build_filter_prompt("", message="")
        assert result == ""

    def test_with_read_files(self, tmp_path):
        """Test build_filter_prompt with -r files by patching the config."""
        ref_file = tmp_path / "ref.txt"
        ref_file.write_text("reference content")

        # Patch load_reference_sections to use a real config
        import configparser

        real_config = configparser.ConfigParser()
        real_config.read_dict({"Paths": {"work_data": str(tmp_path)}})

        with patch("multi_ai_cli.filter_mode.load_reference_sections") as mock_load:
            mock_load.return_value = [
                "--- [File: ref.txt] ---\nreference content\n--- [End of File: ref.txt] ---"
            ]
            result = build_filter_prompt("input", read_files=["ref.txt"])

        assert "[Reference Files]" in result
        assert "reference content" in result

    def test_whitespace_only_stdin(self):
        result = build_filter_prompt("   ", message="msg")
        # Whitespace-only stdin should not produce Primary Input section
        assert "[Primary Input]" not in result
        assert "[Instruction]" in result

    def test_empty_read_files_list(self):
        """Ensure no [Reference Files] header if read_files is an empty list."""
        result = build_filter_prompt("input", read_files=[])
        assert "[Reference Files]" not in result

    def test_load_reference_sections_returns_empty(self):
        """Ensure no [Reference Files] header if load_reference_sections returns empty content."""
        with patch("multi_ai_cli.filter_mode.load_reference_sections") as mock_load:
            mock_load.return_value = []
            result = build_filter_prompt("input", read_files=["nonexistent.txt"])
        assert "[Reference Files]" not in result

    def test_section_ordering(self):
        with patch("multi_ai_cli.filter_mode.load_reference_sections") as mock_load:
            mock_load.return_value = ["ref content"]
            result = build_filter_prompt(
                stdin_text="stdin content",
                message="instruction content",
                read_files=["ref.txt"],
            )

        instr_idx = result.find("[Instruction]")
        input_idx = result.find("[Primary Input]")
        ref_idx = result.find("[Reference Files]")

        assert instr_idx != -1
        assert input_idx != -1
        assert ref_idx != -1
        assert instr_idx < input_idx < ref_idx
