"""Tests for multi_ai_cli.utils module."""

import configparser
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from multi_ai_cli.utils import (
    _make_continue_prompt,
    _tail_of,
    extract_code_block,
    open_editor_for_prompt,
    secure_resolve_path,
)


class TestSecureResolvePath:
    def setup_method(self):
        self.config = configparser.ConfigParser()
        self.tmpdir = tempfile.mkdtemp()
        self.config.add_section("Paths")
        self.config.set("Paths", "work_data", self.tmpdir)
        self.config.set("Paths", "work_efficient", self.tmpdir)

    def test_normal_path(self):
        result = secure_resolve_path("test.txt", "data", config=self.config)
        assert result == os.path.join(os.path.abspath(self.tmpdir), "test.txt")

    def test_efficient_category(self):
        result = secure_resolve_path("persona.txt", "efficient", config=self.config)
        assert result == os.path.join(os.path.abspath(self.tmpdir), "persona.txt")

    def test_traversal_blocked(self):
        with pytest.raises(PermissionError, match="Directory traversal"):
            secure_resolve_path("../../etc/passwd", "data", config=self.config)

    def test_no_config_raises(self):
        with pytest.raises(RuntimeError, match="config must be provided"):
            secure_resolve_path("file.txt", "data", config=None)

    def test_subdirectory(self):
        result = secure_resolve_path("sub/file.txt", "data", config=self.config)
        expected = os.path.join(os.path.abspath(self.tmpdir), "sub", "file.txt")
        assert result == expected

    def test_default_category(self):
        result = secure_resolve_path("file.txt", "unknown_category", config=self.config)
        # Falls back to work_data default
        assert "file.txt" in result


class TestTailOf:
    def test_short_text(self):
        assert _tail_of("hello", 10) == "hello"

    def test_exact_length(self):
        assert _tail_of("hello", 5) == "hello"

    def test_truncated(self):
        assert _tail_of("hello world", 5) == "world"

    def test_empty(self):
        assert _tail_of("", 5) == ""

    def test_zero_n(self):
        assert _tail_of("hello", 0) == "hello"


class TestMakeContinuePrompt:
    def test_contains_tail(self):
        result = _make_continue_prompt("last few chars")
        assert "last few chars" in result
        assert "truncated" in result
        assert "continuation" in result.lower()

    def test_contains_rules(self):
        result = _make_continue_prompt("tail")
        assert "Do NOT repeat" in result


class TestExtractCodeBlock:
    def test_single_block(self):
        text = "Some text\n```python\nprint('hello')\n```\nMore text"
        result = extract_code_block(text)
        assert result == "print('hello')"

    def test_multiple_blocks(self):
        text = "```\nblock1\n```\ntext\n```\nblock2\n```"
        result = extract_code_block(text)
        assert "block1" in result
        assert "block2" in result

    def test_no_code_blocks(self):
        text = "Just regular text without any code"
        result = extract_code_block(text)
        assert result == text

    def test_unclosed_block(self):
        text = "```python\nprint('hello')\n"
        result = extract_code_block(text)
        assert "print('hello')" in result

    def test_empty_code_block(self):
        text = "```\n```"
        result = extract_code_block(text)
        assert result == ""

    def test_no_triple_backtick(self):
        text = "plain text"
        result = extract_code_block(text)
        assert result == text


class TestOpenEditorForPrompt:
    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    def test_open_editor_success(self, mock_mkstemp, mock_run):
        mock_mkstemp.return_value = (1, "/tmp/test.md")
        mock_run.return_value = MagicMock(returncode=0)

        m = mock_open(
            read_data="# Header\n# ==================== END HEADER ====================\n\nHello World"
        )
        # Capture write calls to verify header is written
        write_handle = m.return_value

        with patch("builtins.open", m):
            # Mock os.fdopen to return the same mock_open handle for write
            with patch("os.fdopen", return_value=write_handle):
                with (
                    patch("os.close"),
                    patch("os.unlink"),
                    patch("os.path.exists", return_value=True),
                ):
                    result = open_editor_for_prompt()

        assert result == "Hello World"
        # Verify header was written
        write_handle.write.assert_any_call(
            "# ====================================================\n# Multi-AI CLI - Editor Mode\n# ====================================================\n# Write your prompt below. Lines starting with '#' are\n# ignored (treated as comments).\n#\n# Save and quit the editor to send your prompt.\n# Leave empty (or only comments) to cancel.\n# ==================== END HEADER ====================\n\n"
        )

    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    def test_open_editor_failure(self, mock_mkstemp, mock_run):
        mock_mkstemp.return_value = (1, "/tmp/test.md")
        mock_run.return_value = MagicMock(returncode=1)
        with patch("os.fdopen", mock_open()):
            with (
                patch("os.close"),
                patch("os.unlink"),
                patch("os.path.exists", return_value=True),
            ):
                result = open_editor_for_prompt()
        assert result is None

    @patch("subprocess.run")
    @patch("tempfile.mkstemp")
    def test_open_editor_empty_prompt(self, mock_mkstemp, mock_run):
        mock_mkstemp.return_value = (1, "/tmp/test.md")
        mock_run.return_value = MagicMock(returncode=0)
        content = "# ==================== END HEADER ====================\n\n\n"
        with patch("builtins.open", mock_open(read_data=content)):
            with patch("os.fdopen", mock_open()):
                with (
                    patch("os.close"),
                    patch("os.unlink"),
                    patch("os.path.exists", return_value=True),
                ):
                    result = open_editor_for_prompt()
        assert result is None
