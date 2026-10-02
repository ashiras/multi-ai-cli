"""Tests for multi_ai_cli.main module."""

import pytest

from multi_ai_cli.main import (
    _extract_mode_arg,
    _read_interactive_input,
)


class TestExtractModeArg:
    def test_no_mode(self):
        mode, remaining = _extract_mode_arg(["@gpt", "hello"])
        assert mode is None
        assert remaining == ["@gpt", "hello"]

    def test_mode_repl(self):
        mode, remaining = _extract_mode_arg(["--mode", "repl", "@gpt"])
        assert mode == "repl"
        assert remaining == ["@gpt"]

    def test_mode_filter(self):
        mode, remaining = _extract_mode_arg(["--mode", "filter", "@gpt"])
        assert mode == "filter"
        assert remaining == ["@gpt"]

    def test_mode_equals_syntax(self):
        mode, remaining = _extract_mode_arg(["--mode=repl", "@gpt"])
        assert mode == "repl"
        assert remaining == ["@gpt"]

    def test_invalid_mode(self):
        with pytest.raises(SystemExit):
            _extract_mode_arg(["--mode", "invalid"])

    def test_mode_missing_value(self):
        with pytest.raises(SystemExit):
            _extract_mode_arg(["--mode"])

    def test_mode_empty_equals(self):
        with pytest.raises(SystemExit):
            _extract_mode_arg(["--mode="])

    def test_duplicate_mode(self):
        with pytest.raises(SystemExit):
            _extract_mode_arg(["--mode", "repl", "--mode", "filter"])

    def test_case_insensitive(self):
        mode, _ = _extract_mode_arg(["--mode", "REPL"])
        assert mode == "repl"


class TestReadInteractiveInput:
    def test_single_line(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "hello world")
        result = _read_interactive_input()
        assert result == "hello world"

    def test_eof(self, monkeypatch):
        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        result = _read_interactive_input()
        assert result is None

    def test_continuation(self, monkeypatch):
        responses = iter(["first \\", "second"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = _read_interactive_input()
        assert result == "first  second"

    def test_multiple_continuations(self, monkeypatch):
        responses = iter(["a \\", "b \\", "c"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = _read_interactive_input()
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_continuation_eof(self, monkeypatch, capsys):
        call_count = 0

        def mock_input(_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "first \\"
            raise EOFError

        monkeypatch.setattr("builtins.input", mock_input)
        result = _read_interactive_input()
        assert result is None

    def test_empty_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = _read_interactive_input()
        assert result == ""

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "  hello  ")
        result = _read_interactive_input()
        assert result == "hello"
