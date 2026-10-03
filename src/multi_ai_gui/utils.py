"""
Reusable utility helpers for the Multi-AI GUI.
"""

from __future__ import annotations

import os

from multi_ai_gui.constants import ANSI_ESCAPE_RE


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
