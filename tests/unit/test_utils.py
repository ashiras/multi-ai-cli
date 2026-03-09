import configparser
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from multi_ai_cli.utils import (
    MARKER,
    _get_cfg_int,
    _make_continue_prompt,
    _tail_of,
    clear_thinking_line,
    extract_code_block,
    open_editor_for_prompt,
    print_welcome_banner,
    safe_print,
    secure_resolve_path,
)


class TestSecureResolvePath:
    def test_valid_path(self, tmp_path):
        """Valid file names are resolved correctly"""
        cfg = configparser.ConfigParser()
        cfg.read_dict({"Paths": {"work_data": str(tmp_path)}})

        result = secure_resolve_path("file.txt", "data", config=cfg)
        expected = os.path.abspath(os.path.join(str(tmp_path), "file.txt"))
        assert result == expected

    def test_efficient_category(self, tmp_path):
        """The correct path is used for the 'efficient' category"""
        cfg = configparser.ConfigParser()
        cfg.read_dict({"Paths": {"work_efficient": str(tmp_path)}})

        result = secure_resolve_path("prompt.md", "efficient", config=cfg)
        expected = os.path.abspath(os.path.join(str(tmp_path), "prompt.md"))
        assert result == expected

    def test_directory_traversal_blocked(self, tmp_path):
        """Directory traversal results in PermissionError"""
        cfg = configparser.ConfigParser()
        cfg.read_dict({"Paths": {"work_data": str(tmp_path)}})

        with pytest.raises(PermissionError, match="Directory traversal blocked"):
            secure_resolve_path("../../etc/passwd", "data", config=cfg)

    def test_config_none_raises_runtime_error(self):
        """RuntimeError if config is None"""
        with pytest.raises(RuntimeError, match="config must be provided"):
            secure_resolve_path("file.txt", "data", config=None)

    def test_fallback_default_dir(self):
        """Fall back to default if Paths section is missing"""
        cfg = configparser.ConfigParser()
        result = secure_resolve_path("file.txt", "data", config=cfg)
        expected = os.path.abspath(os.path.join("work_data", "file.txt"))
        assert result == expected


class TestOpenEditorForPrompt:
    @patch("os.path.exists", return_value=True)
    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    @patch("os.fdopen")
    def test_successful_edit(
        self, mock_fdopen, mock_mkstemp, mock_run, mock_unlink, mock_exists
    ):
        """Returns string if content is written in editor"""
        mock_mkstemp.return_value = (5, "/tmp/ai_prompt_test.md")
        mock_fdopen.return_value.__enter__ = MagicMock()
        mock_fdopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value.returncode = 0

        file_content = f"{MARKER}\n\nHello AI, please help."
        m = mock_open(read_data=file_content)

        with patch("builtins.open", m), patch("builtins.print"):
            result = open_editor_for_prompt()

        assert result is not None
        assert "Hello AI, please help." in result

    @patch("os.path.exists", return_value=True)
    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    @patch("os.fdopen")
    def test_empty_content_returns_none(
        self, mock_fdopen, mock_mkstemp, mock_run, mock_unlink, mock_exists
    ):
        """None if editor content is empty"""
        mock_mkstemp.return_value = (5, "/tmp/ai_prompt_test.md")
        mock_fdopen.return_value.__enter__ = MagicMock()
        mock_fdopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value.returncode = 0

        file_content = f"{MARKER}\n\n"
        m = mock_open(read_data=file_content)

        with patch("builtins.open", m), patch("builtins.print"):
            result = open_editor_for_prompt()

        assert result is None

    @patch("os.path.exists", return_value=True)
    @patch("os.unlink")
    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    @patch("os.fdopen")
    def test_editor_nonzero_exit_returns_none(
        self, mock_fdopen, mock_mkstemp, mock_run, mock_unlink, mock_exists
    ):
        """None if editor exits with non-zero status"""
        mock_mkstemp.return_value = (5, "/tmp/ai_prompt_test.md")
        mock_fdopen.return_value.__enter__ = MagicMock()
        mock_fdopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value.returncode = 1

        with patch("builtins.print"):
            result = open_editor_for_prompt()

        assert result is None

    @patch("os.path.exists", return_value=False)
    @patch("tempfile.mkstemp", side_effect=FileNotFoundError("editor not found"))
    def test_editor_not_found(self, mock_mkstemp, mock_exists):
        """None if editor is not found"""
        with patch("builtins.print"):
            result = open_editor_for_prompt()

        assert result is None


class TestSafePrint:
    @patch("builtins.print")
    def test_safe_print_calls_print(self, mock_print):
        safe_print("hello", "world")
        mock_print.assert_called_once_with("hello", "world")

    @patch("builtins.print")
    def test_safe_print_with_kwargs(self, mock_print):
        safe_print("test", end="\n", flush=True)
        mock_print.assert_called_once_with("test", end="\n", flush=True)


class TestClearThinkingLine:
    @patch("builtins.print")
    @patch("shutil.get_terminal_size")
    def test_clears_line(self, mock_terminal_size, mock_print):
        mock_terminal_size.return_value = os.terminal_size((80, 20))
        clear_thinking_line()
        mock_print.assert_called_once_with(" " * 79, end="\r", flush=True)


class TestExtractCodeBlock:
    def test_with_code_block(self):
        text = "Some text\n```\nprint('hello')\n```\nMore text"
        result = extract_code_block(text)
        assert "print('hello')" in result
        assert "Some text" not in result

    def test_multiple_code_blocks(self):
        text = "```\nblock1\n```\ntext\n```\nblock2\n```"
        result = extract_code_block(text)
        assert "block1" in result
        assert "block2" in result

    def test_no_code_block(self):
        text = "This is just plain text."
        result = extract_code_block(text)
        assert result == text

    def test_unclosed_code_block(self):
        text = "`\nsome code\nmore code"
        result = extract_code_block(text)
        assert "some code" in result


class TestGetCfgInt:
    def test_valid_int(self):
        cfg = configparser.ConfigParser()
        cfg.read_dict({"section": {"key": "42"}})
        assert _get_cfg_int(cfg, "section", "key", 10) == 42

    def test_fallback_on_missing(self):
        cfg = configparser.ConfigParser()
        assert _get_cfg_int(cfg, "section", "key", 99) == 99

    def test_fallback_on_invalid(self):
        cfg = configparser.ConfigParser()
        cfg.read_dict({"section": {"key": "not_a_number"}})
        assert _get_cfg_int(cfg, "section", "key", 99) == 99


class TestMakeContinuePrompt:
    def test_contains_tail(self):
        result = _make_continue_prompt("last line of output")
        assert "last line of output" in result
        assert "Continue EXACTLY" in result


class TestTailOf:
    def test_shorter_than_n(self):
        assert _tail_of("abc", 10) == "abc"

    def test_longer_than_n(self):
        assert _tail_of("abcdefgh", 3) == "fgh"

    def test_empty_string(self):
        assert _tail_of("", 5) == ""


class TestPrintWelcomeBanner:
    @patch("builtins.print")
    def test_prints_banner(self, mock_print):
        mock_engine = MagicMock()
        mock_engine.name = "GPT"
        mock_engine.model_name = "gpt-4o-mini"
        engines = {"gpt": mock_engine}

        print_welcome_banner(engines, is_log_enabled=True)

        output = "".join(str(c) for c in mock_print.call_args_list)
        assert "Multi-AI CLI" in output
        assert "GPT" in output


if __name__ == "__main__":
    pytest.main()
