"""
Main window implementation for the Multi-AI GUI.

This module preserves the behavior and UI structure of the original
single-file prototype in work_data/main.py while separating the code
into smaller modules.
"""

from __future__ import annotations

import os
import shutil
from typing import override

from PySide6.QtCore import QPoint, QProcess, QProcessEnvironment, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFontDatabase,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multi_ai_gui.constants import (
    PAUSE_PROMPT,
    PROMPTS_DIR,
    PROMPTS_DIR_ABS,
    RESULT_SAVED_MARKER,
    WORK_DATA_DIR,
    WORK_DATA_DIR_ABS,
)
from multi_ai_gui.repl import get_multi_ai_repl_command
from multi_ai_gui.tree_ops import (
    collect_tree_expanded_paths,
    current_tree_selection_path,
    find_tree_item_by_path,
    populate_tree,
)
from multi_ai_gui.utils import get_dir_state, strip_ansi


class MainWindow(QMainWindow):
    """Main application window that provides a PySide6 frontend for Multi-AI CLI."""

    def __init__(self) -> None:
        """Initialize the main window and start the REPL session."""
        super().__init__()
        self.setWindowTitle("multi-ai-cli IDE")

        self.current_seq_file: str | None = None
        self.current_io_file: str | None = None
        self.last_prompts_state: set[str] = get_dir_state(PROMPTS_DIR)
        self.last_work_data_state: set[str] = get_dir_state(WORK_DATA_DIR)

        self.process: QProcess | None = None
        self._stdout_buffer = ""
        self._pause_waiting = False
        self._last_output_had_newline = True
        self._last_result_saved_line: str | None = None

        self._build_ui()
        self._start_repl_session()
        self._start_polling_timer()

    # ---- UI construction ----

    def _build_ui(self) -> None:
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        # ---------- Left panel: SEQUENCES ----------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QHBoxLayout()
        left_label = QLabel("SEQUENCES")
        left_header.addWidget(left_label)
        left_header.addStretch()

        self.btn_new_seq = QPushButton("New")
        self.btn_new_seq.clicked.connect(self._on_new_seq)
        left_header.addWidget(self.btn_new_seq)

        self.btn_refresh_seq = QPushButton("↻")
        self.btn_refresh_seq.setFixedSize(30, 26)
        self.btn_refresh_seq.clicked.connect(self._on_refresh_seq)
        left_header.addWidget(self.btn_refresh_seq)

        left_layout.addLayout(left_header)

        self.seq_path_label = QLabel(PROMPTS_DIR_ABS)
        self.seq_path_label.setProperty("pathLabel", "true")
        self.seq_path_label.setWordWrap(True)
        self.seq_path_label.setToolTip(PROMPTS_DIR_ABS)
        left_layout.addWidget(self.seq_path_label)

        self.seq_tree = QTreeWidget()
        self.seq_tree.setHeaderHidden(True)
        self.seq_tree.itemClicked.connect(self._on_seq_tree_clicked)
        self.seq_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.seq_tree.customContextMenuRequested.connect(self._show_seq_context_menu)
        populate_tree(self.seq_tree, PROMPTS_DIR)
        left_layout.addWidget(self.seq_tree)
        left_widget.setStyleSheet("background-color: #252526;")

        # ---------- Middle panel (top: FLOW, bottom: TERMINAL) ----------
        mid_top_widget = QWidget()
        mid_top_layout = QVBoxLayout(mid_top_widget)
        mid_top_layout.setContentsMargins(0, 0, 0, 0)

        mid_top_header = QHBoxLayout()
        mid_top_label = QLabel("FLOW DEFINITION")
        mid_top_header.addWidget(mid_top_label)
        mid_top_header.addStretch()

        self.btn_update_seq = QPushButton("Update")
        self.btn_update_seq.clicked.connect(self._on_update_seq)
        mid_top_header.addWidget(self.btn_update_seq)

        self.btn_send = QPushButton("Send")
        self.btn_send.clicked.connect(self._on_send)
        mid_top_header.addWidget(self.btn_send)

        self.btn_run_sequence = QPushButton("Run Sequence")
        self.btn_run_sequence.clicked.connect(self._on_run_sequence)
        mid_top_header.addWidget(self.btn_run_sequence)

        self.btn_restart_repl = QPushButton("Restart REPL")
        self.btn_restart_repl.clicked.connect(self._on_restart_repl)
        mid_top_header.addWidget(self.btn_restart_repl)

        mid_top_layout.addLayout(mid_top_header)

        self.editing_seq_label = QLabel("Editing: <new file>")
        self.editing_seq_label.setProperty("editingLabel", "true")
        self.editing_seq_label.setWordWrap(True)
        mid_top_layout.addWidget(self.editing_seq_label)

        self.flow_edit = QPlainTextEdit()
        self.flow_edit.setStyleSheet("background-color: #1e1e1e; color: #dcdcaa;")
        self.flow_edit.setFont(fixed_font)
        mid_top_layout.addWidget(self.flow_edit)

        # -- Terminal --
        mid_bot_widget = QWidget()
        mid_bot_layout = QVBoxLayout(mid_bot_widget)
        mid_bot_layout.setContentsMargins(0, 0, 0, 0)

        mid_bot_header = QHBoxLayout()
        mid_bot_label = QLabel("TERMINAL")
        mid_bot_header.addWidget(mid_bot_label)
        mid_bot_header.addStretch()

        self.btn_continue = QPushButton("Continue")
        self.btn_continue.setEnabled(False)
        self.btn_continue.clicked.connect(self._on_continue_pause)
        mid_bot_header.addWidget(self.btn_continue)

        self.btn_abort = QPushButton("Abort")
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self._on_abort_pause)
        mid_bot_header.addWidget(self.btn_abort)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._on_clear)
        mid_bot_header.addWidget(self.btn_clear)

        mid_bot_layout.addLayout(mid_bot_header)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.log_view.setFont(fixed_font)
        mid_bot_layout.addWidget(self.log_view)

        mid_splitter = QSplitter(Qt.Orientation.Vertical)
        mid_splitter.addWidget(mid_top_widget)
        mid_splitter.addWidget(mid_bot_widget)
        mid_splitter.setStretchFactor(0, 3)
        mid_splitter.setStretchFactor(1, 10)

        # ---------- Right panel (top: I/O FILES, bottom: FILE PREVIEW) ----------
        right_top_widget = QWidget()
        right_top_layout = QVBoxLayout(right_top_widget)
        right_top_layout.setContentsMargins(0, 0, 0, 0)

        right_top_header = QHBoxLayout()
        right_top_label = QLabel("I/O FILES")
        right_top_header.addWidget(right_top_label)
        right_top_header.addStretch()

        self.btn_refresh_io = QPushButton("↻ Refresh")
        self.btn_refresh_io.clicked.connect(self._on_refresh_io)
        right_top_header.addWidget(self.btn_refresh_io)

        right_top_layout.addLayout(right_top_header)

        self.io_path_label = QLabel(WORK_DATA_DIR_ABS)
        self.io_path_label.setProperty("pathLabel", "true")
        self.io_path_label.setWordWrap(True)
        self.io_path_label.setToolTip(WORK_DATA_DIR_ABS)
        right_top_layout.addWidget(self.io_path_label)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemClicked.connect(self._on_file_tree_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_io_context_menu)
        self.file_tree.setStyleSheet(
            "QTreeWidget { background-color: #2d2d2d; color: #cccccc; }"
        )
        populate_tree(self.file_tree, WORK_DATA_DIR)
        right_top_layout.addWidget(self.file_tree)

        right_bot_widget = QWidget()
        right_bot_layout = QVBoxLayout(right_bot_widget)
        right_bot_layout.setContentsMargins(0, 0, 0, 0)

        right_bot_header = QHBoxLayout()
        right_bot_label = QLabel("FILE PREVIEW")
        right_bot_header.addWidget(right_bot_label)
        right_bot_header.addStretch()

        self.btn_update_io = QPushButton("Update")
        self.btn_update_io.clicked.connect(self._on_update_io_file)
        right_bot_header.addWidget(self.btn_update_io)

        right_bot_layout.addLayout(right_bot_header)

        self.file_view = QPlainTextEdit()
        self.file_view.setStyleSheet("background-color: #1e1e1e; color: #9cdcfe;")
        self.file_view.setFont(fixed_font)
        right_bot_layout.addWidget(self.file_view)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(right_top_widget)
        right_splitter.addWidget(right_bot_widget)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)

        # ---------- Assemble main horizontal splitter ----------
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(mid_splitter)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 2)

        self.setCentralWidget(main_splitter)

        # ---------- Status bar ----------
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.repl_status_label = QLabel("REPL: Starting...")
        self.status_bar.addPermanentWidget(self.repl_status_label)
        self._set_repl_status("Starting...", "#dcdcaa")

    # ---- Status ----

    def _set_repl_status(self, text: str, color: str) -> None:
        self.repl_status_label.setText(f"REPL: {text}")
        self.repl_status_label.setStyleSheet(
            f"color: {color}; font-size: 10pt; font-weight: bold;"
        )

    def _set_pause_waiting(self, waiting: bool) -> None:
        """Update GUI controls for the REPL @pause waiting state."""
        self._pause_waiting = waiting
        self.btn_continue.setEnabled(waiting)
        self.btn_abort.setEnabled(waiting)

        process_running = (
            self.process is not None
            and self.process.state() == QProcess.ProcessState.Running
        )
        self.btn_send.setEnabled(process_running and not waiting)
        self.btn_run_sequence.setEnabled(process_running and not waiting)

        if waiting:
            self._set_repl_status("Paused", "#dcdcaa")
        elif process_running:
            self._set_repl_status("Running", "#4ec9b0")

    def _set_editing_seq_label(self) -> None:
        if self.current_seq_file:
            rel_path = os.path.relpath(self.current_seq_file, os.getcwd())
            self.editing_seq_label.setText(f"Editing: {rel_path}")
            self.editing_seq_label.setToolTip(self.current_seq_file)
        else:
            self.editing_seq_label.setText("Editing: <new file>")
            self.editing_seq_label.setToolTip("No existing sequence file selected")

    # ---- Sequence editing helpers ----

    def _clear_seq_selection(self) -> None:
        self.seq_tree.clearSelection()
        self.current_seq_file = None
        self._set_editing_seq_label()

    def _select_seq_file(self, path: str) -> None:
        item = find_tree_item_by_path(self.seq_tree, path)
        if item is not None:
            self.seq_tree.setCurrentItem(item)
            item.setSelected(True)
        self.current_seq_file = path
        self._set_editing_seq_label()

    def _save_new_sequence_file(self) -> str | None:
        file_name, ok = QInputDialog.getText(
            self,
            "Create Sequence File",
            "Enter new sequence file name:",
        )
        if not ok:
            return None

        file_name = file_name.strip()
        if not file_name:
            QMessageBox.warning(self, "Invalid File Name", "File name cannot be empty.")
            return None

        target_path = os.path.abspath(os.path.join(PROMPTS_DIR, file_name))
        prompts_root = os.path.abspath(PROMPTS_DIR)

        if not (
            target_path == prompts_root or target_path.startswith(prompts_root + os.sep)
        ):
            QMessageBox.warning(
                self,
                "Invalid File Name",
                "File name must stay within the prompts directory.",
            )
            return None

        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)

        if os.path.exists(target_path):
            reply = QMessageBox.question(
                self,
                "Overwrite Existing File",
                f"{os.path.relpath(target_path, os.getcwd())} already exists.\nOverwrite it?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return None

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(self.flow_edit.toPlainText())

        expanded = collect_tree_expanded_paths(self.seq_tree)
        abs_prompts_root = os.path.abspath(PROMPTS_DIR)
        parent_path = os.path.dirname(target_path)
        while parent_path.startswith(abs_prompts_root):
            expanded.add(parent_path)
            if parent_path == abs_prompts_root:
                break
            next_parent = os.path.dirname(parent_path)
            if next_parent == parent_path:
                break
            parent_path = next_parent

        populate_tree(self.seq_tree, PROMPTS_DIR, expanded, target_path)
        self.last_prompts_state = get_dir_state(PROMPTS_DIR)
        self._select_seq_file(target_path)
        return target_path

    def _save_current_sequence(self) -> str | None:
        flow_data = self.flow_edit.toPlainText()
        if not flow_data.strip():
            QMessageBox.warning(self, "Empty Flow", "FLOW DEFINITION is empty.")
            return None

        if self.current_seq_file:
            with open(self.current_seq_file, "w", encoding="utf-8") as f:
                f.write(flow_data)
            self._set_editing_seq_label()
            self.last_prompts_state = get_dir_state(PROMPTS_DIR)
            return self.current_seq_file

        return self._save_new_sequence_file()

    def _build_sequence_run_command(self, seq_file_path: str) -> str:
        relative_path = os.path.relpath(
            os.path.abspath(seq_file_path), os.path.abspath(PROMPTS_DIR)
        )
        return f"@sequence -f {relative_path}"

    # ---- Generic tree file operations ----

    def _path_within_root(self, path: str, root: str) -> bool:
        abs_path = os.path.abspath(path)
        abs_root = os.path.abspath(root)
        return abs_path == abs_root or abs_path.startswith(abs_root + os.sep)

    def _rename_path(self, old_path: str, root_dir: str) -> str | None:
        old_path = os.path.abspath(old_path)
        if not self._path_within_root(old_path, root_dir):
            QMessageBox.warning(
                self, "Rename Failed", "Target is outside the allowed root directory."
            )
            return None

        old_name = os.path.basename(old_path)
        parent_dir = os.path.dirname(old_path)

        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            "Enter new name:",
            text=old_name,
        )
        if not ok:
            return None

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Name cannot be empty.")
            return None

        if (
            new_name in (".", "..")
            or os.sep in new_name
            or (os.altsep and os.altsep in new_name)
        ):
            QMessageBox.warning(
                self, "Invalid Name", "Please enter a simple file or directory name."
            )
            return None

        new_path = os.path.abspath(os.path.join(parent_dir, new_name))
        if not self._path_within_root(new_path, root_dir):
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Renamed path must stay within the root directory.",
            )
            return None

        if new_path == old_path:
            return old_path

        if os.path.exists(new_path):
            QMessageBox.warning(
                self,
                "Rename Failed",
                "A file or directory with that name already exists.",
            )
            return None

        try:
            os.rename(old_path, new_path)
            return new_path
        except OSError as exc:
            QMessageBox.critical(self, "Rename Failed", str(exc))
            return None

    def _delete_path(self, target_path: str, root_dir: str) -> bool:
        target_path = os.path.abspath(target_path)
        abs_root = os.path.abspath(root_dir)

        if target_path == abs_root:
            QMessageBox.warning(
                self, "Delete Blocked", "The root directory itself cannot be deleted."
            )
            return False

        if not self._path_within_root(target_path, root_dir):
            QMessageBox.warning(
                self, "Delete Failed", "Target is outside the allowed root directory."
            )
            return False

        rel_path = os.path.relpath(target_path, os.getcwd())
        if os.path.isdir(target_path):
            message = f"Delete directory and all contents?\n\n{rel_path}"
        else:
            message = f"Delete file?\n\n{rel_path}"

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            return True
        except OSError as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))
            return False

    def _refresh_seq_tree_preserve(self, selected_path: str | None = None) -> None:
        expanded = collect_tree_expanded_paths(self.seq_tree)
        target_selected = (
            selected_path if selected_path is not None else self.current_seq_file
        )
        populate_tree(self.seq_tree, PROMPTS_DIR, expanded, target_selected)
        self.last_prompts_state = get_dir_state(PROMPTS_DIR)

    def _refresh_io_tree_preserve(self, selected_path: str | None = None) -> None:
        expanded = collect_tree_expanded_paths(self.file_tree)
        current_selected = current_tree_selection_path(self.file_tree)
        target_selected = (
            selected_path if selected_path is not None else current_selected
        )
        populate_tree(self.file_tree, WORK_DATA_DIR, expanded, target_selected)
        self.last_work_data_state = get_dir_state(WORK_DATA_DIR)

    def _handle_seq_rename(self, old_path: str) -> None:
        new_path = self._rename_path(old_path, PROMPTS_DIR)
        if new_path is None:
            return

        if self.current_seq_file:
            current_abs = os.path.abspath(self.current_seq_file)
            old_abs = os.path.abspath(old_path)
            if current_abs == old_abs:
                self.current_seq_file = new_path
            elif current_abs.startswith(old_abs + os.sep):
                relative_tail = os.path.relpath(current_abs, old_abs)
                self.current_seq_file = os.path.join(new_path, relative_tail)

        self._refresh_seq_tree_preserve(new_path)
        self._set_editing_seq_label()

    def _handle_seq_delete(self, target_path: str) -> None:
        deleting_abs = os.path.abspath(target_path)
        if not self._delete_path(target_path, PROMPTS_DIR):
            return

        if self.current_seq_file:
            current_abs = os.path.abspath(self.current_seq_file)
            if current_abs == deleting_abs or current_abs.startswith(
                deleting_abs + os.sep
            ):
                self.current_seq_file = None
                self.flow_edit.clear()
                self._set_editing_seq_label()

        self._refresh_seq_tree_preserve(None)

    def _handle_io_rename(self, old_path: str) -> None:
        new_path = self._rename_path(old_path, WORK_DATA_DIR)
        if new_path is None:
            return

        if self.current_io_file:
            current_abs = os.path.abspath(self.current_io_file)
            old_abs = os.path.abspath(old_path)
            if current_abs == old_abs:
                self.current_io_file = new_path
            elif current_abs.startswith(old_abs + os.sep):
                relative_tail = os.path.relpath(current_abs, old_abs)
                self.current_io_file = os.path.join(new_path, relative_tail)

        self._refresh_io_tree_preserve(new_path)

    def _handle_io_delete(self, target_path: str) -> None:
        deleting_abs = os.path.abspath(target_path)
        if not self._delete_path(target_path, WORK_DATA_DIR):
            return

        if self.current_io_file:
            current_abs = os.path.abspath(self.current_io_file)
            if current_abs == deleting_abs or current_abs.startswith(
                deleting_abs + os.sep
            ):
                self.current_io_file = None
                self.file_view.clear()

        self._refresh_io_tree_preserve(None)

    # ---- Context menus ----

    def _show_seq_context_menu(self, pos: QPoint) -> None:
        item = self.seq_tree.itemAt(pos)
        if item is None:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return

        self.seq_tree.setCurrentItem(item)
        item.setSelected(True)

        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        delete_action = QAction("Delete", self)

        rename_action.triggered.connect(lambda: self._handle_seq_rename(path))
        delete_action.triggered.connect(lambda: self._handle_seq_delete(path))

        menu.addAction(rename_action)
        menu.addAction(delete_action)
        menu.exec(self.seq_tree.viewport().mapToGlobal(pos))

    def _show_io_context_menu(self, pos: QPoint) -> None:
        item = self.file_tree.itemAt(pos)
        if item is None:
            return

        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return

        self.file_tree.setCurrentItem(item)
        item.setSelected(True)

        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        delete_action = QAction("Delete", self)

        rename_action.triggered.connect(lambda: self._handle_io_rename(path))
        delete_action.triggered.connect(lambda: self._handle_io_delete(path))

        menu.addAction(rename_action)
        menu.addAction(delete_action)
        menu.exec(self.file_tree.viewport().mapToGlobal(pos))

    # ---- REPL / process management ----

    def _start_repl_session(self) -> None:
        if self.process is not None:
            try:
                self.process.readyReadStandardOutput.disconnect(
                    self._on_ready_read_stdout
                )
            except Exception:
                pass
            try:
                self.process.finished.disconnect(self._on_process_finished)
            except Exception:
                pass
            try:
                self.process.errorOccurred.disconnect(self._on_process_error)
            except Exception:
                pass
            try:
                self.process.started.disconnect(self._on_process_started)
            except Exception:
                pass

        self.process = QProcess(self)
        program, arguments, working_dir = get_multi_ai_repl_command()
        self.process.setWorkingDirectory(working_dir)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        env = QProcessEnvironment.systemEnvironment()
        env.remove("VIRTUAL_ENV")
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(self._on_ready_read_stdout)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)
        self.process.started.connect(self._on_process_started)

        self._stdout_buffer = ""
        self._pause_waiting = False
        self._last_output_had_newline = True
        self._last_result_saved_line = None
        self.btn_continue.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self._set_repl_status("Starting...", "#dcdcaa")
        self.btn_send.setEnabled(False)
        self.btn_run_sequence.setEnabled(False)
        self.btn_restart_repl.setEnabled(False)

        self.process.start(
            program,
            arguments,
        )

    def _restart_repl_session(self) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
                self.process.waitForFinished(2000)

        self.log_view.appendPlainText("[INFO] Restarting REPL process...")
        self._start_repl_session()

    def _on_process_started(self) -> None:
        self._set_repl_status("Running", "#4ec9b0")
        self._set_pause_waiting(False)
        self.btn_restart_repl.setEnabled(True)
        self.log_view.appendPlainText("[INFO] REPL process started.")

    def _on_ready_read_stdout(self) -> None:
        if not self.process:
            return

        data = self.process.readAllStandardOutput()
        text = bytes(data.data()).decode("utf-8", errors="replace")
        text = self._normalize_log_text(text)

        if (
            text.startswith("[*]")
            and not self._last_output_had_newline
            and not self._stdout_buffer.endswith("\n")
        ):
            self._stdout_buffer += "\n"

        self._stdout_buffer += text
        self._last_output_had_newline = text.endswith("\n")

        if PAUSE_PROMPT in self._stdout_buffer:
            self._stdout_buffer = self._stdout_buffer.replace(PAUSE_PROMPT, "")
            if not self._pause_waiting:
                self._set_pause_waiting(True)

        if RESULT_SAVED_MARKER in self._stdout_buffer and not self._pause_waiting:
            self._notify_result_saved(self._stdout_buffer)

        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if line.strip():
                self.log_view.appendPlainText(line)
            else:
                self.log_view.appendPlainText("")

        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _notify_result_saved(self, text: str) -> None:
        """Notify the user when CLI output has been saved to a file."""
        for line in text.splitlines():
            marker_index = line.find(RESULT_SAVED_MARKER)
            if marker_index == -1:
                continue

            if line == self._last_result_saved_line:
                return

            saved_part = line[marker_index + len(RESULT_SAVED_MARKER) :]
            end_index = saved_part.find("'")
            if end_index == -1:
                continue

            saved_path = saved_part[:end_index]
            message = f"Output saved to {saved_path}"

            self._last_result_saved_line = line
            self._set_repl_status("Running", "#4ec9b0")
            self.status_bar.showMessage(message, 5000)
            self.log_view.appendPlainText(f"[INFO] {message}")
            return

        if self._last_result_saved_line != RESULT_SAVED_MARKER:
            self._last_result_saved_line = RESULT_SAVED_MARKER
            self._set_repl_status("Running", "#4ec9b0")
            self.status_bar.showMessage("Output file saved.", 5000)
            self.log_view.appendPlainText("[INFO] Output file saved.")

    def _on_process_finished(
        self, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        del exit_status

        if self._stdout_buffer:
            self.log_view.appendPlainText(self._stdout_buffer.rstrip("\r"))
            self._stdout_buffer = ""

        self._pause_waiting = False
        self.btn_continue.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.btn_run_sequence.setEnabled(False)
        self.btn_restart_repl.setEnabled(True)

        if exit_code == 0:
            self._set_repl_status("Stopped", "#c586c0")
            self.log_view.appendPlainText("[INFO] REPL process finished.")
        else:
            self._set_repl_status("Stopped (error)", "#f48771")
            self.log_view.appendPlainText(
                f"[WARN] REPL process exited with code {exit_code}."
            )

        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        self._set_repl_status("Error", "#f48771")
        self._pause_waiting = False
        self.btn_continue.setEnabled(False)
        self.btn_abort.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.btn_run_sequence.setEnabled(False)
        self.btn_restart_repl.setEnabled(True)
        self.log_view.appendPlainText(f"[ERROR] REPL process error: {error}")

        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    # ---- Polling timer for directory changes ----

    def _start_polling_timer(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_directories)
        self._poll_timer.start(1000)

    def _poll_directories(self) -> None:
        curr_prompts = get_dir_state(PROMPTS_DIR)
        curr_work_data = get_dir_state(WORK_DATA_DIR)

        if curr_prompts != self.last_prompts_state:
            expanded = collect_tree_expanded_paths(self.seq_tree)
            selected = self.current_seq_file
            populate_tree(self.seq_tree, PROMPTS_DIR, expanded, selected)
            self.last_prompts_state = curr_prompts
            if self.current_seq_file and not os.path.exists(self.current_seq_file):
                self.current_seq_file = None
                self._set_editing_seq_label()

        if curr_work_data != self.last_work_data_state:
            expanded = collect_tree_expanded_paths(self.file_tree)
            selected = self.current_io_file
            populate_tree(self.file_tree, WORK_DATA_DIR, expanded, selected)
            self.last_work_data_state = curr_work_data
            if self.current_io_file and not os.path.exists(self.current_io_file):
                self.current_io_file = None
                self.file_view.clear()

    # ---- Event handlers ----

    def _on_seq_tree_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(path, str) and os.path.isfile(path):
            self.current_seq_file = path
            self._set_editing_seq_label()
            with open(path, encoding="utf-8") as f:
                self.flow_edit.setPlainText(f.read())

    def _on_file_tree_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(path, str) and os.path.isfile(path):
            self.current_io_file = path
            with open(path, encoding="utf-8") as f:
                self.file_view.setPlainText(f.read())

    def _on_new_seq(self) -> None:
        self._clear_seq_selection()
        self.flow_edit.clear()

    def _on_update_seq(self) -> None:
        self._save_current_sequence()

    def _on_update_io_file(self) -> None:
        if self.current_io_file:
            with open(self.current_io_file, "w", encoding="utf-8") as f:
                f.write(self.file_view.toPlainText())

    def _send_command_to_repl(self, command: str) -> None:
        if not self.process or self.process.state() != QProcess.ProcessState.Running:
            QMessageBox.warning(
                self, "REPL Not Running", "The REPL process is not running."
            )
            return
        self._set_repl_status("Processing...", "#dcdcaa")

        self.log_view.appendPlainText(command)
        self.log_view.appendPlainText("")
        self.process.write((command + "\n").encode("utf-8"))

    def _on_send(self) -> None:
        flow_data = self.flow_edit.toPlainText().strip()
        if not flow_data:
            QMessageBox.warning(self, "Empty Input", "FLOW DEFINITION is empty.")
            return
        self._send_command_to_repl(flow_data)

    def _on_run_sequence(self) -> None:
        saved_path = self._save_current_sequence()
        if not saved_path:
            return

        command = self._build_sequence_run_command(saved_path)
        self._send_command_to_repl(command)

    def _on_continue_pause(self) -> None:
        """Continue a Flow that is waiting at @pause."""
        if (
            not self._pause_waiting
            or not self.process
            or self.process.state() != QProcess.ProcessState.Running
        ):
            return

        self.process.write(b"\n")
        self._set_pause_waiting(False)
        self._set_repl_status("Running", "#4ec9b0")

    def _on_abort_pause(self) -> None:
        """Abort a Flow that is waiting at @pause."""
        if (
            not self._pause_waiting
            or not self.process
            or self.process.state() != QProcess.ProcessState.Running
        ):
            return

        self.process.write(b"q\n")
        self._set_pause_waiting(False)
        self._set_repl_status("Running", "#4ec9b0")

    def _on_clear(self) -> None:
        self.log_view.clear()

    def _on_refresh_seq(self) -> None:
        self._refresh_seq_tree_preserve()

    def _on_refresh_io(self) -> None:
        self._refresh_io_tree_preserve()

    def _on_restart_repl(self) -> None:
        self._restart_repl_session()

    # ---- Cleanup ----

    @override
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Handle window close event by terminating the REPL process."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(2000):
                self.process.kill()
                self.process.waitForFinished(2000)
        event.accept()

    def _normalize_log_text(self, text: str) -> str:
        text = strip_ansi(text)
        text = text.replace(
            "[*] Pause:    @pause  (interactive pause in pipelines / sequences)", ""
        )
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = text.split("\n")
        cleaned: list[str] = []

        for line in lines:
            if line.strip() == "%":
                continue
            if line.startswith("% "):
                line = line[2:]
            cleaned.append(line)

        return "\n".join(cleaned)
