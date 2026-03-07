import pytest
from unittest.mock import MagicMock
from multi_ai_cli.engines import OpenAIEngine, ClaudeEngine, AIEngine

@pytest.fixture
def mock_openai_client():
    """
    Creates a fake (mocked) OpenAI client.
    This prevents actual API calls and billing during tests.
    """
    client = MagicMock()
    
    # Simulate the response structure of the OpenAI API
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from mock AI!"
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    
    # When client.chat.completions.create is called, return our mock response
    client.chat.completions.create.return_value = mock_response
    
    return client

def test_engine_history_management(mock_openai_client):
    """
    Test common AIEngine features like memory scrubbing, persona loading, 
    and history trimming using OpenAIEngine as a concrete implementation.
    """
    engine = OpenAIEngine("TestGPT", "gpt-test", mock_openai_client)
    
    # 1. Test scrub() (Clearing history)
    engine.history = [{"role": "user", "content": "Previous chat"}]
    engine.scrub()
    assert len(engine.history) == 0, "Scrub should clear the history"

    # 2. Test load_persona()
    engine.load_persona("You are a helpful test assistant.", "test_persona.txt")
    assert engine.system_prompt == "You are a helpful test assistant."
    assert len(engine.history) == 0, "Loading persona should reset history"

    # 3. Test _trim_history()
    # Set max_turns to 1 (meaning it should only keep 1 user + 1 assistant msg = 2 total)
    engine.max_turns = 1 
    engine.history = [
        {"role": "user", "content": "Old Q"},
        {"role": "assistant", "content": "Old A"},
        {"role": "user", "content": "New Q"},
        {"role": "assistant", "content": "New A"},
    ]
    engine._trim_history()
    assert len(engine.history) == 2, "History should be trimmed to max_turns * 2"
    assert engine.history[0]["content"] == "New Q", "Older messages should be removed"

def test_openai_engine_call(mock_openai_client):
    """
    Test the call method of OpenAIEngine to ensure it formats history 
    correctly and handles the mock response.
    """
    engine = OpenAIEngine("TestGPT", "gpt-test", mock_openai_client)
    
    # Call the engine with a prompt
    response = engine.call("Hi AI!")
    
    # Verify the response matches our mock
    assert response == "Hello from mock AI!"
    
    # Verify history is correctly updated
    assert len(engine.history) == 2
    assert engine.history[0]["role"] == "user"
    assert engine.history[0]["content"] == "Hi AI!"
    assert engine.history[1]["role"] == "assistant"
    assert engine.history[1]["content"] == "Hello from mock AI!"
    
    # Verify that the underlying API client was actually called
    mock_openai_client.chat.completions.create.assert_called_once()