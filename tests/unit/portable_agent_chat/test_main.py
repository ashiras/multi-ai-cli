import sys
from unittest.mock import MagicMock, patch

# Mock external dependencies before importing the module under test.
for mod in ["multi_ai_cli.main", "multi_ai_cli.utils"]:
    sys.modules[mod] = MagicMock()

from portable_agent_chat.main import main  # noqa: E402


@patch("sys.argv", ["portable-chat", "--agent", "mock_agent"])
@patch("portable_agent_chat.main.startup")
@patch("portable_agent_chat.main.ChatSession")
@patch("portable_agent_chat.main.PromptSession")
@patch("portable_agent_chat.main.clear_thinking_line")
def test_main_loop(
    mock_clear, mock_prompt_session_class, mock_chat_class, mock_startup, capsys
):
    # Prepare mocks.
    mock_chat = MagicMock()
    mock_chat_class.return_value = mock_chat
    mock_chat.send.return_value = "AI answer"
    mock_chat.pending_output = None
    mock_chat.write_last_response.return_value = 10

    mock_prompt_session = MagicMock()
    mock_prompt_session_class.return_value = mock_prompt_session

    # Simulate user input from the prompt session.
    mock_prompt_session.prompt.side_effect = [
        "",  # Ignore empty input.
        KeyboardInterrupt(),  # Handle Ctrl+C and continue.
        ":w result.txt",  # Write command.
        "hello",  # Normal prompt.
        EOFError(),  # Handle Ctrl+D and exit.
    ]

    main()

    # Verify startup was called.
    mock_startup.assert_called_once()

    # Verify the session was initialized correctly.
    mock_chat_class.assert_called_once_with("mock_agent")

    # Verify the command was handled.
    mock_chat.write_last_response.assert_called_once_with("result.txt", overwrite=False)

    # Verify the prompt was sent.
    mock_chat.send.assert_called_once_with("hello")
    mock_clear.assert_called_once()

    # Verify standard output.
    out, err = capsys.readouterr()
    assert "portable-chat" in out
    assert "agent: mock_agent" in out
    assert "wrote result.txt" in out
    assert "AI answer" in out
    assert "bye" in out


@patch("sys.argv", ["portable-chat", "--agent", "mock_agent"])
@patch("portable_agent_chat.main.startup")
@patch("portable_agent_chat.main.ChatSession")
@patch("portable_agent_chat.main.PromptSession")
@patch("portable_agent_chat.main.parse_command")
def test_main_error_handling(
    mock_parse, mock_prompt_session_class, mock_chat_class, mock_startup, capsys
):
    mock_chat = MagicMock()
    mock_chat_class.return_value = mock_chat
    mock_prompt_session = MagicMock()
    mock_prompt_session_class.return_value = mock_prompt_session

    # Setup scenarios:
    # 1. FileExistsError on write_last_response
    # 2. ValueError on parse_command
    from portable_agent_chat.commands import Command, CommandType

    mock_cmd = Command(CommandType.WRITE, "test.txt")

    mock_chat.write_last_response.side_effect = FileExistsError("file exists")
    mock_parse.side_effect = [mock_cmd, ValueError("invalid command")]
    mock_prompt_session.prompt.side_effect = [":w test.txt", "invalid", EOFError()]

    main()

    out, _ = capsys.readouterr()
    assert "error: file exists" in out
    assert "error: invalid command" in out
