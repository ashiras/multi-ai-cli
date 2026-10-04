"""
Command handlers for Multi-AI CLI.

Processes user commands (@agent, @sh, @sequence, @scrub, etc.) and
dispatches them. All agent interactions go through AgentSession to
ensure proper instance isolation.
"""

import os
import shlex
import subprocess
from typing import TYPE_CHECKING

from .adapters.shell import ShellAdapter
from .adapters.shell.adapter import ShellCommandBuildError
from .adapters.shell.models import ShellResult
from .config import config, logger
from .flow_context import get_flow_execution_context
from .flow_executor import execute_flow
from .flow_parser import FlowSyntaxError, parse_flow
from .flow_validator import FlowValidationError, validate_flow
from .parsers import (
    ParsedInput,
    ParsedShInput,
    _parse_sh_input,
    build_ai_prompt,
    parse_cli_input,
)
from .utils import (
    _console_lock,
    clear_thinking_line,
    extract_code_block,
    open_editor_for_prompt,
    safe_eprint,
    safe_print,
    secure_resolve_path,
)

if TYPE_CHECKING:
    from .session import AgentSession

WRITE_MODE_RAW = "raw"
WRITE_MODE_CODE = "code"


def handle_pause(parts: list[str]) -> bool:
    """
    Handle the @pause control command for interactive pipeline execution.

    Accepts only ``@pause`` with no extra arguments. Prompts the user to
    either continue the pipeline by pressing Enter or abort it by typing
    ``q``.

    Args:
        parts: Tokenized command parts.

    Returns:
        True if the user continues, otherwise False.
    """
    if len(parts) != 1:
        print("[!] Usage: @pause")
        return False

    while True:
        try:
            answer = input(" ").strip().lower()
        except EOFError:
            print("[!] @pause could not read interactive input.")
            logger.error("@pause: EOF while waiting for user input")
            return False

        if answer == "":
            logger.info("@pause: continued by user")
            return True
        if answer == "q":
            logger.info("@pause: aborted by user")
            return False

        print("[!] Invalid input. Press Enter to continue, or type 'q' to abort.")


def dispatch_command(parts: list[str], session: "AgentSession") -> bool:
    """
    Route parsed command tokens to the appropriate handler.

    Args:
        parts: List of command parts to dispatch.
        session: The current agent session.

    Returns:
        True if the command succeeded, otherwise False.
    """
    if not parts:
        return False

    cmd = parts[0].lower()

    if cmd in ["@scrub", "@flush"]:
        handle_scrub(parts, session)
        return True

    if cmd == "@pause":
        return handle_pause(parts)

    if cmd == "@efficient":
        handle_efficient(parts, session)
        return True

    if cmd == "@sequence":
        return handle_sequence(parts, session)

    if cmd == "@sh":
        return handle_sh(parts)

    if cmd == "@figma.pull":
        from .adapters.figma.facade import handle_figma_pull

        return handle_figma_pull(parts)

    if cmd == "@figma.push":
        from .adapters.figma.facade import handle_figma_push

        return handle_figma_push(parts)

    if cmd == "@github.repo":
        from .adapters.github.facade import handle_github_repo

        return handle_github_repo(parts)

    if cmd == "@github.tree":
        from .adapters.github.facade import handle_github_tree

        return handle_github_tree(parts)

    if cmd == "@github.file":
        from .adapters.github.facade import handle_github_file

        return handle_github_file(parts)

    if cmd == "@github.issue":
        from .adapters.github.facade import handle_github_issue

        return handle_github_issue(parts)

    if cmd == "@github.issues":
        from .adapters.github.facade import handle_github_issues

        return handle_github_issues(parts)

    target_key = cmd.replace("@", "").lower()
    if session.is_valid_agent(target_key):
        return handle_ai_interaction(parts, session)

    safe_eprint(f"[!] Unknown command: '{cmd}'")
    available_agents = session.agent_keys()
    safe_eprint(
        f"    Available: {', '.join('@' + k for k in sorted(available_agents))}, "
        f"@pause, @efficient, @scrub, @sequence, @sh, @figma.pull, @figma.push, "
        f"@github.repo, @github.tree, @github.file, @github.issue, @github.issues, exit"
    )
    return False


