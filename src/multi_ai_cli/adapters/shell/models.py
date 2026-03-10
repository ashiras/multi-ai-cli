"""Data models for the Shell adapter."""

from dataclasses import dataclass


@dataclass
class ParsedShInput:
    """
    Structured result of @sh command parsing.

    Attributes:
        command (str | None): Raw command string (direct execution).
        run_file (str | None): Filename to execute (-r flag).
        write_file (str | None): Output artifact filename (-w flag).
        use_shell (bool): Whether --shell was specified.
    """

    command: str | None = None
    run_file: str | None = None
    write_file: str | None = None
    use_shell: bool = False


@dataclass
class ShellResult:
    """
    Result of a shell command execution.

    Attributes:
        exit_code (int): Process exit code.
        stdout (str): Captured standard output.
        stderr (str): Captured standard error.
        duration_ms (float): Execution duration in milliseconds.
        command_display (str): Human-readable command string for display/logging.
        use_shell (bool): Whether shell mode was used.
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    command_display: str
    use_shell: bool
