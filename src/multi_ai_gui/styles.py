"""
Central stylesheet definitions for the Multi-AI GUI.

This stylesheet is copied from the original prototype to preserve the exact
mock UI appearance.
"""

from __future__ import annotations

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
}
QSplitter::handle {
    background-color: #3c3c3c;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    padding: 4px 12px;
    font-size: 10pt;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:pressed {
    background-color: #0d5689;
}
QPushButton:disabled {
    background-color: #3a3d41;
    color: #8a8a8a;
}
QLabel {
    color: #858585;
    font-size: 10pt;
    font-weight: bold;
}
QLabel[pathLabel="true"] {
    color: #6a9955;
    font-size: 9pt;
    font-weight: normal;
    padding-left: 2px;
    padding-bottom: 4px;
}
QLabel[editingLabel="true"] {
    color: #9cdcfe;
    font-size: 9pt;
    font-weight: normal;
    padding-left: 2px;
    padding-bottom: 4px;
}
QTreeWidget {
    background-color: #252526;
    color: #cccccc;
    border: none;
    font-size: 10pt;
}
QTreeWidget::item {
    height: 30px;
}
QTreeWidget::item:selected {
    background-color: #094771;
}
QTreeWidget::item:hover {
    background-color: #2a2d2e;
}
QPlainTextEdit {
    border: none;
    font-size: 11pt;
}
QStatusBar {
    background-color: #252526;
    color: #cccccc;
}
"""
