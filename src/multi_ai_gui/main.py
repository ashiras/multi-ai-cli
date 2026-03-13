"""
Main entry point for the Multi-AI GUI application.

This module implements an experimental GUI frontend for Multi-AI CLI.
It currently acts as a lightweight visual layer for flow editing,
sequence-style execution, file inspection, and basic REPL interaction.

The GUI is still at mock level. Its primary purpose is to explore
usability, validate frontend concepts, and observe how existing
Multi-AI CLI workflows translate into a graphical interface.
"""

import os
import subprocess
import threading
from typing import IO

import FreeSimpleGUI  # type: ignore[import-untyped]

# =================================================================
# 1. Paths and directory settings
# =================================================================
CLI_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "multi-ai-cli"))
PROMPTS_DIR = "prompts"
WORK_DATA_DIR = "work_data"

os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(WORK_DATA_DIR, exist_ok=True)

# Global process management
cli_process: subprocess.Popen[str] | None = None

# =================================================================
# 2. VS Code-like theme settings
# =================================================================
FreeSimpleGUI.theme_add_new(
    "VSCodeDark",
    {
        "BACKGROUND": "#1e1e1e",
        "TEXT": "#cccccc",
        "INPUT": "#2d2d2d",
        "TEXT_INPUT": "#cccccc",
        "SCROLL": "#424242",
        "BUTTON": ("#ffffff", "#0e639c"),
        "PROGRESS": ("#0e639c", "#3c3c3c"),
        "BORDER": 0,
        "SLIDER_DEPTH": 0,
        "PROGRESS_DEPTH": 0,
    },
)
FreeSimpleGUI.theme("VSCodeDark")


# =================================================================
# 3. Utilities and process control
# =================================================================
def get_tree_data(base_folder: str) -> FreeSimpleGUI.TreeData:
    """Build tree data for the specified folder."""
    treedata = FreeSimpleGUI.TreeData()

    def add_items(folder: str, parent_key: str = "") -> None:
        try:
            items = sorted(os.listdir(folder))
        except OSError:
            return
        for item in items:
            if item.startswith("."):
                continue
            full_path = os.path.join(folder, item)
            is_dir = os.path.isdir(full_path)
            icon = "📂" if is_dir else "📄"
            treedata.insert(parent_key, full_path, f"{icon} {item}", values=[])
            if is_dir:
                add_items(full_path, full_path)

    add_items(base_folder, "")
    return treedata


def get_dir_state(folder: str) -> set[str]:
    """Return the visible file state under the specified folder."""
    state = set()
    for root, _dirs, files in os.walk(folder):
        for file_name in files:
            if not file_name.startswith("."):
                state.add(os.path.join(root, file_name))
    return state


def start_repl_session(window: FreeSimpleGUI.Window) -> None:
    """Start the CLI once in REPL mode at application startup."""
    global cli_process
    cmd = "uv run multi-ai --mode repl"

    try:
        clean_env = os.environ.copy()
        clean_env.pop("VIRTUAL_ENV", None)
        clean_env["PYTHONUNBUFFERED"] = "1"

        cli_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            bufsize=1,
            cwd=CLI_DIR,
            env=clean_env,
        )

        # Start a thread that forwards CLI output to the GUI.
        threading.Thread(target=read_output_loop, args=(window,), daemon=True).start()

    except Exception as exc:
        window["-LOG-"].update(f"[ERROR] Failed to start REPL: {exc}\n", append=True)


def read_output_loop(window: FreeSimpleGUI.Window) -> None:
    """Monitor CLI output and forward it to the GUI."""
    global cli_process
    while cli_process and cli_process.poll() is None:
        stdout: IO[str] | None = cli_process.stdout
        if stdout is None:
            break

        line = stdout.readline()
        if line:
            # Send an event to the GUI thread for safe updates.
            window.write_event_value("-STDOUT-", line)
        else:
            break


