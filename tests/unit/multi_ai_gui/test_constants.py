from __future__ import annotations

import re

from multi_ai_gui import constants


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
