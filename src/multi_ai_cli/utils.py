"""
Utility functions for the Multi-AI CLI application.
Includes path security, editor integration, console safety, string helpers, etc.
"""

import configparser
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
from typing import Any

from . import __version__
from .engines import AIEngine

MARKER = "# ==================== END HEADER ===================="

_console_lock = threading.Lock()  # Global lock for thread-safe console output


def secure_resolve_path(
    filename: str,
    category: str = "data",
    config: configparser.ConfigParser | None = None,
) -> str:
    """
    Resolves a file path while preventing directory traversal attacks.
    Ensures the target file stays within the configured base directory.

    Args:
        filename (str): The relative filename to resolve.
        category (str): 'data' or 'efficient' to select the correct base path.
        config: Configuration object containing paths.

    Returns:
        str: Absolute path to the file.

    Raises:
        PermissionError: If path attempts directory traversal.
        RuntimeError: If config is not provided.

    """
    if config is None:
        raise RuntimeError("config must be provided")

    # Map categories to configuration keys and default paths
    section_map = {"efficient": "work_efficient", "data": "work_data"}
    default_map = {"efficient": "prompts", "data": "work_data"}

    # Determine the base directory from the config
    config_key = section_map.get(category, "work_data")
    default_dir = default_map.get(category, "work_data")

    base_dir = config.get("Paths", config_key, fallback=default_dir)
    abs_base = os.path.abspath(base_dir)  # Get absolute base directory
    target_path = os.path.abspath(
        os.path.join(abs_base, filename)
    )  # Resolve target path

    # Prevent directory traversal by ensuring the target path is within the base directory
    if not os.path.commonpath([abs_base, target_path]) == abs_base:
        raise PermissionError(
            f"Security Alert: Directory traversal blocked for '{filename}'"
        )

    return target_path  # Return the secured absolute path


def open_editor_for_prompt(
    logger: logging.Logger | None = None,
) -> str | None:
    """
    Opens the user's preferred editor ($EDITOR or fallback to vi) with a temporary file.
    Returns the content written by the user (after stripping comments), or None if cancelled/empty.

    Flow:
      1. Create temp file with helpful header comment
      2. Launch editor
      3. Read back content, ignore lines starting with '#'
      4. Clean up temp file
      5. Return prompt text or None

    Args:
        logger: Logger instance to log messages; defaults to MultiAI logger.

    Returns:
        str | None: The content written in the editor or None if empty.

    """
    if logger is None:
        logger = logging.getLogger("MultiAI")  # Fallback logger if none is provided

    # Get user's editor from environment or default to 'vi'
    editor_raw = os.environ.get("EDITOR", "vi").strip() or "vi"
    editor_cmd = shlex.split(editor_raw)  # Prepare command to launch the editor

    # Header to include in the temporary editor file
    header = (
        "# ====================================================\n"
        "# Multi-AI CLI - Editor Mode\n"
        "# ====================================================\n"
        "# Write your prompt below. Lines starting with '#' are\n"
        "# ignored (treated as comments).\n"
        "#\n"
        "# Save and quit the editor to send your prompt.\n"
        "# Leave empty (or only comments) to cancel.\n"
        f"{MARKER}\n"
        "\n"
    )

    tmp_fd = None  # Temporary file descriptor
    tmp_path = None  # Path of the temporary file

    try:
        # Create a temporary file for the editor content
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="ai_prompt_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None  # Reset to prevent closing the fd prematurely
            f.write(header)  # Write the header to the temp file

        # Run the editor with the temporary file
        result = subprocess.run(editor_cmd + [tmp_path], check=False)

        # Check if the editor exited with an error code
        if result.returncode != 0:
            logger.warning(f"Editor exited with non-zero status: {result.returncode}")
            print(f"[!] Editor exited with error (code {result.returncode}).")
            return None

        # Read the content from the temporary file
        with open(tmp_path, encoding="utf-8") as f:
            raw_content = f.read()

        # Extract content after marker or ignore comment lines
        lines = raw_content.splitlines()

        if MARKER in lines:
            idx = lines.index(MARKER) + 1  # Get index after marker
            content = (
                "\n".join(lines[idx:]).lstrip("\n").strip()
            )  # Extract relevant content
        else:
            content_lines = []  # Initialize to collect non-comment lines
            started = False  # Flag to indicate if valid content has started
            for line in lines:
                if not started:
                    if (
                        line.lstrip().startswith("#") or not line.strip()
                    ):  # Skip comments/empty lines
                        continue
                    started = True  # Mark that valid content has started
                content_lines.append(line)  # Collect valid content
            content = "\n".join(
                content_lines
            ).strip()  # Join lines into a single content block

        # Handle cancellation if the content is empty
        if not content:
            print("[*] Editor prompt is empty. Request cancelled.")
            logger.info("[*] Editor mode: empty prompt, cancelled.")
            return None

        # Preview the content for the user
        preview_lines = content.splitlines()
        if len(preview_lines) <= 5:
            preview = content  # No truncation needed for short prompts
        else:
            preview = (
                "\n".join(preview_lines[:5])
                + f"\n... ({len(preview_lines)} lines total)"
            )

        print(
            f"[*] Editor prompt captured ({len(content)} chars, {len(preview_lines)} lines):"
        )
        print("--- Preview ---")
        print(preview)
        print("--- End Preview ---")

        return content  # Return the captured content

    except FileNotFoundError:
        print(
            f"[!] Editor '{editor_cmd[0]}' not found. Set $EDITOR to your preferred editor."
        )
        print("    Example: export EDITOR=nano")
        logger.error(f"Editor not found: {editor_cmd[0]}")
        return None
    except Exception as e:
        print(
            f"[!] Editor error: {e}"
        )  # Catch general exceptions related to the editor
        logger.error(f"Editor error: {e}")
        return None
    finally:
        # Cleanup: close and remove the temporary file
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)  # Close the file descriptor if still open
            except OSError:
                pass  # Ignore any errors in closing the fd
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)  # Remove the temporary file
            except OSError as e:
                logger.warning(
                    f"Could not remove temp file {tmp_path}: {e}"
                )  # Log cleanup issues


