"""
Parsing utilities for Multi-AI CLI.
Handles CLI argument parsing, prompt building, and @sequence step parsing.
"""

import re
import shlex
from dataclasses import dataclass

from .config import config
from .utils import secure_resolve_path

WRITE_MODE_RAW = "raw"  # Constant for raw write mode
WRITE_MODE_CODE = "code"  # Constant for code write mode
# Define valid command keywords
VALID_COMMANDS = {
    "gemini",
    "gpt",
    "claude",
    "grok",
    "local",
    "sh",
    "scrub",
    "flush",
    "efficient",
}

@dataclass
class ParsedInput:
    """
    Structured result of CLI input parsing.

    Attributes:
        a1 (str): Context / title text (bare words, no flags).
        message (str): Text from -m flags (concatenated).
        read_files (list[str]): List of filenames from -r flags.
        write_file (str | None): Output filename from -w / -w:code / -w:raw.
        write_mode (str): "raw" or "code".
        use_editor (bool): Whether -e / --edit was used.

    """

    a1: str = ""  # Context/title text
    message: str = ""  # Concatenated message text
    read_files: list[str] = None  # List of read file names
    write_file: str | None = None  # Output file name
    write_mode: str = WRITE_MODE_RAW  # Write mode, defaults to raw
    use_editor: bool = False  # Flag indicating if editor was used

    def __post_init__(self) -> None:
        """Initialize read_files to an empty list if None."""
        if self.read_files is None:
            self.read_files = []

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

    command: str | None = None  # Raw command to be executed
    run_file: str | None = None  # File to run
    write_file: str | None = None  # Output file name
    use_shell: bool = False  # Flag indicating shell execution


def _parse_write_flag(token: str) -> tuple[str | None, bool]:
    """
    Parse write flag variants and return (mode, is_write_flag).

    Supported:
    - -w, --write          → raw
    - -w:raw, --write:raw  → raw
    - -w:code, --write:code → code

    Args:
        token (str): The token to parse.

    Returns:
        tuple[str | None, bool]: A tuple containing the write mode and a flag indicating if it's a write flag.

    """
    pattern = r"^(?:-w|--write)(?::(\w+))?$"  # Regex pattern for write flag
    m = re.match(pattern, token)  # Match against the pattern
    if not m:
        return None, False  # Return if not a valid write flag

    modifier = m.group(1)  # Extract modifier

    # Determine write mode based on the modifier
    if modifier is None or modifier == "raw":
        return WRITE_MODE_RAW, True
    elif modifier == "code":
        return WRITE_MODE_CODE, True
    else:
        print(f"[!] Unknown write modifier ':{modifier}'. Valid: :raw, :code")
        return None, False


