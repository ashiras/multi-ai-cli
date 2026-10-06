"""
Shared constants and path definitions for the Multi-AI GUI.

This module intentionally preserves the runtime behavior of the original
single-file prototype in work_data/main.py.
"""

from __future__ import annotations

import os
import re

CLI_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "multi-ai-cli"))
PROMPTS_DIR = "prompts"
WORK_DATA_DIR = "work_data"
INI_FILE = "multi_ai_cli.ini"

PROMPTS_DIR_ABS = os.path.abspath(PROMPTS_DIR)
WORK_DATA_DIR_ABS = os.path.abspath(WORK_DATA_DIR)
INI_FILE_ABS = os.path.abspath(INI_FILE)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

PAUSE_PROMPT = "[*] Press Enter to continue, or type 'q' to abort:"
RESULT_SAVED_MARKER = "[*] Result saved to '"


def ensure_app_directories() -> None:
    """Create application-managed directories if they do not already exist."""
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    os.makedirs(WORK_DATA_DIR, exist_ok=True)
