from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QTreeWidget

from multi_ai_gui.tree_ops import (
    collect_tree_expanded_paths,
    current_tree_selection_path,
    find_tree_item_by_path,
    populate_tree,
)


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def tree_widget(qapp):
    del qapp
    return QTreeWidget()


def test_populate_tree_and_find_item(tmp_path, tree_widget):
    file_path = tmp_path / "a.txt"
    file_path.write_text("x")

    populate_tree(tree_widget, str(tmp_path))

    item = find_tree_item_by_path(tree_widget, str(file_path))
    assert item is not None
    assert "a.txt" in item.text(0)


def test_collect_expanded_paths(tmp_path, tree_widget):
    subdir = tmp_path / "dir1"
    subdir.mkdir()
    (subdir / "a.txt").write_text("x")

    populate_tree(tree_widget, str(tmp_path))

    item = find_tree_item_by_path(tree_widget, str(subdir))
    assert item is not None

    item.setExpanded(True)
    expanded = collect_tree_expanded_paths(tree_widget)

    assert str(subdir) in expanded


def test_current_tree_selection_path(tmp_path, tree_widget):
    file_path = tmp_path / "a.txt"
    file_path.write_text("x")

    populate_tree(tree_widget, str(tmp_path))

    item = find_tree_item_by_path(tree_widget, str(file_path))
    assert item is not None

    tree_widget.setCurrentItem(item)

    assert current_tree_selection_path(tree_widget) == str(file_path)


def test_populate_tree_selects_correct_path(tmp_path, tree_widget):
    file_path = tmp_path / "a.txt"
    file_path.write_text("x")

    populate_tree(tree_widget, str(tmp_path), selected_path=str(file_path))

    assert current_tree_selection_path(tree_widget) == str(file_path)


def test_populate_tree_handles_permission_error(tmp_path, tree_widget, monkeypatch):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "accessible.txt").write_text("ok")

    def mock_listdir(path):
        if "sub" in path:
            raise PermissionError
        return ["sub"]

    monkeypatch.setattr("os.listdir", mock_listdir)

    # Should not raise exception
    populate_tree(tree_widget, str(tmp_path))

    # Tree should still contain the root level item
    assert tree_widget.topLevelItemCount() > 0


def test_find_tree_item_by_path_nonexistent(tmp_path, tree_widget):
    populate_tree(tree_widget, str(tmp_path))
    assert find_tree_item_by_path(tree_widget, str(tmp_path / "ghost.txt")) is None