def parse_cli_input(parts: list[str]) -> ParsedInput | None:
    """
    Parse command-line tokens into a structured ParsedInput object.

    Supports:
    - -r / --read <file> (repeatable)
    - -w / --write <file> [:raw|:code]
    - -m / --message <text> (repeatable)
    - -e / --edit
    Bare tokens → a1 (context/title)

    Args:
        parts (list[str]): List of command-line tokens.

    Returns:
        ParsedInput | None: A ParsedInput object if parsing succeeds, or None if it fails.

    """
    parsed = ParsedInput()  # Initialize the ParsedInput object
    indices_to_skip = {0}  # Skip command itself (e.g. @gemini)

    i = 1  # Start parsing after the command
    while i < len(parts):
        token = parts[i]  # Current token to parse

        # -r / --read (repeatable)
        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None  # Error if no filename provided
            parsed.read_files.append(parts[i + 1])  # Append filename to read_files
            indices_to_skip.update({i, i + 1})  # Mark indices to skip
            i += 2  # Move to the next token after the filename
            continue

        # -w / --write [:raw|:code]
        write_mode, is_write = _parse_write_flag(token)  # Parse write flag
        if is_write:
            if write_mode is None:
                return None  # Error if write mode is not valid
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None  # Error if no filename provided
            if parsed.write_file is not None:
                print("[!] Warning: write flag specified multiple times. Overwriting.")
            parsed.write_file = parts[i + 1]  # Set write_file
            parsed.write_mode = write_mode  # Set write_mode
            indices_to_skip.update({i, i + 1})  # Mark indices to skip
            i += 2  # Move to the next token after the filename
            continue

        # -m / --message (repeatable)
        if token in ("-m", "--message"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a text argument.")
                return None  # Error if no text provided
            msg_val = parts[i + 1]
            if parsed.message:
                parsed.message += " " + msg_val  # Concatenate additional message text
            else:
                parsed.message = msg_val  # Set message text
            indices_to_skip.update({i, i + 1})  # Mark indices to skip
            i += 2  # Move to the next token after the message
            continue

        # -e / --edit
        if token in ("-e", "--edit"):
            parsed.use_editor = True  # Set use_editor to True
            indices_to_skip.add(i)  # Mark index to skip
            i += 1  # Move to the next token
            continue

        # Bare token → part of a1
        i += 1  # Move to the next token

    # Collect remaining tokens as a1 (context)
    a1_tokens = [parts[j] for j in range(len(parts)) if j not in indices_to_skip]
    parsed.a1 = " ".join(a1_tokens)  # Join remaining tokens into a1

    return parsed  # Return the parsed input


def build_ai_prompt(parsed: ParsedInput, editor_content: str | None = None) -> str:
    """
    Assemble the final prompt from different sources in fixed priority order:
      1. a1 (bare context/title)
      2. message (-m flags)
      3. editor_content (from -e/--edit)
      4. contents of files from -r flags.

    Raises RuntimeError if file reading fails.

    Args:
        parsed (ParsedInput): The parsed input object containing relevant data.
        editor_content (str | None): The content from the editor, if provided.

    Returns:
        str: The assembled prompt.

    """
    sections = []  # List to hold parts of the prompt

    if parsed.a1.strip():
        sections.append(parsed.a1.strip())  # Add a1 to the sections if it exists

    if parsed.message.strip():
        sections.append(
            parsed.message.strip()
        )  # Add the message to the sections if it exists

    if editor_content and editor_content.strip():
        sections.append(editor_content.strip())  # Add editor content if it exists

    if parsed.read_files:
        file_sections = []  # List to hold the contents of read files
        for filename in parsed.read_files:  # Iterate over each file
            try:
                filepath = secure_resolve_path(
                    filename,
                    "data",
                    config=config,
                )  # Resolve secure path for the file
                with open(filepath, encoding="utf-8") as f:
                    file_content = f.read()  # Read the content of the file
                file_sections.append(
                    f"--- [File: {filename}] ---\n"
                    f"{file_content}\n"
                    f"--- [End of File: {filename}] ---"
                )  # Format the file content for the prompt
            except Exception as e:
                raise RuntimeError(
                    f"Error reading input file '{filename}': {e}"
                )  # Raise error if file read fails

        if file_sections:
            sections.append(
                "\n\n".join(file_sections)
            )  # Add all file sections to the prompt

    return "\n\n".join(sections)  # Return the assembled prompt


def smart_split_steps(text: str) -> list[str]:
    """
    Split editor content into sequential steps using '->' delimiter,
    while respecting quoted strings and escapes.

    Args:
        text (str): The text content to split into steps.

    Returns:
        list[str]: A list of split steps.

    """
    steps = []  # List to hold split steps
    current = []  # List for the current step being built
    in_quote = None  # Track if currently inside a quote
    i = 0  # Index for iteration
    length = len(text)  # Length of the text

    while i < length:
        ch = text[i]  # Current character

        if ch == "\\" and i + 1 < length:  # Handle escape sequences
            current.append(ch)  # Add backslash to current step
            current.append(text[i + 1])  # Add the next character
            i += 2  # Move past the escaped character
            continue

        if ch in ('"', "'"):  # Handle quotes
            if in_quote is None:
                in_quote = ch  # Entering quote
            elif in_quote == ch:
                in_quote = None  # Exiting quote
            current.append(ch)  # Add quote to current step
            i += 1  # Move to the next character
            continue

        if (
            in_quote is None and ch == "-" and i + 1 < length and text[i + 1] == ">"
        ):  # '->' delimiter
            steps.append("".join(current).strip())  # Save current step
            current = []  # Reset current step
            i += 2  # Move past the delimiter
            continue

        current.append(ch)  # Add character to current step
        i += 1  # Move to the next character

    if current:  # If there are remaining characters in the current step
        steps.append("".join(current).strip())  # Save the remaining step

    return [s for s in steps if s]  # Return non-empty steps


def smart_split_parallel(text: str) -> list[str]:
    """
    Split parallel tasks using '||' while respecting quotes and escapes.

    Args:
        text (str): The text content to split into parallel tasks.

    Returns:
        list[str]: A list of split parallel tasks.

    """
    segments = []  # List to hold split segments
    current = []  # List for the current segment being built
    in_quote = None  # Track if currently inside a quote
    i = 0  # Index for iteration
    length = len(text)  # Length of the text

    while i < length:
        ch = text[i]  # Current character

        if ch == "\\" and i + 1 < length:  # Handle escape sequences
            current.append(ch)  # Add backslash to current segment
            current.append(text[i + 1])  # Add the next character
            i += 2  # Move past the escaped character
            continue

        if ch in ('"', "'"):  # Handle quotes
            if in_quote is None:
                in_quote = ch  # Entering quote
            elif in_quote == ch:
                in_quote = None  # Exiting quote
            current.append(ch)  # Add quote to current segment
            i += 1  # Move to the next character
            continue

        if (
            in_quote is None and ch == "|" and i + 1 < length and text[i + 1] == "|"
        ):  # '||' delimiter
            segments.append("".join(current).strip())  # Save current segment
            current = []  # Reset current segment
            i += 2  # Move past the delimiter
            continue

        current.append(ch)  # Add character to current segment
        i += 1  # Move to the next character

    if current:  # If there are remaining characters in the current segment
        segments.append("".join(current).strip())  # Save the remaining segment

    return [s for s in segments if s]  # Return non-empty segments


def normalize_step(step_text: str) -> str:
    """
    Normalize raw step text: remove comments, strip whitespace, collapse spaces.

    Args:
        step_text (str): The raw text of the step to normalize.

    Returns:
        str: The normalized step text.

    """
    lines = step_text.splitlines()  # Split step text into lines
    filtered = []  # List to hold filtered lines
    for line in lines:
        stripped = line.strip()  # Strip leading/trailing whitespace
        if not stripped or stripped.startswith("#"):  # Ignore empty lines and comments
            continue
        filtered.append(stripped)  # Add valid line to filtered list

    normalized = " ".join(filtered)  # Join filtered lines into a single string
    while "  " in normalized:  # Collapse multiple spaces
        normalized = normalized.replace("  ", " ")
    return normalized.strip()  # Return the final normalized step


def detect_parallel_block(normalized_text: str) -> tuple[bool, str]:
    """
    Check if normalized text is a parallel block wrapped in [ ... ].

    Args:
        normalized_text (str): The normalized text to check.

    Returns:
        tuple[bool, str]: Tuple indicating if it's a parallel block and the inner text.

    """
    stripped = normalized_text.strip()  # Strip whitespace
    if stripped.startswith("[") and stripped.endswith("]"):  # Check for parallel block
        return True, stripped[1:-1].strip()  # Return inner text without brackets
    return False, stripped  # Return False if not a parallel block


def parse_sequence_steps(editor_content: str) -> list[list[list[str]]] | None:
    """
    Parse full editor content into nested list of tokenized commands.

    Returns:
        list[list[list[str]]] | None: An outer list of sequential steps,
            each containing middle lists of parallel tasks, and inner lists of tokens,
            or None if parsing/validation fails.

    """
    raw_steps = smart_split_steps(editor_content)  # Split editor content into raw steps

    parsed_steps = []  # List to hold parsed steps
    global_step_idx = 0  # Global step index for error reporting

    for raw in raw_steps:
        normalized = normalize_step(raw)  # Normalize the raw step
        if not normalized:
            continue  # Skip empty normalized steps

        global_step_idx += 1  # Increment step index

        is_parallel, inner_text = detect_parallel_block(
            normalized
        )  # Check if step is parallel

        if is_parallel:
            # Handle parallel commands
            parallel_segments = smart_split_parallel(inner_text)  # Split parallel tasks
            parallel_tasks = []  # List to hold parallel tasks

            for seg_idx, segment in enumerate(parallel_segments, 1):
                seg_normalized = normalize_step(segment)  # Normalize the segment
                if not seg_normalized:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Empty task."
                    )
                    return None  # Return None if empty segment

                try:
                    tokens = shlex.split(
                        seg_normalized
                    )  # Tokenize the normalized segment
                except ValueError as e:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Parse error: {e}"
                    )
                    return None  # Return None if tokenization fails

                if not tokens:
                    continue  # Skip empty tokens

                cmd_key = tokens[0].lower().replace("@", "")  # Normalize command
                if cmd_key not in VALID_COMMANDS:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: Unknown command '{tokens[0]}'"
                    )
                    print(
                        f"    Available: {', '.join('@' + c for c in sorted(VALID_COMMANDS))}"
                    )
                    return None  # Return None if invalid command

                if not tokens[0].startswith("@"):
                    tokens[0] = "@" + tokens[0]  # Prefix command with '@'

                parallel_tasks.append(tokens)  # Add tokens to the parallel tasks

            if not parallel_tasks:
                print(f"[!] Step {global_step_idx}: No valid tasks in parallel block.")
                return None  # Return None if no valid tasks

            parsed_steps.append(parallel_tasks)  # Append parallel tasks to the result

        else:
            # Handle sequential commands
            try:
                tokens = shlex.split(normalized)  # Tokenize the normalized step
            except ValueError as e:
                print(f"[!] Step {global_step_idx}: Parse error: {e}")
                return None  # Return None if tokenization fails

            if not tokens:
                continue  # Skip empty tokens

            cmd_key = tokens[0].lower().replace("@", "")  # Normalize command
            if cmd_key not in VALID_COMMANDS:
                print(f"[!] Step {global_step_idx}: Unknown command '{tokens[0]}'")
                print(
                    f"    Available: {', '.join('@' + c for c in sorted(VALID_COMMANDS))}"
                )
                return None  # Return None if invalid command

            if not tokens[0].startswith("@"):
                tokens[0] = "@" + tokens[0]  # Prefix command with '@'

            parsed_steps.append([tokens])  # Append tokens as a new step

    return parsed_steps  # Return the list of parsed sequence steps


