"""
Command handlers for Multi-AI CLI.

Processes user commands (@model, @sh, @sequence, @scrub, etc.) and
dispatches them.
"""

import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from .adapters.shell import ShellAdapter
from .adapters.shell.adapter import ShellCommandBuildError
from .adapters.shell.models import ShellResult
from .config import config, engines, logger
from .parsers import (
    ParsedInput,
    ParsedShInput,
    _parse_sh_input,
    build_ai_prompt,
    parse_cli_input,
    parse_sequence_steps,
)
from .utils import (
    _console_lock,
    clear_thinking_line,
    extract_code_block,
    open_editor_for_prompt,
    safe_print,
    secure_resolve_path,
)

WRITE_MODE_RAW = "raw"
WRITE_MODE_CODE = "code"


def dispatch_command(parts: list[str]) -> bool:
    """
    Routes the parsed command tokens to the appropriate handler.

    Args:
        parts (list[str]): List of command parts to be dispatched.

    Returns:
        bool: True if command succeeded, False otherwise.
    """
    if not parts:
        return False

    cmd = parts[0].lower()

    if cmd in ["@scrub", "@flush"]:
        handle_scrub(parts)
        return True

    if cmd == "@efficient":
        handle_efficient(parts)
        return True

    if cmd == "@sequence":
        handle_sequence(parts)
        return True

    if cmd == "@sh":
        return handle_sh(parts)

    if cmd == "@figma.pull":
        from .adapters.figma.facade import handle_figma_pull

        return handle_figma_pull(parts)

    if cmd == "@figma.push":
        from .adapters.figma.facade import handle_figma_push

        return handle_figma_push(parts)

    target_key = cmd.replace("@", "")
    if target_key in engines:
        return handle_ai_interaction(parts)

    safe_print(f"[!] Unknown command: '{cmd}'")
    safe_print(
        f"    Available: {', '.join('@' + k for k in engines.keys())}, "
        f"@efficient, @scrub, @sequence, @sh, @figma.pull, @figma.push, exit"
    )
    return False


def handle_scrub(parts: list[str]) -> None:
    """
    Handles @scrub / @flush command to clear engine history.

    Args:
        parts (list[str]): List of command parts.
    """
    target = parts[1].lower() if len(parts) > 1 else "all"
    valid_targets = set(engines.keys()) | {"all"}

    if target not in valid_targets:
        print(f"[!] Invalid target '{target}'. Valid: {', '.join(valid_targets)}")
        return

    for name, engine in engines.items():
        if target in ["all", name]:
            engine.scrub()
            print(f"[*] {engine.name} memory scrubbed.")


def handle_efficient(parts: list[str]) -> None:
    """
    Handles @efficient command to load persona files.

    Args:
        parts (list[str]): List of command parts.
    """
    if len(parts) < 2:
        print("[!] Usage: @efficient [target/all] <filename.txt>")
        return

    if parts[1].lower() in (list(engines.keys()) + ["all"]):
        target = parts[1].lower()
        filename = parts[2] if len(parts) > 2 else None
    else:
        target = "all"
        filename = parts[1]

    if not filename:
        print("[!] Error: Persona filename is required.")
        return

    try:
        filepath = secure_resolve_path(filename, "efficient", config=config)
        with open(filepath, encoding="utf-8") as f:
            content = f.read().strip()

        for name, engine in engines.items():
            if target in ["all", name]:
                engine.load_persona(content, filename)
                print(f"[*] {engine.name} persona loaded: '{filename}'.")
    except Exception as e:
        print(f"[!] Persona loading failed: {e}")


def handle_ai_interaction(parts: list[str]) -> bool:
    """
    Handles interaction with a specific AI model (@gemini "prompt" ...).

    Supports flags: -m, -r, -w[:raw|:code], -e

    Args:
        parts (list[str]): List of command parts to interact with AI.

    Returns:
        bool: True if interaction succeeded, False otherwise. Returns
            False if prompt building fails or an AI engine error occurs.
    """
    target_key = parts[0].lower().replace("@", "")
    engine = engines.get(target_key)

    if not engine:
        safe_print(f"[!] Engine '{target_key}' not found.")
        return False

    parsed: ParsedInput | None = parse_cli_input(parts)
    if parsed is None:
        return False

    editor_content = None
    if parsed.use_editor:
        editor_content = open_editor_for_prompt()
        if editor_content is None:
            return False

    try:
        prompt_main = build_ai_prompt(parsed, editor_content)
    except Exception as e:
        safe_print(f"[!] {e}")
        return False

    if not prompt_main.strip():
        safe_print("[!] No prompt to send. Provide text, use -e, -m, or -r.")
        return False

    logger.info(f"@User ({engine.name}): {prompt_main}")
    with _console_lock:
        print(f"[*] {engine.name} is thinking...", end="\r", flush=True)
    logger.info(f"[*] {engine.name} is thinking...")

    try:
        result = engine.call(prompt_main)
        clear_thinking_line()
        logger.info(f"@{engine.name}: {result}")
        logger.info("-" * 40)

        if parsed.write_file:
            if parsed.write_mode == WRITE_MODE_CODE:
                final_out = extract_code_block(result)
                mode_label = "code-extracted"
            else:
                final_out = result
                mode_label = "raw"

            out_path = secure_resolve_path(parsed.write_file, "data", config=config)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(final_out.strip())
                f.flush()
                os.fsync(f.fileno())

            safe_print(
                f"[*] Result saved to '{parsed.write_file}' (mode: {mode_label})."
            )
            logger.info(f"[*] File written: '{parsed.write_file}' (mode: {mode_label})")
        else:
            safe_print(f"\n--- {engine.name} ---\n{result}\n")

        return True

    except Exception as e:
        clear_thinking_line()
        safe_print(f"[!] AI Engine Error: {e}")
        logger.error(f"AI interaction error: {e}")
        return False