def handle_scrub(parts: list[str], session: "AgentSession") -> None:
    """
    Handle @scrub / @flush to clear agent history.

    Only affects agents already instantiated in the current session.

    Args:
        parts: List of command parts.
        session: The current agent session.
    """
    target = parts[1].lower() if len(parts) > 1 else "all"
    valid_targets = set(session.agent_keys()) | {"all"}

    if target not in valid_targets:
        print(f"[!] Invalid target '{target}'. Valid: {', '.join(valid_targets)}")
        return

    if target == "all":
        scrubbed = session.scrub()
        for key in scrubbed:
            engine = session.get_agent(key)
            print(f"[*] {engine.name} memory scrubbed.")
    else:
        if session.has_agent(target):
            session.scrub(target)
            engine = session.get_agent(target)
            print(f"[*] {engine.name} memory scrubbed.")
        else:
            print(
                f"[*] @{target} has not been used in this session yet. Nothing to scrub."
            )


def handle_efficient(parts: list[str], session: "AgentSession") -> None:
    """
    Handle @efficient command to load persona files.

    Args:
        parts: List of command parts.
        session: The current agent session.
    """
    if len(parts) < 2:
        print("[!] Usage: @efficient [target/all] <filename.txt>")
        return

    all_agent_keys = session.agent_keys()

    if parts[1].lower() in (all_agent_keys + ["all"]):
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

        if target == "all":
            for agent_key in all_agent_keys:
                engine = session.get_agent(agent_key)
                engine.load_persona(content, filename)
                print(f"[*] {engine.name} persona loaded: '{filename}'.")
        else:
            engine = session.get_agent(target)
            engine.load_persona(content, filename)
            print(f"[*] {engine.name} persona loaded: '{filename}'.")
    except Exception as e:
        safe_eprint(f"[!] Persona loading failed: {e}")


def handle_ai_interaction(parts: list[str], session: "AgentSession") -> bool:
    """
    Handle interaction with a specific AI agent.

    Supports flags: -m, -r, -w[:raw|:code], -e.

    Args:
        parts: Command parts to interact with the AI.
        session: The current agent session.

    Returns:
        True if interaction succeeded, otherwise False.
    """
    target_key = parts[0].lower().replace("@", "")
    engine = session.get_agent(target_key)

    if not engine:
        safe_eprint(f"[!] Agent '@{target_key}' not found.")
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
        safe_eprint(f"[!] {e}")
        logger.error(f"AI prompt build error: {e}")
        return False

    flow_context = get_flow_execution_context()
    branch_label = flow_context.branch_label

    if branch_label:
        thinking_prefix = f"[{branch_label}]"
        response_header = f"--- [{branch_label}] {engine.name} ---"
    else:
        thinking_prefix = "[*]"
        response_header = f"--- {engine.name} ---"

    if not prompt_main.strip():
        safe_eprint("[!] No prompt to send. Provide text, use -e, -m, or -r.")
        return False

    logger.info(f"@User ({engine.name}): {prompt_main}")

    with _console_lock:
        print(
            f"{thinking_prefix} {engine.name} is thinking...",
            end="\r",
            flush=True,
        )

    logger.info(f"{thinking_prefix} {engine.name} is thinking...")

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
            safe_print(f"\n{response_header}\n{result}\n")

        return True

    except Exception as e:
        clear_thinking_line()
        safe_eprint(f"[!] AI Engine Error: {e}")
        logger.error(f"AI interaction error: {e}")
        return False