def _parse_sh_input(parts: list[str]) -> ParsedShInput | None:
    """
    Parse @sh command tokens into ParsedShInput.

    Syntax: @sh ["command"] [-r file] [-w output] [--shell]

    Args:
        parts (list[str]): The list of command tokens.

    Returns:
        ParsedShInput | None: A ParsedShInput object if parsing succeeds, or None if it fails.

    """
    parsed = ParsedShInput()  # Initialize the ParsedShInput object
    bare_tokens = []  # List to hold bare command tokens

    i = 1  # Skip '@sh'
    while i < len(parts):
        token = parts[i]  # Current token to parse

        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None  # Error if no filename provided
            if parsed.run_file is not None:
                print("[!] @sh: -r specified more than once.")
            parsed.run_file = parts[i + 1]  # Set run_file to the next token
            i += 2  # Move to the next token after the filename
            continue

        if token in ("-w", "--write"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None  # Error if no filename provided
            if parsed.write_file is not None:
                print("[!] @sh: -w specified more than once.")
            parsed.write_file = parts[i + 1]  # Set write_file to the next token
            i += 2  # Move to the next token after the filename
            continue

        if token == "--shell":
            parsed.use_shell = True  # Set use_shell to True if --shell specified
            i += 1  # Move to the next token
            continue

        bare_tokens.append(token)  # Add non-flag token to bare_tokens
        i += 1  # Move to the next token

    if bare_tokens:
        parsed.command = " ".join(bare_tokens)  # Join bare tokens into a command string

    if (
        not parsed.command and not parsed.run_file
    ):  # Check if both command and run_file are empty
        print("[!] @sh: No command or file specified.")
        return None  # Return None if neither specified

    return parsed  # Return the parsed input object
