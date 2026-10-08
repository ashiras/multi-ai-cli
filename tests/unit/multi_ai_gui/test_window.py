from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from multi_ai_gui.window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_main_window_initialization(qapp):
    win = MainWindow()
    assert win.windowTitle() != ""
    assert win.current_seq_file is None
    assert win.current_io_file is None
    assert hasattr(win, "process")
    # Verify tree is populated (top-level items exist)
    assert win.seq_tree.topLevelItemCount() > 0


def test_main_window_clear_log_view(qapp):
    win = MainWindow()
    win.log_view.setPlainText("some logs")
    assert win.log_view.toPlainText() == "some logs"
    win._on_clear()
    assert win.log_view.toPlainText() == ""


def test_main_window_clear_logging_view(qapp):
    win = MainWindow()
    win.logging_view.setPlainText("system logs")
    assert win.logging_view.toPlainText() == "system logs"
    win._on_clear_log_view()
    assert win.logging_view.toPlainText() == ""