def handle_sh(parts: list[str]) -> bool:
    """
    Handle @sh command for local shell execution with artifact capture.

    Args:
        parts: List of command parts.

    Returns:
        True if shell command execution succeeded, otherwise False.
    """
    parsed: ParsedShInput | None = _parse_sh_input(parts)
    if parsed is None:
        return False

    adapter = ShellAdapter()

    def _resolve_path(filename: str) -> str:
        return secure_resolve_path(filename, "data", config=config)

    try:
        cmd, use_shell = adapter.build_command(parsed, resolve_path_fn=_resolve_path)
    except PermissionError as e:
        safe_eprint(f"[!] @sh: {e}")
        logger.error(f"@sh: Permission error: {e}")
        return False
    except ShellCommandBuildError as e:
        safe_eprint(f"[!] @sh: {e}")
        logger.error(f"@sh: Build error: {e}")
        return False

    cmd_display = shlex.join(cmd) if isinstance(cmd, list) else cmd

    logger.info(f"@sh: Executing '{cmd_display}' (shell={use_shell})")
    print(f"[*] @sh: Executing: {cmd_display}")
    if use_shell:
        print("[*] @sh: --shell mode enabled (shell=True)")

    try:
        shell_result: ShellResult = adapter.execute_command(cmd, use_shell)
    except FileNotFoundError as e:
        safe_eprint(f"[!] @sh: Command not found: {e}")
        logger.error(f"@sh: Command not found: {e}")
        return False
    except subprocess.TimeoutExpired:
        safe_eprint("[!] @sh: Command timed out (300s limit).")
        logger.error(f"@sh: Timeout for '{cmd_display}'")
        return False
    except OSError as e:
        safe_eprint(f"[!] @sh: Execution error: {e}")
        logger.error(f"@sh: Execution error: {e}")
        return False

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
            safe_eprint(f"[!] @sh: Error writing artifact: {e}")
            logger.error(f"@sh: Artifact write error: {e}")

    return exit_code == 0


def handle_sequence(parts: list[str], session: "AgentSession") -> bool:
    """
    Handle @sequence command.

    Supported input modes:

        @sequence -e
        @sequence --edit
        @sequence -f <file>
        @sequence --file <file>

    Args:
        parts: List of command parts.
        session: The current agent session.

    Returns:
        True if the entire Flow completed successfully, otherwise False.
    """
    args = parts[1:]

    has_edit = any(token in ("-e", "--edit") for token in args)
    file_flag_indexes = [
        index for index, token in enumerate(args) if token in ("-f", "--file")
    ]

    if has_edit and file_flag_indexes:
        safe_eprint("[!] @sequence: -e/--edit and -f/--file cannot be used together.")
        safe_eprint("[!] Usage:")
        safe_eprint("    @sequence -e")
        safe_eprint("    @sequence -f <file>")
        return False

    flow_content: str | None = None

    if has_edit:
        if len(args) != 1:
            safe_eprint("[!] Usage: @sequence -e")
            return False

        logger.info("[*] @sequence: Opening editor for Flow input.")
        flow_content = open_editor_for_prompt()

        if flow_content is None:
            return False

    elif file_flag_indexes:
        if len(file_flag_indexes) > 1:
            safe_eprint("[!] @sequence: -f/--file specified more than once.")
            return False

        file_flag_index = file_flag_indexes[0]

        if file_flag_index + 1 >= len(args):
            safe_eprint("[!] @sequence: -f/--file requires a filename.")
            safe_eprint("[!] Usage: @sequence -f <file>")
            return False

        if len(args) != 2:
            safe_eprint("[!] Usage: @sequence -f <file>")
            return False

        filename = args[file_flag_index + 1]

        try:
            filepath = secure_resolve_path(
                filename,
                "efficient",
                config=config,
            )

            with open(filepath, encoding="utf-8") as f:
                flow_content = f.read()

            logger.info(f"[*] @sequence: Loaded Flow from '{filename}'.")

        except Exception as exc:
            safe_eprint(
                f"[!] @sequence: Failed to load sequence file '{filename}': {exc}"
            )
            logger.error(f"@sequence file load failed for '{filename}': {exc}")
            return False

    else:
        safe_eprint("[!] Usage:")
        safe_eprint("    @sequence -e")
        safe_eprint("    @sequence -f <file>")
        return False

    try:
        flow_ast = parse_flow(flow_content)
    except FlowSyntaxError as exc:
        safe_eprint(f"[!] Sequence syntax error: {exc}")
        logger.error(f"@sequence syntax error: {exc}")
        return False

    try:
        validate_flow(flow_ast)
    except FlowValidationError as exc:
        safe_eprint(f"[!] Sequence validation error: {exc}")
        logger.error(f"@sequence validation error: {exc}")
        return False

    print("[*] Sequence Execution started.")
    print("=" * 50)

    logger.info("[*] @sequence: Starting AST Flow execution.")

    success = execute_flow(
        flow_ast,
        session,
    )

    print("=" * 50)

    if not success:
        safe_eprint("[!] Sequence Execution failed.")
        logger.error("@sequence: Flow execution failed.")
        return False

    print("[✓] Sequence Execution complete.")
    logger.info("[*] @sequence: Flow execution completed successfully.")

    return True
