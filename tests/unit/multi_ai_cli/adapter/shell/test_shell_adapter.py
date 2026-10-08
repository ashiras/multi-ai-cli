"""Tests for multi_ai_cli.adapters.shell.adapter module."""

import json
import os
import tempfile

import pytest

from multi_ai_cli.adapters.shell.adapter import (
    RUNNER_MAP,
    ShellAdapter,
    ShellCommandBuildError,
)
from multi_ai_cli.adapters.shell.models import ParsedShInput, ShellResult


class TestRunnerMap:
    def test_python(self):
        assert RUNNER_MAP[".py"] == ["python3"]

    def test_shell(self):
        assert RUNNER_MAP[".sh"] == ["bash"]

    def test_ruby(self):
        assert RUNNER_MAP[".rb"] == ["ruby"]

    def test_javascript(self):
        assert RUNNER_MAP[".js"] == ["node"]

    def test_typescript(self):
        assert RUNNER_MAP[".ts"] == ["npx", "ts-node"]

    def test_r_lowercase(self):
        assert RUNNER_MAP[".r"] == ["Rscript"]

    def test_r_uppercase(self):
        assert RUNNER_MAP[".R"] == ["Rscript"]


class TestShellAdapterBuildCommand:
    def setup_method(self):
        self.adapter = ShellAdapter()

    def test_direct_command(self):
        parsed = ParsedShInput(command="echo hello")
        cmd, use_shell = self.adapter.build_command(parsed)
        assert cmd == ["echo", "hello"]
        assert use_shell is False

    def test_direct_command_shell_mode(self):
        parsed = ParsedShInput(command="echo $HOME | grep user", use_shell=True)
        cmd, use_shell = self.adapter.build_command(parsed)
        assert cmd == "echo $HOME | grep user"
        assert use_shell is True

    def test_run_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"print('hello')")
            tmpfile = f.name

        try:
            parsed = ParsedShInput(run_file=tmpfile)
            cmd, use_shell = self.adapter.build_command(parsed)
            assert cmd == ["python3", tmpfile]
            assert use_shell is False
        finally:
            os.unlink(tmpfile)

    def test_run_file_with_resolve_fn(self):
        with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as f:
            f.write(b"echo hi")
            tmpfile = f.name

        try:
            parsed = ParsedShInput(run_file="test.sh")

            def resolve_fn(name):
                return tmpfile

            cmd, use_shell = self.adapter.build_command(
                parsed, resolve_path_fn=resolve_fn
            )
            assert cmd == ["bash", tmpfile]
        finally:
            os.unlink(tmpfile)

    def test_both_command_and_file_raises(self):
        parsed = ParsedShInput(command="echo hello", run_file="test.py")
        with pytest.raises(ShellCommandBuildError, match="Cannot use both"):
            self.adapter.build_command(parsed)

    def test_no_command_no_file_raises(self):
        parsed = ParsedShInput()
        with pytest.raises(ShellCommandBuildError, match="No command or file"):
            self.adapter.build_command(parsed)

    def test_file_not_found_raises(self):
        parsed = ParsedShInput(run_file="nonexistent.py")
        with pytest.raises(ShellCommandBuildError, match="File not found"):
            self.adapter.build_command(parsed)

    def test_no_runner_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"data")
            tmpfile = f.name

        try:
            parsed = ParsedShInput(run_file=tmpfile)
            with pytest.raises(ShellCommandBuildError, match="No runner"):
                self.adapter.build_command(parsed)
        finally:
            os.unlink(tmpfile)

    def test_empty_command_string_raises(self):
        parsed = ParsedShInput(command="")
        with pytest.raises(ShellCommandBuildError):
            self.adapter.build_command(parsed)

    def test_command_parse_error(self):
        parsed = ParsedShInput(command="echo 'unterminated")
        with pytest.raises(ShellCommandBuildError, match="parse error"):
            self.adapter.build_command(parsed)

    def test_shell_mode_no_command_raises(self):
        parsed = ParsedShInput(command=None, use_shell=True)
        with pytest.raises(ShellCommandBuildError, match="No command"):
            self.adapter.build_command(parsed)


