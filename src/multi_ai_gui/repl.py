"""
REPL-related helpers for launching the Multi-AI CLI.
"""

from __future__ import annotations

import os
import sys

from multi_ai_gui.constants import CLI_DIR


def get_multi_ai_repl_command() -> tuple[str, list[str], str]:
    """Return program, arguments, and working directory for the CLI REPL."""
    if getattr(sys, "frozen", False):
        executable_dir = os.path.dirname(sys.executable)

        program = os.path.join(
            executable_dir,
            "multi-ai",
        )

        return (
            program,
            ["--mode", "repl"],
            executable_dir,
        )

    return (
        "uv",
        [
            "run",
            "multi-ai",
            "--mode",
            "repl",
        ],
        CLI_DIR,
    )
