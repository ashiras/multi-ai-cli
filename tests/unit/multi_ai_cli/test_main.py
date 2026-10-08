"""Tests for multi_ai_cli.main module."""

import pytest

from multi_ai_cli.main import (
    _create_file_if_missing,
    _ensure_directory,
    _extract_mode_arg,
    _read_interactive_input,
    _update_gitignore,
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


class TestWorkspaceUtils:
    def test_create_file_if_missing_creates(self, monkeypatch, tmp_path):
        target = tmp_path / "test.txt"
        monkeypatch.setattr(
            "os.path.exists", lambda path: path == str(target) and False
        )

        # Use actual open but in temp dir
        _create_file_if_missing(str(target), "content")
        assert target.exists()
        assert target.read_text() == "content"

    def test_create_file_if_missing_skips_existing(self, monkeypatch, tmp_path, capsys):
        target = tmp_path / "exists.txt"
        target.write_text("old")

        _create_file_if_missing(str(target), "new")
        assert target.read_text() == "old"
        captured = capsys.readouterr()
        assert "skip" in captured.out

    def test_ensure_directory_creates(self, monkeypatch, tmp_path):
        target = tmp_path / "new_dir"
        monkeypatch.setattr("os.path.isdir", lambda p: False)
        monkeypatch.setattr("os.path.exists", lambda p: False)

        # We need to mock os.makedirs to avoid actual filesystem calls if desired,
        # but for this test let's mock it to verify it's called.
        mock_makedirs = []
        monkeypatch.setattr("os.makedirs", lambda p: mock_makedirs.append(p))

        _ensure_directory(str(target))
        assert str(target) in mock_makedirs

    def test_ensure_directory_conflict(self, monkeypatch, tmp_path):
        target = tmp_path / "file.txt"
        target.write_text("content")

        with pytest.raises(RuntimeError, match="Path conflict"):
            _ensure_directory(str(target))

    def test_update_gitignore_creates_new(self, monkeypatch, tmp_path):
        d = tmp_path / "cwd"
        d.mkdir()
        target = d / ".gitignore"
        monkeypatch.chdir(d)
        monkeypatch.setattr("os.path.exists", lambda p: p == ".gitignore" and False)

        _update_gitignore()
        assert target.exists()
        assert "multi_ai_cli.ini" in target.read_text()

    def test_update_gitignore_appends(self, monkeypatch, tmp_path):
        d = tmp_path / "cwd"
        d.mkdir()
        target = d / ".gitignore"
        target.write_text("existing_file\n")
        monkeypatch.chdir(d)
        monkeypatch.setattr("os.path.exists", lambda p: p == ".gitignore" and True)
        monkeypatch.setattr("os.path.isfile", lambda p: True)

        _update_gitignore()
        content = target.read_text()
        assert "existing_file" in content
        assert "multi_ai_cli.ini" in content
        assert content.endswith("\n")

    def test_update_gitignore_idempotent(self, monkeypatch, tmp_path):
        d = tmp_path / "cwd"
        d.mkdir()
        target = d / ".gitignore"
        # Start with the expected content already present
        initial_content = (
            "# Multi-AI local/runtime files\nmulti_ai_cli.ini\nwork_data/\nlogs/\n"
        )
        target.write_text(initial_content)
        monkeypatch.chdir(d)
        monkeypatch.setattr("os.path.exists", lambda p: p == ".gitignore" and True)
        monkeypatch.setattr("os.path.isfile", lambda p: True)

        _update_gitignore()
        assert target.read_text() == initial_content

    def test_update_gitignore_no_trailing_newline(self, monkeypatch, tmp_path):
        d = tmp_path / "cwd"
        d.mkdir()
        target = d / ".gitignore"
        target.write_text("existing_file")
        monkeypatch.chdir(d)
        monkeypatch.setattr("os.path.exists", lambda p: p == ".gitignore" and True)
        monkeypatch.setattr("os.path.isfile", lambda p: True)

        _update_gitignore()
        content = target.read_text()
        assert content.endswith("\nlogs/\n")
        assert "existing_file\n\n# Multi-AI" in content
