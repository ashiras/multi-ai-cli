"""
Shell adapter implementation.

Encapsulates all shell execution logic: command building,
subprocess execution, output capture, and artifact formatting.

Design principles:
    - No print() calls — UI is the handler's responsibility.
    - No logger calls — logging is the handler's responsibility.
    - Errors are raised as exceptions, not printed.
"""

import json
import os
import shlex
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from .models import ParsedShInput, ShellResult

RUNNER_MAP: dict[str, list[str]] = {
    ".py": ["python3"],
    ".sh": ["bash"],
    ".rb": ["ruby"],
    ".js": ["node"],
    ".ts": ["npx", "ts-node"],
    ".pl": ["perl"],
    ".lua": ["lua"],
    ".r": ["Rscript"],
    ".R": ["Rscript"],
}


class ShellCommandBuildError(Exception):
    """Raised when shell command building fails."""

    pass


class ShellAdapter:
    """
    Adapter for local shell command execution.

    Responsibilities:
        - Command building from ParsedShInput
        - Runner resolution for -r files
        - subprocess execution with timeout
        - stdout / stderr / exit code capture
        - Artifact formatting (text / JSON)

    This adapter does not perform any print() or logging calls.
    All UI output and logging is the caller's responsibility.
    Errors are communicated via exceptions or structured return values.
    """

    def __init__(self) -> None:
        """Initialize ShellAdapter. Currently stateless."""
        pass

    def build_command(
        self,
        parsed: ParsedShInput,
        resolve_path_fn: Callable[[str], str] | None = None,
    ) -> tuple[list[str] | str, bool]:
        """
        Build the final command list or string from ParsedShInput.

        Resolves runner for -r files or uses shlex for direct commands.

        Args:
            parsed: Parsed shell input.
            resolve_path_fn: Callable to resolve file paths securely.
                Signature: (filename: str) -> str.
                If None, raw filenames are used (mainly for testing).

        Returns:
            Tuple of (command, use_shell).

        Raises:
            ShellCommandBuildError: If command building fails due to
                invalid input (both -r and command, missing command,
                file not found, no runner, parse error, etc.).
            PermissionError: If path resolution blocks directory traversal.
        """
        if parsed.run_file and parsed.command:
            raise ShellCommandBuildError(
                "Cannot use both -r <file> and direct command."
            )

        if not parsed.run_file and not parsed.command:
            raise ShellCommandBuildError("No command or file specified.")

        if parsed.run_file:
            if resolve_path_fn is not None:
                filepath = resolve_path_fn(parsed.run_file)
            else:
                filepath = parsed.run_file

            if not os.path.isfile(filepath):
                raise ShellCommandBuildError(f"File not found: '{parsed.run_file}'")

            runner = self._resolve_runner(parsed.run_file)
            if runner is None:
                ext = Path(parsed.run_file).suffix
                raise ShellCommandBuildError(f"No runner for extension '{ext}'.")

            if isinstance(runner, str):
                runner = [runner]

            cmd = runner + [filepath]
            return cmd, parsed.use_shell

        if parsed.use_shell:
            if parsed.command is None:
                raise ShellCommandBuildError("No command provided.")
            return parsed.command, True

        if parsed.command is None:
            raise ShellCommandBuildError("No command provided.")

        try:
            cmd = shlex.split(parsed.command)
        except ValueError as e:
            raise ShellCommandBuildError(f"Command parse error: {e}") from e

        if not cmd:
            raise ShellCommandBuildError("Empty command.")

        return cmd, False

    def execute_command(
        self,
        cmd: list[str] | str,
        use_shell: bool,
        timeout: int = 300,
    ) -> ShellResult:
        """
        Execute a pre-built shell command via subprocess.

        Args:
            cmd: Command to execute (list for exec, string for shell).
            use_shell: Whether to use shell mode.
            timeout: Maximum execution time in seconds.

        Returns:
            ShellResult with execution details.

        Raises:
            FileNotFoundError: If the command executable is not found.
            subprocess.TimeoutExpired: If the command exceeds the timeout.
            OSError: If another OS-level execution error occurs.
        """
        cmd_display = shlex.join(cmd) if isinstance(cmd, list) else cmd

        start_time = time.monotonic()

        result = subprocess.run(
            cmd,
            shell=use_shell,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        end_time = time.monotonic()
        duration_ms = (end_time - start_time) * 1000

        return ShellResult(
            exit_code=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            duration_ms=duration_ms,
            command_display=cmd_display,
            use_shell=use_shell,
        )

    @staticmethod
    def _resolve_runner(filename: str) -> list[str] | None:
        """
        Resolve the appropriate runner for the given filename's extension.

        Args:
            filename: The name of the file.

        Returns:
            List of runner command parts or None if not found.
        """
        ext = Path(filename).suffix.lower()
        if Path(filename).suffix == ".R":
            ext = ".R"
        return RUNNER_MAP.get(ext)

    @staticmethod
    def format_artifact_text(
        cmd_display: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> str:
        """
        Format shell execution result as plain text artifact.

        Args:
            cmd_display: Command that was executed.
            exit_code: Exit code of the command.
            stdout: Standard output.
            stderr: Standard error.
            duration_ms: Duration in milliseconds.

        Returns:
            Formatted artifact as text.
        """
        status = "SUCCESS" if exit_code == 0 else "FAILURE"
        lines = [
            "# Shell Execution Artifact",
            f"- **Command:** `{cmd_display}`",
            f"- **Status:** {status}",
            f"- **Exit Code:** {exit_code}",
            f"- **Duration:** {duration_ms:.1f}ms",
            "",
        ]

        if stdout.strip():
            lines.extend(["## stdout", "```", stdout.rstrip(), "```", ""])
        else:
            lines.append("## stdout\n_(empty)_\n")

        if stderr.strip():
            lines.extend(["## stderr", "```", stderr.rstrip(), "```", ""])
        else:
            lines.append("## stderr\n_(empty)_\n")

        return "\n".join(lines)

    @staticmethod
    def format_artifact_json(
        cmd_display: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> str:
        """
        Format shell execution result as JSON artifact.

        Args:
            cmd_display: Command that was executed.
            exit_code: Exit code of the command.
            stdout: Standard output.
            stderr: Standard error.
            duration_ms: Duration in milliseconds.

        Returns:
            Formatted artifact as JSON string.
        """
        artifact = {
            "command": cmd_display,
            "status": "success" if exit_code == 0 else "failure",
            "exit_code": exit_code,
            "duration_ms": round(duration_ms, 1),
            "stdout": stdout,
            "stderr": stderr,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        return json.dumps(artifact, indent=2, ensure_ascii=False)