def safe_print(*args: Any, **kwargs: Any) -> None:
    """Thread-safe print using global console lock."""
    with _console_lock:
        print(*args, **kwargs)  # Print arguments safely


def clear_thinking_line() -> None:
    """Clears the temporary 'thinking...' status line in the terminal."""
    with _console_lock:
        cols = shutil.get_terminal_size(fallback=(80, 20)).columns  # Get terminal width
        print(" " * (cols - 1), end="\r", flush=True)  # Print spaces to clear the line


def print_welcome_banner(engines: dict[str, AIEngine], is_log_enabled: bool) -> None:
    """
    Displays the startup banner with model info and available commands.

    Args:
        engines: Dictionary of available model engines.
        is_log_enabled (bool): Whether logging is enabled.

    """
    print("==================================================")
    print(f"  Multi-AI CLI v{__version__} (Raw-by-Default Write Mode)")
    for name, eng in engines.items():
        print(f"  {eng.name:<6}: {eng.model_name}")  # Print engine information
    print("==================================================")

    log_status = (
        "Disabled (Stealth)" if not is_log_enabled else "Enabled (tail-f logs/chat.log)"
    )
    print(f"[*] Logging: {log_status}")
    print("[*] Commands: @model, @efficient, @scrub, @sequence, @sh, exit")
    print("[*] Editor:   @model -e | --edit  (uses $EDITOR or vi)")
    print("[*] Sequence: @sequence -e  (multi-step pipeline via editor)")
    print("[*]           Use '->' to chain steps in editor mode")
    print("[*]           Use '[ cmd1 || cmd2 ]' for parallel execution")
    print('[*] Shell:    @sh "command"  |  @sh -r script.py  |  @sh "cmd" -w out.json')
    print('[*]           @sh --shell "echo $HOME | grep user"  (pipes/env expansion)')
    print("[*] Write:    -w <file>       (save full response -- raw, default)")
    print("[*]           -w:code <file>  (extract code blocks only)")
    print("[*]           -w:raw <file>   (explicit raw, same as -w)")
    print('[*] Flags:    -r <file> (read, repeatable)  -m "<msg>" (message)')


def _get_cfg_int(
    config: configparser.ConfigParser, section: str, key: str, fallback: int
) -> int:
    """
    Safely read an integer from config with fallback on error.

    Args:
        config: The configuration object to read from.
        section (str): The section of the config.
        key (str): The key within the section.
        fallback (int): The fallback value if reading fails.

    Returns:
        int: The integer value from the config or fallback.

    """
    try:
        return config.getint(section, key, fallback=fallback)  # Get integer from config
    except Exception:
        return fallback  # Return fallback if there's an error


def _make_continue_prompt(tail: str) -> str:
    """Builds a continuation instruction anchored by the tail of the previous output.
    Uses fenced block to avoid quote/escape issues.

    Args:
        tail (str): The tail of the previous output for reference.

    Returns:
        str: The formatted continuation prompt.

    """
    return (
        "The output was truncated due to an output limit.\n"
        "Continue EXACTLY from where you stopped.\n"
        "Rules:\n"
        "- Do NOT repeat any earlier content.\n"
        "- Do NOT add greetings, headings, apologies, or explanations.\n"
        "- Output ONLY the continuation.\n\n"
        "Here is the tail of your last output for alignment:\n"
        "```tail\n"
        f"{tail}\n"
        "```\n"
    )


def _tail_of(text: str, n: int) -> str:
    """
    Return the last n characters of text (or the whole text if shorter).

    Args:
        text (str): The text to extract from.
        n (int): The number of characters to return.

    Returns:
        str: The last n characters of the text.

    """
    if not text:
        return ""  # Return empty string if input is empty
    return text[-n:] if len(text) > n else text  # Return last n characters


def extract_code_block(text: str) -> str:
    """Extract all fenced code blocks from the text and concatenates them.
    Used for -w:code mode to save only code, stripping explanatory text.
    Falls back to full text if no code blocks are found.

    Args:
        text (str): The text to analyze for code blocks.

    Returns:
        str: Concatenated code blocks or the original text.

    """
    if "```" not in text:  # Check for presence of code blocks
        return text  # Return the original text if no blocks are present

    lines = text.splitlines()  # Split text into lines
    extracted_blocks = []  # List to hold extracted code blocks
    current_block: list[str] = []  # List for the current block being constructed
    in_block = False  # Flag to track if currently inside a code block

    for line in lines:
        if line.startswith("```"):  # Start or end of a code block
            if not in_block:
                in_block = True  # Entering a code block
            else:
                if line.strip() == "```":  # Closing mark for a block
                    in_block = False
                    extracted_blocks.append(
                        "\n".join(current_block)
                    )  # Add the completed block
                    current_block = []  # Reset for next block
                else:
                    current_block.append(line)  # Collect lines within a block
        else:
            if in_block:  # Collect lines only if inside a block
                current_block.append(line)

    # Check if we're still in a block at the end
    if in_block and current_block:
        extracted_blocks.append("\n".join(current_block))  # Add any remaining block

    if extracted_blocks:  # If we have extracted blocks
        return "\n\n".join(extracted_blocks)  # Join blocks with newlines

    return text  # Fallback to original text if no code blocks found