def handle_sh(parts: list[str]) -> bool:
    """
    Handles @sh command: local shell execution with artifact capture.

    Delegates command building and execution to ShellAdapter.
    This handler is responsible for all UI output (print) and logging.

    Args:
        parts (list[str]): List of command parts.

    Returns:
        bool: True if shell command execution succeeded, False otherwise.
            Returns False if command parsing fails, the command is not
            found, times out, or another execution error occurs.

    Examples:
        >>> handle_sh(["@sh", "ls -la"])
        >>> handle_sh(["@sh", "-r", "script.py", "-w", "output.json"])
        >>> handle_sh(["@sh", "--shell", "echo $HOME | grep user", "-w", "result.md"])
    """
    parsed: ParsedShInput | None = _parse_sh_input(parts)
    if parsed is None:
        return False

    adapter = ShellAdapter()

    # --- Build command (before execution, so we can display it) ---
    def _resolve_path(filename: str) -> str:
        return secure_resolve_path(filename, "data", config=config)

    try:
        cmd, use_shell = adapter.build_command(parsed, resolve_path_fn=_resolve_path)
    except PermissionError as e:
        print(f"[!] @sh: {e}")
        logger.error(f"@sh: Permission error: {e}")
        return False
    except ShellCommandBuildError as e:
        print(f"[!] @sh: {e}")
        logger.error(f"@sh: Build error: {e}")
        return False

    cmd_display = shlex.join(cmd) if isinstance(cmd, list) else cmd

    # --- Pre-execution display (must happen BEFORE subprocess runs) ---
    logger.info(f"@sh: Executing '{cmd_display}' (shell={use_shell})")
    print(f"[*] @sh: Executing: {cmd_display}")
    if use_shell:
        print("[*] @sh: --shell mode enabled (shell=True)")

    # --- Execute command via adapter ---
    try:
        shell_result: ShellResult = adapter.execute_command(cmd, use_shell)
    except FileNotFoundError as e:
        print(f"[!] @sh: Command not found: {e}")
        logger.error(f"@sh: Command not found: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("[!] @sh: Command timed out (300s limit).")
        logger.error(f"@sh: Timeout for '{cmd_display}'")
        return False
    except OSError as e:
        print(f"[!] @sh: Execution error: {e}")
        logger.error(f"@sh: Execution error: {e}")
        return False

    # --- Post-execution display ---
    exit_code = shell_result.exit_code
    stdout = shell_result.stdout
    stderr = shell_result.stderr
    duration_ms = shell_result.duration_ms

    status_icon = "✓" if exit_code == 0 else "✗"
    status_label = "SUCCESS" if exit_code == 0 else "FAILURE"

    logger.info(
        f"@sh: Completed '{cmd_display}' -> exit_code={exit_code}, "
        f"duration={duration_ms:.1f}ms"
    )

    print(
        f"[{status_icon}] @sh: {status_label} (exit code: {exit_code}, {duration_ms:.1f}ms)"
    )

    if stdout.strip():
        display_stdout = stdout.rstrip()
        max_lines = 50
        lines = display_stdout.splitlines()
        if len(lines) > max_lines:
            print(f"--- stdout (showing first {max_lines}/{len(lines)} lines) ---")
            print("\n".join(lines[:max_lines]))
            print(f"--- (truncated, {len(lines) - max_lines} more lines) ---")
        else:
            print("--- stdout ---")
            print(display_stdout)
            print("--- end stdout ---")

    if stderr.strip():
        display_stderr = stderr.rstrip()
        max_lines = 30
        lines = display_stderr.splitlines()
        if len(lines) > max_lines:
            print(f"--- stderr (showing first {max_lines}/{len(lines)} lines) ---")
            print("\n".join(lines[:max_lines]))
            print(f"--- (truncated, {len(lines) - max_lines} more lines) ---")
        else:
            print("--- stderr ---")
            print(display_stderr)
            print("--- end stderr ---")

    # --- Artifact output ---
    if parsed.write_file:
        try:
            out_path = secure_resolve_path(parsed.write_file, "data", config=config)

            if parsed.write_file.lower().endswith(".json"):
                artifact = adapter.format_artifact_json(
                    cmd_display, exit_code, stdout, stderr, duration_ms
                )
                fmt_label = "JSON"
            else:
                artifact = adapter.format_artifact_text(
                    cmd_display, exit_code, stdout, stderr, duration_ms
                )
                fmt_label = "text"

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(artifact)
                f.flush()
                os.fsync(f.fileno())

            print(
                f"[*] @sh: Artifact saved to '{parsed.write_file}' (format: {fmt_label})."
            )
            logger.info(f"@sh: Artifact written ({fmt_label})")

        except Exception as e:
            print(f"[!] @sh: Error writing artifact: {e}")
            logger.error(f"@sh: Artifact write error: {e}")

    return exit_code == 0


def handle_sequence(parts: list[str]) -> None:
    """
    Handles @sequence command (requires -e/--edit flag).

    This command allows executing a series of commands defined in a
    temporary editor. Steps can be executed sequentially or in parallel.
    If any step fails, the sequence halts immediately (cascade stop) and
    subsequent steps are skipped.

    Args:
        parts (list[str]): List of command parts, expecting the ``-e`` or
            ``--edit`` flag.

    Examples:
        >>> handle_sequence(["@sequence", "-e"])
    """
    has_edit = any(t in ("-e", "--edit") for t in parts[1:])

    if not has_edit:
        print("[!] Usage: @sequence -e")
        print("    The -e (--edit) flag is required.")
        return

    logger.info("[*] @sequence: Opening editor for pipeline input.")
    editor_content = open_editor_for_prompt()
    if editor_content is None:
        return

    parsed_steps = parse_sequence_steps(editor_content)
    if parsed_steps is None or not parsed_steps:
        print("[!] No valid steps found in sequence. Cancelled.")
        return

    total_steps = len(parsed_steps)
    print(f"[*] Sequence Execution: {total_steps} steps detected.")
    print("=" * 50)
    logger.info(f"[*] @sequence: Starting pipeline with {total_steps} steps.")

    for step_idx, step_tasks in enumerate(parsed_steps, 1):
        is_parallel = len(step_tasks) > 1

        if is_parallel:
            print(
                f"[*] Executing Step {step_idx}/{total_steps} [PARALLEL: {len(step_tasks)} tasks]..."
            )
            for t_idx, task in enumerate(step_tasks, 1):
                print(f"    Task {t_idx}: {shlex.join(task)}")

            results = {}
            with ThreadPoolExecutor(max_workers=len(step_tasks)) as executor:
                future_to_task = {
                    executor.submit(dispatch_command, task): t_idx
                    for t_idx, task in enumerate(step_tasks, 1)
                }

                for future in as_completed(future_to_task):
                    t_idx = future_to_task[future]
                    try:
                        results[t_idx] = future.result()
                    except Exception as e:
                        logger.error(f"Step {step_idx}, Task {t_idx} failed: {e}")
                        results[t_idx] = False

            all_success = all(results.values())
            if not all_success:
                failed = [t for t, ok in results.items() if not ok]
                print(
                    f"[!] Step {step_idx}/{total_steps} PARALLEL BLOCK FAILED. Tasks: {failed}"
                )
                print(
                    f"[!] Cascade Stop: {total_steps - step_idx} remaining step(s) skipped."
                )
                logger.error(f"@sequence Cascade Stop at parallel step {step_idx}")
                return

            print(
                f"[✓] Step {step_idx}/{total_steps} completed (all parallel tasks done)."
            )

        else:
            tokens = step_tasks[0]
            print(f"[*] Executing Step {step_idx}/{total_steps}...")
            print(f"    Command: {shlex.join(tokens)}")

            success = dispatch_command(tokens)
            if not success:
                print(f"[!] Step {step_idx}/{total_steps} failed. Halting sequence.")
                print(
                    f"[!] Cascade Stop: {total_steps - step_idx} remaining step(s) skipped."
                )
                logger.error(f"@sequence Cascade Stop at step {step_idx}")
                return

            print(f"[✓] Step {step_idx}/{total_steps} completed successfully.")

        if step_idx < total_steps:
            print("-" * 50)

    print("=" * 50)
    print(f"[✓] Sequence Execution complete. All {total_steps} steps succeeded.")
    logger.info("[*] @sequence: Pipeline completed successfully.")
