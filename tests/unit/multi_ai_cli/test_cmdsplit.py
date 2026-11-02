"""Tests for multi_ai_cli.cmdsplit module."""

import shlex
import types

import pytest

from multi_ai_cli import cmdsplit
from multi_ai_cli.adapters.shell.adapter import ShellAdapter
from multi_ai_cli.adapters.shell.models import ParsedShInput
from multi_ai_cli.cmdsplit import split_command


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(cmdsplit, "sys", types.SimpleNamespace(platform="win32"))


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(cmdsplit, "sys", types.SimpleNamespace(platform="linux"))


class TestSplitCommandNonWindows:
    def test_identical_to_shlex(self, linux):
        for text in [
            r"-r sub\x.md",
            r'@a "say \"hi\""',
            r"a\ b c",
            "@gpt hello -w out.md",
        ]:
            assert split_command(text) == shlex.split(text)

    def test_backslash_is_still_an_escape(self, linux):
        assert split_command(r"-r sub\x.md") == ["-r", "subx.md"]

    def test_unterminated_quote_raises(self, linux):
        with pytest.raises(ValueError):
            split_command('@a "unterminated')


class TestSplitCommandWindows:
    def test_relative_path_keeps_backslash(self, windows):
        assert split_command(r"-r sub\x.md") == ["-r", r"sub\x.md"]

    def test_drive_path_keeps_backslashes(self, windows):
        assert split_command(r"C:\Windows\notepad.exe") == [r"C:\Windows\notepad.exe"]

    def test_quoted_path_with_spaces(self, windows):
        text = r'"C:\Program Files\Editor\ed.exe" --wait'
        assert split_command(text) == [r"C:\Program Files\Editor\ed.exe", "--wait"]

    def test_escaped_quote_is_still_an_escape(self, windows):
        assert split_command(r'@a "say \"hi\""') == ["@a", 'say "hi"']

    def test_escaped_space_is_still_an_escape(self, windows):
        assert split_command(r"a\ b c") == ["a b", "c"]

    def test_escaped_backslash_is_still_an_escape(self, windows):
        assert split_command(r"a\\b") == [r"a\b"]

    def test_trailing_backslash_is_literal(self, windows):
        assert split_command("dir sub\\") == ["dir", "sub\\"]

    def test_plain_text_unchanged(self, windows):
        text = '@gpt "hello world" -w out.md'
        assert split_command(text) == shlex.split(text)

    def test_unterminated_quote_raises(self, windows):
        with pytest.raises(ValueError):
            split_command('@a "unterminated')

    def test_sh_command_survives_double_parse(self, windows):
        outer = split_command(r'@sh "dir C:\temp"')
        assert outer == ["@sh", r"dir C:\temp"]

        parsed = ParsedShInput(command=outer[1])
        cmd, use_shell = ShellAdapter().build_command(parsed)
        assert cmd == ["dir", r"C:\temp"]
        assert use_shell is False
