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
