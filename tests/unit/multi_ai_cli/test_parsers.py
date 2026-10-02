"""Tests for multi_ai_cli.parsers module."""

import configparser
import os
import tempfile

import pytest

from multi_ai_cli.parsers import (
    BUILTIN_COMMANDS,
    ParsedInput,
    _is_known_flag,
    _is_unknown_flag,
    _parse_agent_flags,
    _parse_sh_input,
    _parse_write_flag,
    _tokenize_agent_input,
    _validate_parsed_input,
    build_ai_prompt,
    detect_parallel_block,
    load_reference_sections,
    normalize_step,
    parse_cli_input,
    parse_sequence_steps,
    smart_split_parallel,
    smart_split_steps,
)


class TestBuiltinCommands:
    def test_contains_expected(self):
        expected = {"sh", "scrub", "flush", "efficient", "pause", "sequence"}
        assert expected.issubset(BUILTIN_COMMANDS)

    def test_contains_figma(self):
        assert "figma.pull" in BUILTIN_COMMANDS
        assert "figma.push" in BUILTIN_COMMANDS

    def test_contains_github(self):
        assert "github.repo" in BUILTIN_COMMANDS
        assert "github.tree" in BUILTIN_COMMANDS
        assert "github.file" in BUILTIN_COMMANDS
        assert "github.issue" in BUILTIN_COMMANDS
        assert "github.issues" in BUILTIN_COMMANDS


class TestParsedInput:
    def test_defaults(self):
        p = ParsedInput()
        assert p.a1 == ""
        assert p.message == ""
        assert p.read_files == []
        assert p.write_file is None
        assert p.write_mode == "raw"
        assert p.use_editor is False

    def test_post_init_none_read_files(self):
        p = ParsedInput(read_files=None)
        assert p.read_files == []


class TestIsKnownFlag:
    def test_known_flags(self):
        for flag in ["-r", "--read", "-w", "--write", "-m", "--message", "-e", "--edit"]:
            assert _is_known_flag(flag), f"{flag} should be known"

    def test_write_variants(self):
        assert _is_known_flag("-w:raw")
        assert _is_known_flag("-w:code")
        assert _is_known_flag("--write:raw")
        assert _is_known_flag("--write:code")

    def test_unknown(self):
        assert not _is_known_flag("--unknown")
        assert not _is_known_flag("hello")


class TestIsUnknownFlag:
    def test_known_flags_not_unknown(self):
        assert not _is_unknown_flag("-r")
        assert not _is_unknown_flag("-w")
        assert not _is_unknown_flag("-e")

    def test_unknown_flags(self):
        assert _is_unknown_flag("-x")
        assert _is_unknown_flag("--verbose")
        assert _is_unknown_flag("--unknown")

    def test_non_flags(self):
        assert not _is_unknown_flag("hello")
        assert not _is_unknown_flag("file.txt")


class TestParseWriteFlag:
    def test_not_write_flag(self):
        mode, is_write, err = _parse_write_flag("hello")
        assert not is_write

    def test_plain_w(self):
        mode, is_write, err = _parse_write_flag("-w")
        assert is_write
        assert mode == "raw"
        assert err is None

    def test_plain_write(self):
        mode, is_write, err = _parse_write_flag("--write")
        assert is_write
        assert mode == "raw"

    def test_w_raw(self):
        mode, is_write, err = _parse_write_flag("-w:raw")
        assert mode == "raw"
        assert err is None

    def test_w_code(self):
        mode, is_write, err = _parse_write_flag("-w:code")
        assert mode == "code"
        assert err is None

    def test_write_code(self):
        mode, is_write, err = _parse_write_flag("--write:code")
        assert mode == "code"

    def test_invalid_modifier(self):
        mode, is_write, err = _parse_write_flag("-w:invalid")
        assert is_write
        assert err is not None
        assert "Unknown write modifier" in err


class TestTokenizeAgentInput:
    def test_skip_command(self):
        assert _tokenize_agent_input(["@gpt", "hello"]) == ["hello"]

    def test_empty(self):
        assert _tokenize_agent_input(["@gpt"]) == []

    def test_single_element(self):
        assert _tokenize_agent_input(["@gpt"]) == []


