from unittest.mock import MagicMock, patch

import pytest

from portable_agent_chat.chat import ChatSession, create_agent_session


@patch("portable_agent_chat.chat.AgentSession")
def test_create_agent_session(mock_agent_session_class):
    session = create_agent_session()
    assert session is not None
    mock_agent_session_class.assert_called_once()
    mock_agent_session_class.assert_called_once()


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_init_unknown_agent(mock_create_session):
    mock_session = MagicMock()
    mock_session.is_valid_agent.return_value = False
    mock_create_session.return_value = mock_session

    with pytest.raises(ValueError, match="Unknown agent: bad_agent"):
        ChatSession("bad_agent")


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_send(mock_create_session):
    mock_session, mock_engine = MagicMock(), MagicMock()
    mock_session.is_valid_agent.return_value = True
    mock_session.get_agent.return_value = mock_engine
    mock_create_session.return_value = mock_session
    mock_engine.call.return_value = "assistant response"

    chat = ChatSession("test_agent")
    res = chat.send("hello!")

    assert res == "assistant response"
    assert chat.last_response == "assistant response"
    mock_engine.call.assert_called_once_with("hello!")


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_send_with_files(mock_create_session, tmp_path):
    mock_session, mock_engine = MagicMock(), MagicMock()
    mock_session.is_valid_agent.return_value = True
    mock_session.get_agent.return_value = mock_engine
    mock_create_session.return_value = mock_session
    mock_engine.call.return_value = "response with files"

    chat = ChatSession("test_agent")

    # Prepare the input file to be loaded with :r.
    in_file = tmp_path / "input.txt"
    in_file.write_text("file data")
    chat.add_pending_read(str(in_file))

    # Prepare the output file to be written with :o.
    out_file = tmp_path / "output.txt"
    chat.set_pending_output(str(out_file))

    res = chat.send("process this")

    # Verify the response and written output.
    assert res == "response with files"
    assert out_file.read_text() == "response with files"
    assert chat.pending_output is None
    assert chat.pending_reads == []

    # Verify the final prompt sent to the engine.
    expected_prompt = (
        f"--- file: {str(in_file)} ---\n"
        f"file data\n"
        f"--- end file: {str(in_file)} ---\n\n"
        "process this"
    )
    mock_engine.call.assert_called_once_with(expected_prompt)


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_send_clears_pending_output_even_if_write_fails(
    mock_create_session,
):
    mock_session, mock_engine = MagicMock(), MagicMock()
    mock_session.is_valid_agent.return_value = True
    mock_session.get_agent.return_value = mock_engine
    mock_create_session.return_value = mock_session
    mock_engine.call.return_value = "assistant response"

    chat = ChatSession("test_agent")
    chat.pending_output = "out.txt"

    with patch(
        "portable_agent_chat.chat.write_new_file",
        side_effect=OSError("write failed"),
    ) as mock_write:
        with pytest.raises(OSError, match="write failed"):
            chat.send("hello!")

    assert chat.last_response == "assistant response"
    assert chat.pending_output is None
    mock_engine.call.assert_called_once_with("hello!")
    mock_write.assert_called_once_with("out.txt", "assistant response")


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_send_clears_pending_reads_if_engine_call_fails(
    mock_create_session, tmp_path
):
    mock_session, mock_engine = MagicMock(), MagicMock()
    mock_session.is_valid_agent.return_value = True
    mock_session.get_agent.return_value = mock_engine
    mock_create_session.return_value = mock_session
    mock_engine.call.side_effect = RuntimeError("model failed")

    chat = ChatSession("test_agent")

    in_file = tmp_path / "input.txt"
    in_file.write_text("file data")
    chat.add_pending_read(str(in_file))

    with pytest.raises(RuntimeError, match="model failed"):
        chat.send("process this")

    assert chat.pending_reads == []


@patch("portable_agent_chat.chat.create_agent_session")
def test_chat_session_write_last_response(mock_create_session, tmp_path):
    mock_session = MagicMock()
    mock_session.is_valid_agent.return_value = True
    mock_create_session.return_value = mock_session

    chat = ChatSession("test_agent")

    with pytest.raises(ValueError, match="no assistant response"):
        chat.write_last_response("out.txt")

    chat.last_response = "test data"
    out_file = tmp_path / "last_resp.txt"
    size = chat.write_last_response(str(out_file))

    assert size == 9
    assert out_file.read_text() == "test data"
