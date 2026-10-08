from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from multi_ai_gui.styles import DARK_STYLESHEET


# We mock QApplication to prevent actual UI instantiation during main() test
@patch("multi_ai_gui.main.QApplication")
@patch("multi_ai_gui.main.MainWindow")
@patch("multi_ai_gui.main.ensure_app_directories")
@patch("multi_ai_gui.main.sys.exit")
def test_main_execution_flow(mock_exit, mock_ensure_dirs, mock_window, mock_qapp):
    from multi_ai_gui.main import main

    # Mock the app instance returned by QApplication()
    mock_app_instance = MagicMock()
    mock_qapp.return_value = mock_app_instance

    # Run main
    main()

    # Verify ensure_app_directories was called
    mock_ensure_dirs.assert_called_once()

    # Verify QApplication was initialized with sys.argv
    mock_qapp.assert_called_once_with(sys.argv)

    # Verify stylesheet was set correctly
    mock_app_instance.setStyleSheet.assert_called_once_with(DARK_STYLESHEET)

    # Verify MainWindow was created and shown
    mock_window.assert_called_once()
    mock_window.return_value.showMaximized.assert_called_once()

    # Verify application loop execution
    mock_app_instance.exec.assert_called_once()
    mock_exit.assert_called_once()
