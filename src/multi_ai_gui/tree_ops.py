"""
Tree widget helper functions for file and directory display.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


def collect_tree_expanded_paths(tree_widget: QTreeWidget) -> set[str]:
    """Collect expanded directory paths from a tree widget."""
    expanded: set[str] = set()

    def walk(item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(path, str) and os.path.isdir(path) and item.isExpanded():
            expanded.add(path)
        for i in range(item.childCount()):
            child = item.child(i)
            if child is not None:
                walk(child)

    for i in range(tree_widget.topLevelItemCount()):
        item = tree_widget.topLevelItem(i)
        if item is not None:
            walk(item)

    return expanded


def current_tree_selection_path(tree_widget: QTreeWidget) -> str | None:
    """Return current selected item path."""
    item = tree_widget.currentItem()
    if item is None:
        return None
    path = item.data(0, Qt.ItemDataRole.UserRole)
    return path if isinstance(path, str) else None


def find_tree_item_by_path(
    tree_widget: QTreeWidget, target_path: str
) -> QTreeWidgetItem | None:
    """Find a tree item by its stored path."""

    def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path == target_path:
            return item
        for i in range(item.childCount()):
            child = item.child(i)
            if child is None:
                continue
            found = walk(child)
            if found is not None:
                return found
        return None

    for i in range(tree_widget.topLevelItemCount()):
        item = tree_widget.topLevelItem(i)
        if item is None:
            continue
        found = walk(item)
        if found is not None:
            return found
    return None


def populate_tree(
    tree_widget: QTreeWidget,
    base_folder: str,
    expanded_paths: set[str] | None = None,
    selected_path: str | None = None,
) -> None:
    """Build tree items for the specified folder and populate the tree widget."""
    tree_widget.clear()

    item_to_select: QTreeWidgetItem | None = None

    def add_items(folder: str, parent_item: QTreeWidgetItem | None = None) -> None:
        nonlocal item_to_select
        try:
            items = sorted(os.listdir(folder))
        except OSError:
            return

        for item_name in items:
            if item_name.startswith("."):
                continue

            full_path = os.path.join(folder, item_name)
            is_dir = os.path.isdir(full_path)
            icon = "📂" if is_dir else "📄"
            display_text = f"{icon} {item_name}"

            tree_item = QTreeWidgetItem()
            tree_item.setText(0, display_text)
            tree_item.setData(0, Qt.ItemDataRole.UserRole, full_path)

            if parent_item is None:
                tree_widget.addTopLevelItem(tree_item)
            else:
                parent_item.addChild(tree_item)

            if selected_path == full_path:
                item_to_select = tree_item

            if is_dir:
                add_items(full_path, tree_item)
                if expanded_paths is None:
                    tree_item.setExpanded(True)
                else:
                    tree_item.setExpanded(full_path in expanded_paths)

    add_items(base_folder)

    if item_to_select is not None:
        tree_widget.setCurrentItem(item_to_select)
