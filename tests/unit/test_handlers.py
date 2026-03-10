from unittest.mock import MagicMock, mock_open, patch

import pytest

from multi_ai_cli.adapters.shell import ParsedShInput, ShellAdapter
from multi_ai_cli.adapters.shell.adapter import ShellCommandBuildError
from multi_ai_cli.adapters.shell.models import ShellResult
from multi_ai_cli.handlers import (
    dispatch_command,
    handle_ai_interaction,
    handle_efficient,
    handle_scrub,
    handle_sequence,
    handle_sh,
)


@pytest.fixture(autouse=True)
def mock_engines_fixture():
    """Set up engines with mock engines for each test, clear after completion"""
    mock_engine = MagicMock()
    mock_engine.name = "TestEngine"
    mock_engine.model_name = "test-model"

    with patch("multi_ai_cli.handlers.engines", {"testengine": mock_engine}):
        yield {"testengine": mock_engine}


class TestDispatchCommand:
    def test_empty_parts_returns_false(self):
        with patch("multi_ai_cli.handlers.engines", {}):
            assert dispatch_command([]) is False

    def test_scrub_command(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with patch("builtins.print"):
            result = dispatch_command(["@scrub", "testengine"])
        assert result is True
        engine.scrub.assert_called_once()

    def test_flush_command(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with patch("builtins.print"):
            result = dispatch_command(["@flush"])
        assert result is True
        engine.scrub.assert_called_once()

    def test_efficient_command(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with (
            patch(
                "multi_ai_cli.handlers.secure_resolve_path",
                return_value="/fake/persona.txt",
            ),
            patch("builtins.open", mock_open(read_data="persona content")),
            patch("builtins.print"),
        ):
            result = dispatch_command(["@efficient", "testengine", "persona.txt"])
        assert result is True
        engine.load_persona.assert_called_with("persona content", "persona.txt")

    def test_sequence_command(self, mock_engines_fixture):
        with patch("multi_ai_cli.handlers.handle_sequence") as mock_seq:
            result = dispatch_command(["@sequence", "-e"])
        assert result is True
        mock_seq.assert_called_once_with(["@sequence", "-e"])

    def test_sh_command(self, mock_engines_fixture):
        with patch("multi_ai_cli.handlers.handle_sh", return_value=True) as mock_sh:
            result = dispatch_command(["@sh", "echo", "hi"])
        assert result is True
        mock_sh.assert_called_once_with(["@sh", "echo", "hi"])

    def test_ai_engine_command(self, mock_engines_fixture):
        with patch(
            "multi_ai_cli.handlers.handle_ai_interaction", return_value=True
        ) as mock_ai:
            result = dispatch_command(["@testengine", "hello"])
        assert result is True
        mock_ai.assert_called_once_with(["@testengine", "hello"])

    def test_unknown_command(self, mock_engines_fixture):
        with patch("multi_ai_cli.handlers.safe_print") as mock_safe_print:
            result = dispatch_command(["@unknown"])
        assert result is False
        # safe_print is called twice (error + list of available commands)
        assert mock_safe_print.call_count == 2
        assert "Unknown command" in mock_safe_print.call_args_list[0][0][0]


class TestHandleScrub:
    def test_scrub_specific_engine(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with patch("builtins.print") as mock_print:
            handle_scrub(["@scrub", "testengine"])
        engine.scrub.assert_called_once()
        mock_print.assert_any_call("[*] TestEngine memory scrubbed.")

    def test_scrub_all(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with patch("builtins.print"):
            handle_scrub(["@scrub"])
        engine.scrub.assert_called_once()

    def test_scrub_invalid_target(self, mock_engines_fixture):
        with patch("builtins.print") as mock_print:
            handle_scrub(["@scrub", "nonexistent"])
        assert any("Invalid target" in str(c) for c in mock_print.call_args_list)


class TestHandleEfficient:
    def test_load_persona_for_target(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with (
            patch(
                "multi_ai_cli.handlers.secure_resolve_path", return_value="/fake/p.txt"
            ),
            patch("builtins.open", mock_open(read_data="persona text")),
            patch("builtins.print"),
        ):
            handle_efficient(["@efficient", "testengine", "p.txt"])
        engine.load_persona.assert_called_with("persona text", "p.txt")

    def test_no_filename(self, mock_engines_fixture):
        with patch("builtins.print") as mock_print:
            handle_efficient(["@efficient"])
        assert any("Usage" in str(c) for c in mock_print.call_args_list)

    def test_load_persona_all(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        with (
            patch(
                "multi_ai_cli.handlers.secure_resolve_path", return_value="/fake/p.txt"
            ),
            patch("builtins.open", mock_open(read_data="persona")),
            patch("builtins.print"),
        ):
            handle_efficient(["@efficient", "persona.txt"])
        engine.load_persona.assert_called_once()


class TestHandleAiInteraction:
    def test_successful_interaction(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        engine.call.return_value = "AI response"

        with (
            patch("multi_ai_cli.handlers.build_ai_prompt", return_value="test prompt"),
            patch("multi_ai_cli.handlers.safe_print") as mock_safe_print,
            patch("multi_ai_cli.handlers.clear_thinking_line"),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print"),
        ):
            result = handle_ai_interaction(["@testengine", "-m", "Hello"])

        assert result is True
        engine.call.assert_called_once_with("test prompt")
        mock_safe_print.assert_any_call("\n--- TestEngine ---\nAI response\n")

    def test_empty_prompt(self, mock_engines_fixture):
        with (
            patch("multi_ai_cli.handlers.build_ai_prompt", return_value=""),
            patch("multi_ai_cli.handlers.safe_print") as mock_safe_print,
        ):
            result = handle_ai_interaction(["@testengine"])

        assert result is False
        assert any("No prompt" in str(c) for c in mock_safe_print.call_args_list)

    def test_engine_not_found(self):
        with (
            patch("multi_ai_cli.handlers.engines", {}),
            patch("multi_ai_cli.handlers.safe_print"),
        ):
            result = handle_ai_interaction(["@nonexistent", "hello"])
        assert result is False

    def test_with_write_file_raw(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        engine.call.return_value = "AI output"

        with (
            patch("multi_ai_cli.handlers.build_ai_prompt", return_value="prompt"),
            patch(
                "multi_ai_cli.handlers.secure_resolve_path",
                return_value="/fake/out.txt",
            ),
            patch("builtins.open", mock_open()),
            patch("multi_ai_cli.handlers.safe_print"),
            patch("multi_ai_cli.handlers.clear_thinking_line"),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print"),
            patch("os.fsync"),
        ):
            result = handle_ai_interaction(["@testengine", "-m", "hi", "-w", "out.txt"])

        assert result is True

    def test_engine_error(self, mock_engines_fixture):
        engine = mock_engines_fixture["testengine"]
        engine.call.side_effect = RuntimeError("API error")

        with (
            patch("multi_ai_cli.handlers.build_ai_prompt", return_value="prompt"),
            patch("multi_ai_cli.handlers.safe_print") as mock_safe_print,
            patch("multi_ai_cli.handlers.clear_thinking_line"),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print"),
        ):
            result = handle_ai_interaction(["@testengine", "-m", "hi"])

        assert result is False
        assert any("AI Engine Error" in str(c) for c in mock_safe_print.call_args_list)


class TestHandleSh:
    def test_successful_command(self, mock_engines_fixture):
        with (
            patch("multi_ai_cli.handlers._parse_sh_input") as mock_parse,
            patch.object(
                ShellAdapter,
                "build_command",
                return_value=(["echo", "Hello"], False),
            ),
            patch.object(
                ShellAdapter,
                "execute_command",
                return_value=ShellResult(
                    exit_code=0,
                    stdout="Hello",
                    stderr="",
                    duration_ms=1.2,
                    command_display="echo Hello",
                    use_shell=False,
                ),
            ),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print") as mock_print,
        ):
            mock_parse.return_value = ParsedShInput(command="echo Hello")
            result = handle_sh(["@sh", "echo", "Hello"])

        assert result is True
        assert any("SUCCESS" in str(c) for c in mock_print.call_args_list)

    def test_build_error(self, mock_engines_fixture):
        with (
            patch("multi_ai_cli.handlers._parse_sh_input") as mock_parse,
            patch.object(
                ShellAdapter,
                "build_command",
                side_effect=ShellCommandBuildError("bad command"),
            ),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print") as mock_print,
        ):
            mock_parse.return_value = ParsedShInput(command="bad")
            result = handle_sh(["@sh", "bad"])

        assert result is False
        assert any("bad command" in str(c) for c in mock_print.call_args_list)

    def test_timeout(self, mock_engines_fixture):
        import subprocess as sp

        with (
            patch("multi_ai_cli.handlers._parse_sh_input") as mock_parse,
            patch.object(
                ShellAdapter,
                "build_command",
                return_value=(["sleep", "999"], False),
            ),
            patch.object(
                ShellAdapter,
                "execute_command",
                side_effect=sp.TimeoutExpired(cmd="sleep", timeout=300),
            ),
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print") as mock_print,
        ):
            mock_parse.return_value = ParsedShInput(command="sleep 999")
            result = handle_sh(["@sh", "sleep", "999"])

        assert result is False
        assert any("timed out" in str(c) for c in mock_print.call_args_list)


class TestHandleSequence:
    def test_no_edit_flag(self, mock_engines_fixture):
        with patch("builtins.print") as mock_print:
            handle_sequence(["@sequence"])
        assert any("Usage" in str(c) for c in mock_print.call_args_list)

    def test_editor_returns_none(self, mock_engines_fixture):
        with patch("multi_ai_cli.handlers.open_editor_for_prompt", return_value=None):
            handle_sequence(["@sequence", "-e"])

    def test_single_step_success(self, mock_engines_fixture):
        # parse_sequence_steps returns list[list[list[str]]]
        parsed_steps = [[["@testengine", "hello"]]]

        with (
            patch(
                "multi_ai_cli.handlers.open_editor_for_prompt",
                return_value="@testengine hello",
            ),
            patch(
                "multi_ai_cli.handlers.parse_sequence_steps", return_value=parsed_steps
            ),
            patch(
                "multi_ai_cli.handlers.dispatch_command", return_value=True
            ) as mock_dispatch,
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print"),
        ):
            handle_sequence(["@sequence", "-e"])

        assert mock_dispatch.call_count == 1
        mock_dispatch.assert_called_once_with(["@testengine", "hello"])

    def test_step_failure_cascades(self, mock_engines_fixture):
        parsed_steps = [
            [["@testengine", "step1"]],
            [["@testengine", "step2"]],
        ]

        with (
            patch(
                "multi_ai_cli.handlers.open_editor_for_prompt", return_value="content"
            ),
            patch(
                "multi_ai_cli.handlers.parse_sequence_steps", return_value=parsed_steps
            ),
            patch(
                "multi_ai_cli.handlers.dispatch_command", return_value=False
            ) as mock_dispatch,
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print") as mock_print,
        ):
            handle_sequence(["@sequence", "-e"])

        # Fails at the first step -> second step is skipped
        assert mock_dispatch.call_count == 1
        assert any("Cascade Stop" in str(c) for c in mock_print.call_args_list)

    def test_parallel_tasks(self, mock_engines_fixture):
        # Two parallel tasks
        parsed_steps = [[["@testengine", "task1"], ["@testengine", "task2"]]]

        with (
            patch(
                "multi_ai_cli.handlers.open_editor_for_prompt", return_value="content"
            ),
            patch(
                "multi_ai_cli.handlers.parse_sequence_steps", return_value=parsed_steps
            ),
            patch(
                "multi_ai_cli.handlers.dispatch_command", return_value=True
            ) as mock_dispatch,
            patch("multi_ai_cli.handlers.logger"),
            patch("builtins.print"),
        ):
            handle_sequence(["@sequence", "-e"])

        assert mock_dispatch.call_count == 2

    def test_empty_steps_returns(self, mock_engines_fixture):
        with (
            patch(
                "multi_ai_cli.handlers.open_editor_for_prompt", return_value="content"
            ),
            patch("multi_ai_cli.handlers.parse_sequence_steps", return_value=[]),
            patch("builtins.print") as mock_print,
        ):
            handle_sequence(["@sequence", "-e"])
        assert any("No valid steps" in str(c) for c in mock_print.call_args_list)


class TestResolveRunner:
    def test_python_file(self):
        result = ShellAdapter._resolve_runner("script.py")
        assert result == ["python3"]

    def test_shell_file(self):
        result = ShellAdapter._resolve_runner("script.sh")
        assert result == ["bash"]

    def test_unknown_extension(self):
        result = ShellAdapter._resolve_runner("file.xyz")
        assert result is None

    def test_r_uppercase(self):
        result = ShellAdapter._resolve_runner("analysis.R")
        assert result == ["Rscript"]


class TestBuildShCommand:
    def setup_method(self):
        self.adapter = ShellAdapter()

    def test_direct_command(self):
        parsed = ParsedShInput(command="echo hello")
        cmd, use_shell = self.adapter.build_command(parsed)
        assert cmd == ["echo", "hello"]
        assert use_shell is False

    def test_shell_mode(self):
        parsed = ParsedShInput(command="echo $HOME | grep user", use_shell=True)
        cmd, use_shell = self.adapter.build_command(parsed)
        assert cmd == "echo $HOME | grep user"
        assert use_shell is True

    def test_both_command_and_file_error(self):
        parsed = ParsedShInput(command="echo hi", run_file="script.py")
        with pytest.raises(ShellCommandBuildError):
            self.adapter.build_command(parsed)

    def test_no_command_or_file(self):
        parsed = ParsedShInput()
        with pytest.raises(ShellCommandBuildError):
            self.adapter.build_command(parsed)

    def test_run_file_not_found(self):
        parsed = ParsedShInput(run_file="missing.py")
        with patch(
            "multi_ai_cli.adapters.shell.adapter.os.path.isfile",
            return_value=False,
        ):
            with pytest.raises(ShellCommandBuildError):
                self.adapter.build_command(parsed)


class TestFormatArtifact:
    def test_format_text_success(self):
        result = ShellAdapter.format_artifact_text("echo hi", 0, "hi\n", "", 5.2)
        assert "SUCCESS" in result
        assert "echo hi" in result
        assert "hi" in result

    def test_format_text_failure(self):
        result = ShellAdapter.format_artifact_text("bad", 1, "", "err\n", 10.0)
        assert "FAILURE" in result
        assert "err" in result

    def test_format_json(self):
        import json

        result = ShellAdapter.format_artifact_json("echo hi", 0, "hi\n", "", 5.2)
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["command"] == "echo hi"
        assert data["exit_code"] == 0


if __name__ == "__main__":
    pytest.main()
