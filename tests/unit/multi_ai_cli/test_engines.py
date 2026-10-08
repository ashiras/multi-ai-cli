"""Tests for multi_ai_cli.engines module — unit tests with mocked SDK clients."""

from unittest.mock import MagicMock

import pytest

from multi_ai_cli.engines import AIError, ClaudeEngine, GeminiEngine, OpenAIEngine


class TestAIEngineBase:
    """Tests for base AIEngine functionality via OpenAIEngine."""

    def test_init(self):
        client = MagicMock()
        engine = OpenAIEngine(name="Test", model_name="gpt-4", client=client)
        assert engine.name == "Test"
        assert engine.model_name == "gpt-4"
        assert engine.system_prompt == ""
        assert engine.history == []
        assert engine.filter_mode is False

    def test_scrub(self):
        client = MagicMock()
        engine = OpenAIEngine(name="Test", model_name="gpt-4", client=client)
        engine.history = [{"role": "user", "content": "hi"}]
        engine.scrub()
        assert engine.history == []

    def test_load_persona(self):
        client = MagicMock()
        engine = OpenAIEngine(name="Test", model_name="gpt-4", client=client)
        engine.history = [{"role": "user", "content": "old"}]
        engine.load_persona("You are a coder.", "coder.txt")
        assert engine.system_prompt == "You are a coder."
        assert engine.history == []

    def test_trim_history(self):
        client = MagicMock()
        engine = OpenAIEngine(name="Test", model_name="gpt-4", client=client)
        engine.max_turns = 5
        # Add 12 messages (6 turns)
        engine.history = [{"role": "user", "content": f"msg{i}"} for i in range(12)]
        engine._trim_history()
        # Should keep 10 messages (5 turns)
        assert len(engine.history) == 10

    def test_get_client(self):
        client = MagicMock()
        engine = OpenAIEngine(name="Test", model_name="gpt-4", client=client)
        assert engine.get_client() is client