# =================================================================
# 4. Layout definitions
# =================================================================
def build_layout() -> list[list[object]]:
    """Build and return the application layout."""
    sidebar_bg = "#252526"

    col_left = FreeSimpleGUI.Column(
        [
            [
                FreeSimpleGUI.Text(
                    "SEQUENCES",
                    font=("Segoe UI", 10, "bold"),
                    background_color=sidebar_bg,
                    text_color="#858585",
                    pad=(5, 10),
                ),
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button("↻", size=(2, 1), key="-REFRESH_SEQ-"),
            ],
            [
                FreeSimpleGUI.Tree(
                    data=get_tree_data(PROMPTS_DIR),
                    headings=[],
                    col0_width=40,
                    col0_heading="",
                    num_rows=30,
                    show_expanded=True,
                    enable_events=True,
                    key="-SEQ_TREE-",
                    background_color=sidebar_bg,
                    text_color="#cccccc",
                    expand_x=True,
                    expand_y=True,
                    row_height=30,
                )
            ],
        ],
        background_color=sidebar_bg,
        expand_y=True,
        expand_x=True,
        pad=(0, 0),
    )

    col_mid_top = FreeSimpleGUI.Column(
        [
            [
                FreeSimpleGUI.Text(
                    "FLOW DEFINITION",
                    font=("Segoe UI", 10, "bold"),
                    text_color="#858585",
                    pad=(10, 10),
                ),
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button("Update", size=(10, 1), key="-UPDATE_SEQ-"),
                FreeSimpleGUI.Button("▶ Run Flow", size=(12, 1), key="-RUN-"),
            ],
            [
                FreeSimpleGUI.Multiline(
                    size=(80, 15),
                    key="-FLOW-",
                    background_color="#1e1e1e",
                    text_color="#dcdcaa",
                    font=("Consolas", 11),
                    expand_x=True,
                    expand_y=True,
                    border_width=0,
                    pad=(10, 0),
                )
            ],
        ],
        expand_x=True,
        expand_y=True,
        pad=(0, 0),
    )

    col_mid_bot = FreeSimpleGUI.Column(
        [
            [
                FreeSimpleGUI.Text(
                    "TERMINAL",
                    font=("Segoe UI", 10, "bold"),
                    text_color="#858585",
                    pad=(10, 10),
                ),
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button("Clear", size=(8, 1), key="-CLEAR-"),
            ],
            [
                FreeSimpleGUI.Multiline(
                    size=(80, 10),
                    key="-LOG-",
                    background_color="#1e1e1e",
                    text_color="#d4d4d4",
                    font=("Consolas", 11),
                    autoscroll=True,
                    expand_x=True,
                    expand_y=True,
                    border_width=0,
                    pad=(10, 0),
                )
            ],
        ],
        expand_x=True,
        expand_y=True,
        pad=(0, 0),
    )

    pane_mid = FreeSimpleGUI.Pane(
        [col_mid_top, col_mid_bot],
        orientation="v",
        relief=FreeSimpleGUI.RELIEF_SUNKEN,
        show_handle=False,
        handle_size=15,
        expand_x=True,
        expand_y=True,
    )

    col_right_top = FreeSimpleGUI.Column(
        [
            [
                FreeSimpleGUI.Text(
                    "I/O FILES",
                    font=("Segoe UI", 10, "bold"),
                    text_color="#858585",
                    pad=(10, 10),
                ),
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button("↻ Refresh", size=(10, 1), key="-REFRESH_IO-"),
            ],
            [
                FreeSimpleGUI.Tree(
                    data=get_tree_data(WORK_DATA_DIR),
                    headings=[],
                    col0_width=30,
                    col0_heading="",
                    num_rows=25,
                    show_expanded=True,
                    enable_events=True,
                    key="-FILE_TREE-",
                    background_color="#2d2d2d",
                    text_color="#cccccc",
                    expand_x=True,
                    expand_y=True,
                    row_height=30,
                )
            ],
        ],
        expand_x=True,
        expand_y=True,
        pad=(0, 0),
    )

    col_right_bot = FreeSimpleGUI.Column(
        [
            [
                FreeSimpleGUI.Text(
                    "FILE PREVIEW",
                    font=("Segoe UI", 10, "bold"),
                    text_color="#858585",
                    pad=(10, 10),
                ),
                FreeSimpleGUI.Push(),
                FreeSimpleGUI.Button("Update", size=(8, 1), key="-UPDATE_IO_FILE-"),
            ],
            [
                FreeSimpleGUI.Multiline(
                    size=(20, 15),
                    key="-FILE_VIEW-",
                    background_color="#1e1e1e",
                    text_color="#9cdcfe",
                    font=("Consolas", 10),
                    expand_x=True,
                    expand_y=True,
                    border_width=0,
                    pad=(10, 0),
                )
            ],
        ],
        expand_x=True,
        expand_y=True,
        pad=(0, 0),
    )

    pane_right = FreeSimpleGUI.Pane(
        [col_right_top, col_right_bot],
        orientation="v",
        relief=FreeSimpleGUI.RELIEF_SUNKEN,
        show_handle=False,
        handle_size=15,
        expand_x=True,
        expand_y=True,
    )

    return [
        [
            FreeSimpleGUI.Pane(
                [
                    col_left,
                    FreeSimpleGUI.Column(
                        [[pane_mid]],
                        expand_x=True,
                        expand_y=True,
                        pad=(0, 0),
                    ),
                    FreeSimpleGUI.Column(
                        [[pane_right]],
                        expand_x=True,
                        expand_y=True,
                        pad=(0, 0),
                    ),
                ],
                orientation="h",
                relief=FreeSimpleGUI.RELIEF_SUNKEN,
                show_handle=False,
                handle_size=15,
                expand_x=True,
                expand_y=True,
            )
        ]
    ]


