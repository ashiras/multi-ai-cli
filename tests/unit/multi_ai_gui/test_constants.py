from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from multi_ai_gui import constants


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hello", False),
        ("\x1b[31mred\x1b[0m", True),
        ("\x1b[1;32mbold green\x1b[0m", True),
        ("plain text", False),
        ("\x1b[Kclear line", True),
        ("\x1b[1Acursor up", True),
    ],
)
def test_ansi_escape_re(text, expected):
    assert bool(constants.ANSI_ESCAPE_RE.search(text)) == expected


def test_constants_are_defined():
    assert isinstance(constants.CLI_DIR, str)
    assert isinstance(constants.PROMPTS_DIR, str)
    assert isinstance(constants.WORK_DATA_DIR, str)
    assert isinstance(constants.PROMPTS_DIR_ABS, str)
    assert isinstance(constants.WORK_DATA_DIR_ABS, str)
    assert isinstance(constants.ANSI_ESCAPE_RE, re.Pattern)
    assert isinstance(constants.PAUSE_PROMPT, str)
    assert isinstance(constants.RESULT_SAVED_MARKER, str)


def test_ensure_app_directories_creates_dirs(tmp_path, monkeypatch):
    prompts = tmp_path / "prompts"
    work = tmp_path / "work"

    monkeypatch.setattr(constants, "PROMPTS_DIR", str(prompts))
    monkeypatch.setattr(constants, "WORK_DATA_DIR", str(work))

    constants.ensure_app_directories()

    assert prompts.exists() and prompts.is_dir()
    assert work.exists() and work.is_dir()

    # 2回呼んでもエラーにならない
    constants.ensure_app_directories()


def test_ensure_app_directories_raises_on_oserror(monkeypatch):
    with patch("multi_ai_gui.constants.os.makedirs") as mock_makedirs:
        mock_makedirs.side_effect = OSError("Permission denied")
        with pytest.raises(OSError, match="Permission denied"):
            constants.ensure_app_directories()
