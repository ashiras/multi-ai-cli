import configparser

import pytest

from multi_ai_cli.utils import (
    _make_continue_prompt,
    _tail_of,
    extract_code_block,
    secure_resolve_path,
)


@pytest.fixture
def mock_config(tmp_path):
    """
    Create a mock config and safe temporary directories for testing path resolution.
    """
    config = configparser.ConfigParser()
    config.add_section("Paths")

    # Create temporary directories representing 'work_data' and 'prompts'
    work_data_dir = tmp_path / "work_data"
    work_data_dir.mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    config.set("Paths", "work_data", str(work_data_dir))
    config.set("Paths", "work_efficient", str(prompts_dir))

    return config, tmp_path


def test_secure_resolve_path_valid(mock_config):
    """
    Test resolving a valid filename within the allowed directory.
    """
    config, tmp_path = mock_config

    # Test resolving a file in the 'data' category
    result = secure_resolve_path("test_file.txt", category="data", config=config)
    expected_path = str(tmp_path / "work_data" / "test_file.txt")

    assert result == expected_path


def test_secure_resolve_path_directory_traversal(mock_config):
    """
    Test that attempting to access files outside the base directory raises an error.
    """
    config, _ = mock_config

    # Attempting to go up one directory using '../'
    malicious_filename = "../secret_system_file.txt"

    # Verify that a PermissionError is raised to prevent directory traversal
    with pytest.raises(
        PermissionError, match="Security Alert: Directory traversal blocked"
    ):
        secure_resolve_path(malicious_filename, category="data", config=config)


def test_extract_code_block():
    """
    Test the extraction of code blocks from Markdown text.
    """
    # UIのマークダウンパーサーのバグを回避するため、
    # バッククォート3つを直接書かずに `chr(96) * 3` で動的に生成します。
    fence = chr(96) * 3

    # 1. Text without any code blocks -> should return the original text
    plain_text = "This is just a normal sentence."
    assert extract_code_block(plain_text) == plain_text

    # 2. Text with a single code block
    text_with_code = (
        f"Here is the code:\n{fence}python\nprint('Hello')\n{fence}\nEnd of message."
    )
    assert extract_code_block(text_with_code) == "print('Hello')"

    # 3. Text with multiple code blocks
    text_multiple_blocks = (
        f"Block 1:\n{fence}\nCode 1\n{fence}\nBlock 2:\n{fence}\nCode 2\n{fence}"
    )
    assert extract_code_block(text_multiple_blocks) == "Code 1\n\nCode 2"


def test_tail_of():
    """
    Test the _tail_of string helper function.
    """
    text = "abcdefghij"

    # Cut exactly 3 characters from the end
    assert _tail_of(text, 3) == "hij"

    # Requesting more characters than the string has should return the whole string
    assert _tail_of("abc", 10) == "abc"

    # Empty string handling
    assert _tail_of("", 5) == ""


def test_make_continue_prompt():
    """
    Test that the continuation prompt includes the provided tail text.
    """
    tail_text = "print('Hello Wor"
    result = _make_continue_prompt(tail_text)

    assert "Continue EXACTLY from where you stopped" in result
    assert tail_text in result