# =================================================================
# 5. Main loop
# =================================================================
def main() -> None:
    """Run the GUI application."""
    global cli_process

    window = FreeSimpleGUI.Window(
        "multi-ai-cli IDE",
        build_layout(),
        resizable=True,
        finalize=True,
        margins=(0, 0),
    )
    window.maximize()

    # Start the REPL session once at startup.
    start_repl_session(window)

    current_seq_file: str | None = None
    current_io_file: str | None = None
    last_prompts_state = get_dir_state(PROMPTS_DIR)
    last_work_data_state = get_dir_state(WORK_DATA_DIR)

    while True:
        event, values = window.read(timeout=1000)
        if event in (FreeSimpleGUI.WIN_CLOSED, "Exit"):
            if cli_process:
                cli_process.terminate()
            break

        # Display standard output received from the background thread.
        if event == "-STDOUT-":
            window["-LOG-"].update(values["-STDOUT-"], append=True)

        if event == FreeSimpleGUI.TIMEOUT_EVENT:
            curr_prompts_state = get_dir_state(PROMPTS_DIR)
            curr_work_data_state = get_dir_state(WORK_DATA_DIR)

            if curr_prompts_state != last_prompts_state:
                window["-SEQ_TREE-"].update(values=get_tree_data(PROMPTS_DIR))
                last_prompts_state = curr_prompts_state

            if curr_work_data_state != last_work_data_state:
                window["-FILE_TREE-"].update(values=get_tree_data(WORK_DATA_DIR))
                last_work_data_state = curr_work_data_state

        if event == "-SEQ_TREE-" and values["-SEQ_TREE-"]:
            path = values["-SEQ_TREE-"][0]
            if os.path.isfile(path):
                current_seq_file = path
                with open(path, encoding="utf-8") as file:
                    window["-FLOW-"].update(file.read())

        if event == "-FILE_TREE-" and values["-FILE_TREE-"]:
            path = values["-FILE_TREE-"][0]
            if os.path.isfile(path):
                current_io_file = path
                with open(path, encoding="utf-8") as file:
                    window["-FILE_VIEW-"].update(file.read())

        if event == "-UPDATE_SEQ-":
            if current_seq_file:
                with open(current_seq_file, "w", encoding="utf-8") as file:
                    file.write(values["-FLOW-"])

        if event == "-UPDATE_IO_FILE-":
            if current_io_file:
                with open(current_io_file, "w", encoding="utf-8") as file:
                    file.write(values["-FILE_VIEW-"])

        if event == "-RUN-":
            flow_data = values["-FLOW-"].strip()
            if flow_data and cli_process:
                stdin: IO[str] | None = cli_process.stdin
                if stdin is not None:
                    # Show the submitted command in the log area.
                    window["-LOG-"].update(
                        f"% {flow_data}\n",
                        append=True,
                        text_color_for_value="#ffffff",
                    )
                    # Send the command to the persistent process.
                    stdin.write(flow_data + "\n")
                    stdin.flush()

        if event == "-CLEAR-":
            window["-LOG-"].update("")

        if event == "-REFRESH_SEQ-":
            window["-SEQ_TREE-"].update(values=get_tree_data(PROMPTS_DIR))

        if event == "-REFRESH_IO-":
            window["-FILE_TREE-"].update(values=get_tree_data(WORK_DATA_DIR))

    window.close()


if __name__ == "__main__":
    main()