class TestOpenAIEngine:
    def test_call_success(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello!"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response

        engine = OpenAIEngine(name="GPT", model_name="gpt-4", client=client)
        result = engine.call("Hi")
        assert result == "Hello!"
        assert len(engine.history) == 2
        assert engine.history[0]["role"] == "user"
        assert engine.history[1]["role"] == "assistant"

    def test_call_with_system_prompt(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        client.chat.completions.create.return_value = mock_response

        engine = OpenAIEngine(name="GPT", model_name="gpt-4", client=client)
        engine.system_prompt = "You are helpful."
        engine.call("Hello")

        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."

    def test_call_api_error(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API Error")

        engine = OpenAIEngine(name="GPT", model_name="gpt-4", client=client)
        with pytest.raises(AIError, match="GPT error"):
            engine.call("Hello")

    def test_call_auto_continue(self):
        client = MagicMock()

        # First call: finish_reason = "length"
        resp1 = MagicMock()
        choice1 = MagicMock()
        choice1.message.content = "partial"
        choice1.finish_reason = "length"
        resp1.choices = [choice1]

        # Second call: finish_reason = "stop"
        resp2 = MagicMock()
        choice2 = MagicMock()
        choice2.message.content = " complete"
        choice2.finish_reason = "stop"
        resp2.choices = [choice2]

        client.chat.completions.create.side_effect = [resp1, resp2]

        engine = OpenAIEngine(name="GPT", model_name="gpt-4", client=client)
        engine.filter_mode = True  # Suppress print output
        result = engine.call("Hello")
        assert result == "partial complete"

    def test_fallback_max_completion_tokens(self):
        client = MagicMock()

        # First create call raises, second succeeds
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]

        client.chat.completions.create.side_effect = [
            Exception("max_tokens not supported"),
            mock_response,
        ]

        engine = OpenAIEngine(name="GPT", model_name="gpt-4", client=client)
        result = engine.call("Test")
        assert result == "OK"


class TestGeminiEngine:
    def test_call_success(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini response"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].finish_reason = MagicMock()
        mock_response.candidates[0].finish_reason.name = "STOP"
        client.models.generate_content.return_value = mock_response

        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)
        result = engine.call("Hello")
        assert result == "Gemini response"
        assert len(engine.history) == 2

    def test_call_empty_response(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = None
        mock_response.candidates = []
        client.models.generate_content.return_value = mock_response

        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)
        result = engine.call("Hello")
        assert result == ""

    def test_get_client(self):
        client = MagicMock()
        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)
        assert engine.get_client() is client

    def test_hit_output_limit_max_tokens(self):
        client = MagicMock()
        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)

        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].finish_reason = MagicMock()
        response.candidates[0].finish_reason.name = "MAX_TOKENS"

        assert engine._hit_output_limit(response, "text") is True

    def test_hit_output_limit_odd_backticks(self):
        client = MagicMock()
        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)

        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].finish_reason = MagicMock()
        response.candidates[0].finish_reason.name = "STOP"

        assert engine._hit_output_limit(response, "```python\ncode") is True

    def test_hit_output_limit_trailing_chars(self):
        client = MagicMock()
        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)

        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].finish_reason = MagicMock()
        response.candidates[0].finish_reason.name = "STOP"

        assert engine._hit_output_limit(response, "some text,") is True
        assert engine._hit_output_limit(response, "some text:") is True
        assert engine._hit_output_limit(response, "some text(") is True
        assert engine._hit_output_limit(response, "some text[") is True
        assert engine._hit_output_limit(response, "some text{") is True
        assert engine._hit_output_limit(response, "some text ") is False

        assert engine._hit_output_limit(response, "some text,") is True

    def test_call_auto_continue(self):
        client = MagicMock()

        # First call: truncated via MAX_TOKENS
        resp1 = MagicMock()
        resp1.text = "partial"
        candidate1 = MagicMock()
        candidate1.finish_reason.name = "MAX_TOKENS"
        resp1.candidates = [candidate1]

        # Second call: complete
        resp2 = MagicMock()
        resp2.text = " complete"
        candidate2 = MagicMock()
        candidate2.finish_reason.name = "STOP"
        resp2.candidates = [candidate2]

        client.models.generate_content.side_effect = [resp1, resp2]

        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)
        engine.filter_mode = True  # Suppress print output
        result = engine.call("Hello")
        assert result == "partial complete"
        assert client.models.generate_content.call_count == 2

        assert engine._hit_output_limit(resp2, "item,") is True

    def test_hit_output_limit_normal_stop(self):
        client = MagicMock()
        engine = GeminiEngine(name="Gemini", model_name="gemini-pro", client=client)

        response = MagicMock()
        response.candidates = [MagicMock()]
        response.candidates[0].finish_reason = MagicMock()
        response.candidates[0].finish_reason.name = "STOP"

        assert engine._hit_output_limit(response, "Complete text.") is False


class TestClaudeEngine:
    def test_call_success(self):
        client = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "Claude response"

        # Need to make isinstance check work
        from anthropic.types import TextBlock

        mock_block.__class__ = TextBlock

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "end_turn"
        client.messages.create.return_value = mock_response

        engine = ClaudeEngine(name="Claude", model_name="claude-3", client=client)
        result = engine.call("Hello")
        assert result == "Claude response"
        assert len(engine.history) == 2

    def test_call_api_error(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("Claude API Error")

        engine = ClaudeEngine(name="Claude", model_name="claude-3", client=client)
        with pytest.raises(AIError, match="Claude error"):
            engine.call("Hello")

    def test_get_client(self):
        client = MagicMock()
        engine = ClaudeEngine(name="Claude", model_name="claude-3", client=client)
        assert engine.get_client() is client

    def test_call_with_system_prompt(self):
        client = MagicMock()

        from anthropic.types import TextBlock

        mock_block = MagicMock()
        mock_block.__class__ = TextBlock
        mock_block.text = "OK"

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "end_turn"
        client.messages.create.return_value = mock_response

        engine = ClaudeEngine(name="Claude", model_name="claude-3", client=client)
        engine.system_prompt = "Be helpful"
        engine.call("Test")

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "Be helpful"