class TestShellAdapterExecuteCommand:
    def setup_method(self):
        self.adapter = ShellAdapter()

    def test_simple_echo(self):
        result = self.adapter.execute_command(["echo", "hello"], use_shell=False)
        assert isinstance(result, ShellResult)
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.duration_ms >= 0

    def test_shell_mode(self):
        result = self.adapter.execute_command("echo hello", use_shell=True)
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_nonzero_exit(self):
        result = self.adapter.execute_command(["false"], use_shell=False)
        assert result.exit_code != 0

    def test_stderr_capture(self):
        result = self.adapter.execute_command(
            ["python3", "-c", "import sys; sys.stderr.write('err\\n')"],
            use_shell=False,
        )
        assert "err" in result.stderr

    def test_command_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.adapter.execute_command(
                ["__nonexistent_command_xyz__"], use_shell=False
            )

    def test_command_display(self):
        result = self.adapter.execute_command(["echo", "test"], use_shell=False)
        assert "echo" in result.command_display

    def test_timeout_expired(self):
        import subprocess

        # Use a command that sleeps longer than the timeout
        with pytest.raises(subprocess.TimeoutExpired):
            self.adapter.execute_command(
                ["python3", "-c", "import time; time.sleep(1)"],
                use_shell=False,
                timeout=0.1,
            )


class TestShellAdapterResolveRunner:
    def test_known_extensions(self):
        assert ShellAdapter._resolve_runner("test.py") == ["python3"]
        assert ShellAdapter._resolve_runner("test.sh") == ["bash"]
        assert ShellAdapter._resolve_runner("test.rb") == ["ruby"]
        assert ShellAdapter._resolve_runner("test.js") == ["node"]
        assert ShellAdapter._resolve_runner("test.ts") == ["npx", "ts-node"]
        assert ShellAdapter._resolve_runner("test.pl") == ["perl"]
        assert ShellAdapter._resolve_runner("test.lua") == ["lua"]
        assert ShellAdapter._resolve_runner("test.r") == ["Rscript"]
        assert ShellAdapter._resolve_runner("test.R") == ["Rscript"]

    def test_unknown_extension(self):
        assert ShellAdapter._resolve_runner("test.xyz") is None
        assert ShellAdapter._resolve_runner("test") is None


class TestShellAdapterFormatArtifactText:
    def test_success(self):
        text = ShellAdapter.format_artifact_text("echo hi", 0, "hi\n", "", 10.5)
        assert "SUCCESS" in text
        assert "echo hi" in text
        assert "hi" in text
        assert "10.5ms" in text

    def test_failure(self):
        text = ShellAdapter.format_artifact_text("false", 1, "", "error\n", 5.0)
        assert "FAILURE" in text
        assert "error" in text

    def test_empty_stdout_stderr(self):
        text = ShellAdapter.format_artifact_text("cmd", 0, "", "", 1.0)
        assert "_(empty)_" in text


class TestShellAdapterFormatArtifactJson:
    def test_valid_json(self):
        result = ShellAdapter.format_artifact_json("echo hi", 0, "hi\n", "", 10.0)
        data = json.loads(result)
        assert data["command"] == "echo hi"
        assert data["status"] == "success"
        assert data["exit_code"] == 0
        assert data["stdout"] == "hi\n"
        assert data["duration_ms"] == 10.0

    def test_failure_status(self):
        result = ShellAdapter.format_artifact_json("cmd", 1, "", "err", 5.0)
        data = json.loads(result)
        assert data["status"] == "failure"
        assert data["exit_code"] == 1

    def test_has_timestamp(self):
        result = ShellAdapter.format_artifact_json("cmd", 0, "", "", 1.0)
        data = json.loads(result)
        assert "timestamp" in data
