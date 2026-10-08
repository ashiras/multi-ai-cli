"""Tests for multi_ai_cli.adapters.shell.models module."""

import pytest

from multi_ai_cli.adapters.shell.models import ParsedShInput, ShellResult


class TestParsedShInput:
    def test_defaults(self):
        p = ParsedShInput()
        assert p.command is None
        assert p.run_file is None
        assert p.write_file is None
        assert p.use_shell is False

    def test_with_values(self):
        p = ParsedShInput(
            command="ls -la",
            run_file="script.py",
            write_file="out.json",
            use_shell=True,
        )
        assert p.command == "ls -la"
        assert p.run_file == "script.py"
        assert p.write_file == "out.json"
        assert p.use_shell is True

    def test_partial_construction(self):
        p = ParsedShInput(command="only_command")
        assert p.command == "only_command"
        assert p.run_file is None
        assert p.write_file is None
        assert p.use_shell is False


class TestShellResult:
    def test_missing_arguments(self):
        with pytest.raises(TypeError):
            ShellResult()

    def test_empty_and_zero_values(self):
        r = ShellResult(
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=0.0,
            command_display="",
            use_shell=False,
        )
        assert r.exit_code == 0
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.duration_ms == 0.0
        assert r.command_display == ""
        assert r.use_shell is False

    def test_creation(self):
        r = ShellResult(
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=42.5,
            command_display="echo hello",
            use_shell=False,
        )
        assert r.exit_code == 0
        assert r.stdout == "output"
        assert r.stderr == ""
        assert r.duration_ms == 42.5
        assert r.command_display == "echo hello"
        assert r.use_shell is False

    def test_error_state(self):
        r = ShellResult(
            exit_code=1,
            stdout="",
            stderr="error occurred",
            duration_ms=10.0,
            command_display="false",
            use_shell=False,
        )
        assert r.exit_code == 1
        assert r.stderr == "error occurred"

    def test_complex_output(self):
        r = ShellResult(
            exit_code=0,
            stdout="line1\nline2",
            stderr="",
            duration_ms=100.0,
            command_display="cat file",
            use_shell=False,
        )
        assert r.stdout == "line1\nline2"
