"""
Reusable utility helpers for the Multi-AI GUI.
"""

from __future__ import annotations

import configparser
import os

from multi_ai_gui.constants import ANSI_ESCAPE_RE, INI_FILE_ABS


def get_dir_state(folder: str) -> set[str]:
    """Return the visible file and directory state under the specified folder."""
    state: set[str] = set()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [dir_name for dir_name in dirs if not dir_name.startswith(".")]

        for dir_name in dirs:
            state.add(os.path.join(root, dir_name))
        for file_name in files:
            if not file_name.startswith("."):
                state.add(os.path.join(root, file_name))
    return state


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return ANSI_ESCAPE_RE.sub("", text)


def get_logging_file_path() -> str | None:
    """
    Read logging target file path from multi_ai_cli.ini in the current working directory.

    Returns:
        Absolute path to the configured log file, or None when logging is disabled
        or the configuration is unavailable / incomplete.
    """
    if not os.path.exists(INI_FILE_ABS):
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(INI_FILE_ABS, encoding="utf-8")
    except (OSError, configparser.Error):
        return None

    if not parser.has_section("logging"):
        return None

    enabled = parser.getboolean("logging", "enabled", fallback=False)
    if not enabled:
        return None

    log_dir = parser.get("logging", "log_dir", fallback="").strip()
    base_filename = parser.get("logging", "base_filename", fallback="").strip()

    if not log_dir or not base_filename:
        return None

    return os.path.abspath(os.path.join(os.getcwd(), log_dir, base_filename))