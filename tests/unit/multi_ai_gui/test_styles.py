from __future__ import annotations

from multi_ai_gui.styles import DARK_STYLESHEET


def test_dark_stylesheet_is_non_empty():
    assert isinstance(DARK_STYLESHEET, str)
    assert len(DARK_STYLESHEET) > 0


def test_dark_stylesheet_contains_essential_components():
    assert "QMainWindow" in DARK_STYLESHEET
    assert "QPushButton" in DARK_STYLESHEET
    assert "QTreeWidget" in DARK_STYLESHEET