class TestParseAgentFlags:
    def test_bare_text(self):
        result = _parse_agent_flags(["hello", "world"])
        assert result is not None
        assert result.a1 == "hello world"

    def test_message_flag(self):
        result = _parse_agent_flags(["-m", "test message"])
        assert result is not None
        assert result.message == "test message"

    def test_multiple_messages(self):
        result = _parse_agent_flags(["-m", "first", "-m", "second"])
        assert result is not None
        assert result.message == "first second"

    def test_read_flag(self):
        result = _parse_agent_flags(["-r", "file.txt"])
        assert result is not None
        assert result.read_files == ["file.txt"]

    def test_multiple_reads(self):
        result = _parse_agent_flags(["-r", "a.txt", "-r", "b.txt"])
        assert result is not None
        assert result.read_files == ["a.txt", "b.txt"]

    def test_write_flag(self):
        result = _parse_agent_flags(["-w", "output.txt"])
        assert result is not None
        assert result.write_file == "output.txt"
        assert result.write_mode == "raw"

    def test_write_code(self):
        result = _parse_agent_flags(["-w:code", "output.py"])
        assert result is not None
        assert result.write_file == "output.py"
        assert result.write_mode == "code"

    def test_editor_flag(self):
        result = _parse_agent_flags(["-e"])
        assert result is not None
        assert result.use_editor is True

    def test_editor_long_flag(self):
        result = _parse_agent_flags(["--edit"])
        assert result is not None
        assert result.use_editor is True

    def test_unknown_flag_rejected(self, capsys):
        result = _parse_agent_flags(["--unknown"])
        assert result is None
        captured = capsys.readouterr()
        assert "Unknown flag" in captured.out

    def test_missing_r_value(self, capsys):
        result = _parse_agent_flags(["-r"])
        assert result is None
        captured = capsys.readouterr()
        assert "requires a filename" in captured.out

    def test_missing_w_value(self, capsys):
        result = _parse_agent_flags(["-w"])
        assert result is None
        captured = capsys.readouterr()
        assert "requires a filename" in captured.out

    def test_missing_m_value(self, capsys):
        result = _parse_agent_flags(["-m"])
        assert result is None
        captured = capsys.readouterr()
        assert "requires a text" in captured.out

    def test_r_value_is_flag(self, capsys):
        result = _parse_agent_flags(["-r", "-m"])
        assert result is None

    def test_combined(self):
        result = _parse_agent_flags(
            ["context", "-m", "message", "-r", "file.txt", "-w:code", "out.py", "-e"]
        )
        assert result is not None
        assert result.a1 == "context"
        assert result.message == "message"
        assert result.read_files == ["file.txt"]
        assert result.write_file == "out.py"
        assert result.write_mode == "code"
        assert result.use_editor is True


class TestParseCliInput:
    def test_basic(self):
        result = parse_cli_input(["@gpt", "hello", "world"])
        assert result is not None
        assert result.a1 == "hello world"

    def test_with_flags(self):
        result = parse_cli_input(["@gpt", "-m", "test", "-r", "f.txt"])
        assert result is not None
        assert result.message == "test"
        assert result.read_files == ["f.txt"]

    def test_empty_tokens(self):
        result = parse_cli_input(["@gpt"])
        assert result is not None
        assert result.a1 == ""

    def test_unknown_flag_returns_none(self, capsys):
        result = parse_cli_input(["@gpt", "--bad-flag"])
        assert result is None


class TestValidateParsedInput:
    def test_always_true(self):
        assert _validate_parsed_input(ParsedInput()) is True
        assert _validate_parsed_input(ParsedInput(a1="text")) is True


class TestLoadReferenceSections:
    def test_single_file(self):
        cfg = configparser.ConfigParser()
        tmpdir = tempfile.mkdtemp()
        cfg.add_section("Paths")
        cfg.set("Paths", "work_data", tmpdir)

        filepath = os.path.join(tmpdir, "test.txt")
        with open(filepath, "w") as f:
            f.write("file content")

        sections = load_reference_sections(["test.txt"], config=cfg)
        assert len(sections) == 1
        assert "file content" in sections[0]
        assert "[File: test.txt]" in sections[0]

    def test_multiple_files(self):
        cfg = configparser.ConfigParser()
        tmpdir = tempfile.mkdtemp()
        cfg.add_section("Paths")
        cfg.set("Paths", "work_data", tmpdir)

        for name in ["a.txt", "b.txt"]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write(f"content of {name}")

        sections = load_reference_sections(["a.txt", "b.txt"], config=cfg)
        assert len(sections) == 2

    def test_missing_file_raises(self):
        cfg = configparser.ConfigParser()
        tmpdir = tempfile.mkdtemp()
        cfg.add_section("Paths")
        cfg.set("Paths", "work_data", tmpdir)

        with pytest.raises(RuntimeError, match="Error reading"):
            load_reference_sections(["nonexistent.txt"], config=cfg)


