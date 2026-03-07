"""
Utility functions for the Multi-AI CLI application.
Includes path security, editor integration, console safety, string helpers, etc.
"""

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading

from . import __version__

_console_lock = threading.Lock()


def secure_resolve_path(
    filename: str,
    category: str = "data",
    config=None,
) -> str:
    """
    Resolves a file path while preventing directory traversal attacks.
    Ensures the target file stays within the configured base directory.

    Args:
        filename: The relative filename to resolve.
        category: 'data' or 'efficient' to select the correct base path.

    Returns:
        Absolute path to the file.

    Raises:
        PermissionError: If path attempts directory traversal.
    """
    if config is None:
        raise RuntimeError("config must be provided")

    section_map = {"efficient": "work_efficient", "data": "work_data"}
    default_map = {"efficient": "prompts", "data": "work_data"}

    config_key = section_map.get(category, "work_data")
    default_dir = default_map.get(category, "work_data")

    base_dir = config.get("Paths", config_key, fallback=default_dir)
    abs_base = os.path.abspath(base_dir)
    target_path = os.path.abspath(os.path.join(abs_base, filename))

    if not os.path.commonpath([abs_base, target_path]) == abs_base:
        raise PermissionError(
            f"Security Alert: Directory traversal blocked for '{filename}'"
        )

    return target_path


def open_editor_for_prompt(
    logger=None,
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
    """
    if logger is None:
        logger = logging.getLogger("MultiAI")  # fallback

    editor_raw = os.environ.get("EDITOR", "vi").strip() or "vi"
    editor_cmd = shlex.split(editor_raw)

    MARKER = "# ==================== END HEADER ===================="
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

    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="ai_prompt_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None
            f.write(header)

        result = subprocess.run(editor_cmd + [tmp_path], check=False)

        if result.returncode != 0:
            logger.warning(f"Editor exited with non-zero status: {result.returncode}")
            print(f"[!] Editor exited with error (code {result.returncode}).")
            return None

        with open(tmp_path, encoding="utf-8") as f:
            raw_content = f.read()

        # Extract content after marker or ignore comment lines
        lines = raw_content.splitlines()

        if MARKER in lines:
            idx = lines.index(MARKER) + 1
            content = "\n".join(lines[idx:]).lstrip("\n").strip()
        else:
            content_lines = []
            started = False
            for line in lines:
                if not started:
                    if line.lstrip().startswith("#") or not line.strip():
                        continue
                    started = True
                content_lines.append(line)
            content = "\n".join(content_lines).strip()

        if not content:
            print("[*] Editor prompt is empty. Request cancelled.")
            logger.info("[*] Editor mode: empty prompt, cancelled.")
            return None

        # Preview
        preview_lines = content.splitlines()
        if len(preview_lines) <= 5:
            preview = content
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

        return content

    except FileNotFoundError:
        print(
            f"[!] Editor '{editor_cmd[0]}' not found. Set $EDITOR to your preferred editor."
        )
        print("    Example: export EDITOR=nano")
        logger.error(f"Editor not found: {editor_cmd[0]}")
        return None
    except Exception as e:
        print(f"[!] Editor error: {e}")
        logger.error(f"Editor error: {e}")
        return None
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning(f"Could not remove temp file {tmp_path}: {e}")


def safe_print(*args, **kwargs):
    """Thread-safe print using global console lock."""
    with _console_lock:
        print(*args, **kwargs)


def clear_thinking_line():
    """Clears the temporary 'thinking...' status line in the terminal."""
    with _console_lock:
        cols = shutil.get_terminal_size(fallback=(80, 20)).columns
        print(" " * (cols - 1), end="\r", flush=True)


def print_welcome_banner(engines, is_log_enabled):
    """Displays the startup banner with model info and available commands."""
    print("==================================================")
    print(f"  Multi-AI CLI v{__version__} (Raw-by-Default Write Mode)")
    for name, eng in engines.items():
        print(f"  {eng.name:<6}: {eng.model_name}")
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


def _get_cfg_int(config, section: str, key: str, fallback: int) -> int:
    """Safely read an integer from config with fallback on error."""
    try:
        return config.getint(section, key, fallback=fallback)
    except Exception:
        return fallback


def _make_continue_prompt(tail: str) -> str:
    """
    Builds a continuation instruction anchored by the tail of the previous output.
    Uses fenced block to avoid quote/escape issues.
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
    """Return the last n characters of text (or the whole text if shorter)."""
    if not text:
        return ""
    return text[-n:] if len(text) > n else text


def extract_code_block(text: str) -> str:
    """
    Extracts all fenced code blocks from the text and concatenates them.
    Used for -w:code mode to save only code, stripping explanatory text.
    Falls back to full text if no code blocks are found.
    """
    if "```" not in text:
        return text

    lines = text.splitlines()
    extracted_blocks = []
    current_block = []
    in_block = False

    for line in lines:
        if line.startswith("```"):
            if not in_block:
                in_block = True
            else:
                if line.strip() == "```":
                    in_block = False
                    extracted_blocks.append("\n".join(current_block))
                    current_block = []
                else:
                    current_block.append(line)
        else:
            if in_block:
                current_block.append(line)

    if in_block and current_block:
        extracted_blocks.append("\n".join(current_block))

    if extracted_blocks:
        return "\n\n".join(extracted_blocks)

    return text
