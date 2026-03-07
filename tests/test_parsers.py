import pytest
from multi_ai_cli.parsers import (
    _parse_write_flag,
    parse_cli_input,
    smart_split_steps,
    WRITE_MODE_RAW,
    WRITE_MODE_CODE
)

def test_parse_write_flag():
    """
    Test if the write flag modifier parser correctly identifies modes.
    """
    # Test default raw mode
    assert _parse_write_flag("-w") == (WRITE_MODE_RAW, True)
    assert _parse_write_flag("--write") == (WRITE_MODE_RAW, True)
    assert _parse_write_flag("-w:raw") == (WRITE_MODE_RAW, True)

    # Test code mode
    assert _parse_write_flag("-w:code") == (WRITE_MODE_CODE, True)
    assert _parse_write_flag("--write:code") == (WRITE_MODE_CODE, True)

    # Test invalid modifier (should return None, False)
    assert _parse_write_flag("-w:invalid") == (None, False)

    # Test non-write flags
    assert _parse_write_flag("-m") == (None, False)

def test_parse_cli_input_basic():
    """
    Test parsing basic CLI input without complex flags.
    """
    # parts[0] is usually the command like '@gemini'
    parts = ["@gemini", "Translate", "this", "text"]
    parsed = parse_cli_input(parts)

    assert parsed is not None
    assert parsed.a1 == "Translate this text"
    assert parsed.message == ""
    assert parsed.read_files == []
    assert parsed.write_file is None

def test_parse_cli_input_complex():
    """
    Test parsing CLI input with multiple flags and values.
    """
    parts = [
        "@gpt", 
        "Context text", 
        "-m", "First message", 
        "-r", "input1.txt", 
        "-m", "Second message", 
        "-w:code", "output.py",
        "-e"
    ]
    parsed = parse_cli_input(parts)

    assert parsed is not None
    assert parsed.a1 == "Context text"
    # Messages should be concatenated with a space
    assert parsed.message == "First message Second message"
    assert parsed.read_files == ["input1.txt"]
    assert parsed.write_file == "output.py"
    assert parsed.write_mode == WRITE_MODE_CODE
    assert parsed.use_editor is True

def test_parse_cli_input_errors():
    """
    Test parsing failures when required arguments for flags are missing.
    """
    # Missing filename after -r
    assert parse_cli_input(["@claude", "-r"]) is None
    
    # Missing filename after -w
    assert parse_cli_input(["@gpt", "-w:code"]) is None
    
    # Missing text after -m
    assert parse_cli_input(["@gemini", "-m"]) is None

def test_smart_split_steps():
    """
    Test the custom sequence splitter focusing on quote and escape handling.
    """
    # Basic split
    result = smart_split_steps("step 1 -> step 2 -> step 3")
    assert result == ["step 1", "step 2", "step 3"]

    # Split with quotes (should NOT split inside quotes)
    text_with_quotes = "echo 'don\\'t split -> here' -> next step"
    result = smart_split_steps(text_with_quotes)
    assert result == ["echo 'don\\'t split -> here'", "next step"]

    # Split with double quotes
    text_with_double_quotes = 'print("->") -> @gemini'
    result = smart_split_steps(text_with_double_quotes)
    assert result == ['print("->")', '@gemini']