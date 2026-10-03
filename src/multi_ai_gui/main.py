"""
Application startup module for the Multi-AI GUI.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from multi_ai_gui.constants import ensure_app_directories
from multi_ai_gui.styles import DARK_STYLESHEET
from multi_ai_gui.window import MainWindow


def main() -> None:
    """Run the GUI application."""
    ensure_app_directories()

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