class TestBuildAiPrompt:
    def setup_method(self):
        from multi_ai_cli import config as cfg_mod

        self.tmpdir = tempfile.mkdtemp()
        cfg_mod.config.read_dict({"Paths": {"work_data": self.tmpdir}})

    def test_bare_text_only(self):
        parsed = ParsedInput(a1="hello world")
        result = build_ai_prompt(parsed)
        assert result == "hello world"

    def test_message_only(self):
        parsed = ParsedInput(message="do this")
        result = build_ai_prompt(parsed)
        assert result == "do this"

    def test_editor_content(self):
        parsed = ParsedInput()
        result = build_ai_prompt(parsed, editor_content="editor text")
        assert result == "editor text"

    def test_combined_order(self):
        parsed = ParsedInput(a1="context", message="instruction")
        result = build_ai_prompt(parsed, editor_content="editor")
        parts = result.split("\n\n")
        assert parts[0] == "context"
        assert parts[1] == "instruction"
        assert parts[2] == "editor"

    def test_with_read_file(self):
        filepath = os.path.join(self.tmpdir, "ref.txt")
        with open(filepath, "w") as f:
            f.write("reference content")

        parsed = ParsedInput(a1="prompt", read_files=["ref.txt"])
        result = build_ai_prompt(parsed)
        assert "reference content" in result
        assert "prompt" in result


class TestSmartSplitSteps:
    def test_single_step(self):
        assert smart_split_steps("@gpt hello") == ["@gpt hello"]

    def test_multiple_steps(self):
        result = smart_split_steps("@gpt hello -> @claude world")
        assert result == ["@gpt hello", "@claude world"]

    def test_quoted_arrow(self):
        result = smart_split_steps('@gpt "a -> b" -> @claude')
        assert len(result) == 2
        assert '"a -> b"' in result[0]

    def test_empty_steps_filtered(self):
        result = smart_split_steps("@gpt hello ->  -> @claude")
        assert len(result) == 2

    def test_escaped_chars(self):
        result = smart_split_steps("@gpt hello\\->world -> @claude")
        assert len(result) == 2


class TestSmartSplitParallel:
    def test_single_task(self):
        assert smart_split_parallel("@gpt hello") == ["@gpt hello"]

    def test_two_tasks(self):
        result = smart_split_parallel("@gpt hello || @claude world")
        assert result == ["@gpt hello", "@claude world"]

    def test_quoted_pipes(self):
        result = smart_split_parallel('@gpt "a || b" || @claude')
        assert len(result) == 2

    def test_empty_segments_filtered(self):
        result = smart_split_parallel("@gpt ||  || @claude")
        assert len(result) == 2


class TestNormalizeStep:
    def test_basic(self):
        assert normalize_step("  @gpt hello  ") == "@gpt hello"

    def test_removes_comments(self):
        text = "# comment\n@gpt hello\n# another"
        assert normalize_step(text) == "@gpt hello"

    def test_removes_empty_lines(self):
        text = "\n\n@gpt hello\n\n"
        assert normalize_step(text) == "@gpt hello"

    def test_collapses_spaces(self):
        assert normalize_step("@gpt   hello   world") == "@gpt hello world"

    def test_multiline_join(self):
        text = "@gpt\nhello\nworld"
        assert normalize_step(text) == "@gpt hello world"


class TestDetectParallelBlock:
    def test_parallel(self):
        is_par, inner = detect_parallel_block("[ @gpt || @claude ]")
        assert is_par
        assert inner == "@gpt || @claude"

    def test_not_parallel(self):
        is_par, inner = detect_parallel_block("@gpt hello")
        assert not is_par
        assert inner == "@gpt hello"

    def test_nested_brackets(self):
        is_par, inner = detect_parallel_block("[@gpt [test]]")
        assert is_par
        assert inner == "@gpt [test]"


class TestParseShInput:
    def test_direct_command(self, capsys):
        result = _parse_sh_input(["@sh", "echo", "hello"])
        assert result is not None
        assert result.command == "echo hello"

    def test_run_file(self, capsys):
        result = _parse_sh_input(["@sh", "-r", "script.py"])
        assert result is not None
        assert result.run_file == "script.py"

    def test_write_file(self, capsys):
        result = _parse_sh_input(["@sh", "echo", "hi", "-w", "out.txt"])
        assert result is not None
        assert result.write_file == "out.txt"

    def test_shell_flag(self, capsys):
        result = _parse_sh_input(["@sh", "--shell", "echo $HOME"])
        assert result is not None
        assert result.use_shell is True

    def test_no_command_no_file(self, capsys):
        result = _parse_sh_input(["@sh"])
        assert result is None
        captured = capsys.readouterr()
        assert "No command" in captured.out

    def test_missing_r_value(self, capsys):
        result = _parse_sh_input(["@sh", "-r"])
        assert result is None
        captured = capsys.readouterr()
        assert "requires a filename" in captured.out

    def test_missing_w_value(self, capsys):
        result = _parse_sh_input(["@sh", "-w"])
        assert result is None
        captured = capsys.readouterr()
        assert "requires a filename" in captured.out