"""Tests for multi_ai_cli.adapters.shell.models module."""

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


class TestShellResult:
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
