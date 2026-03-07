import pytest
from unittest.mock import MagicMock, patch
from multi_ai_cli import handlers

@pytest.fixture
def mock_engines():
    """
    Replace the global 'engines' dictionary in handlers.py with a mock engine.
    This prevents the handler from trying to access real AI configurations.
    """
    mock_engine = MagicMock()
    mock_engine.name = "MockAI"
    mock_engine.call.return_value = "Mock response from AI"
    
    # Patch the dictionary only during the test
    with patch.dict(handlers.engines, {"mockai": mock_engine}, clear=True):
        yield mock_engine

def test_dispatch_command_unknown():
    """
    Test routing behavior for an unknown command.
    """
    # Should return False and print an error message safely
    result = handlers.dispatch_command(["@unknown"])
    assert result is False

def test_handle_scrub(mock_engines):
    """
    Test if the @scrub command correctly calls the scrub method on the engine.
    """
    # Execute scrub for all engines
    handlers.handle_scrub(["@scrub", "all"])
    
    # Verify our mock engine's scrub method was triggered
    mock_engines.scrub.assert_called_once()

def test_handle_ai_interaction_basic(mock_engines):
    """
    Test basic AI interaction routing without an editor.
    """
    # parts: ["@mockai", "Hello", "AI"]
    result = handlers.handle_ai_interaction(["@mockai", "Hello", "AI"])
    
    assert result is True
    # Verify the AI was called with the combined bare tokens as the prompt
    mock_engines.call.assert_called_once_with("Hello AI")

@patch("multi_ai_cli.handlers.subprocess.run")
def test_handle_sh_direct_command(mock_subprocess_run):
    """
    Test @sh command execution safely by mocking subprocess.run.
    """
    # 1. Setup the fake result of the subprocess
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello world\n"
    mock_result.stderr = ""
    mock_subprocess_run.return_value = mock_result

    # 2. Execute the handler
    result = handlers.handle_sh(["@sh", "echo", "hello world"])

    # 3. Verify the execution
    assert result is True
    
    # Verify subprocess.run was called exactly once
    mock_subprocess_run.assert_called_once()
    
    # Verify it was called with the correctly parsed command list
    # Because _parse_sh_input joins bare tokens and shlex.split separates them
    called_args = mock_subprocess_run.call_args[0][0]
    assert called_args == ["echo", "hello", "world"]

def test_handle_sequence_requires_edit_flag(capsys):
    """
    Test that @sequence fails safely if the -e or --edit flag is missing.
    """
    # Execute without -e
    handlers.handle_sequence(["@sequence"])
    
    # Capture the print output
    captured = capsys.readouterr()
    
    assert "Usage: @sequence -e" in captured.out
    assert "flag is required" in captured.out