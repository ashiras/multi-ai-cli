import pytest
from anthropic.types import Message, TextBlock
from openai.types.chat import ChatCompletionMessageParam
from pytest_mock import MockerFixture

from multi_ai_cli.engines import (
    AIError,
    ClaudeEngine,
    GeminiEngine,
    OpenAIEngine,
    initialize_engines,
)


@pytest.fixture
def mock_config(mocker: MockerFixture):
    """Mock the config within the engines module"""
    mocked_config = mocker.patch("multi_ai_cli.engines.config")
    mocked_config.getint.side_effect = lambda section, option, fallback: {
        ("MODELS", "max_history_turns"): 30,
    }.get((section, option), fallback)
    mocked_config.get.return_value = "test-model-from-config"
    return mocked_config


@pytest.fixture
def mock_logger(mocker: MockerFixture):
    """Mock the logger within the engines module"""
    mocked_logger = mocker.patch("multi_ai_cli.engines.logger")
    return mocked_logger


@pytest.fixture
def mock_console_lock(mocker: MockerFixture):
    """Mock the _console_lock within the engines module (ignore PytestMockWarning intentionally)"""
    mocked_lock = mocker.patch("multi_ai_cli.engines._console_lock")
    mocked_lock.__enter__.return_value = None
    mocked_lock.__exit__.return_value = None
    return mocked_lock


@pytest.fixture
def mock_utils(mocker: MockerFixture):
    """Mock the utility functions within the engines module"""
    mocker.patch(
        "multi_ai_cli.engines._make_continue_prompt",
        return_value="The output was truncated due to an output limit.\nContinue EXACTLY from where you stopped.\nRules:\n- Do NOT repeat anything from previous turns unless explicitly asked.\n- Provide the output in full, but be concise.\n- Your response should start exactly with the next logical token.",
    )
    mocker.patch(
        "multi_ai_cli.engines._tail_of", side_effect=lambda text, length: text[-length:]
    )
    mocker.patch(
        "multi_ai_cli.engines._get_cfg_int",
        side_effect=lambda cfg, sec, opt, fallback: {
            ("MODELS", "gemini_max_output_tokens"): 8192,
            ("MODELS", "openai_max_tokens"): 4096,
            ("MODELS", "claude_max_tokens"): 8192,
            ("MODELS", "grok_max_tokens"): 4096,
            ("MODELS", "local_max_tokens"): 4096,
            ("MODELS", "auto_continue_max_rounds"): 5,
            ("MODELS", "auto_continue_tail_chars"): 1200,
        }.get((sec, opt), fallback),
    )
    return mocker.patch("multi_ai_cli.engines.get_api_key", return_value="mock_api_key")


@pytest.fixture
def gemini_engine(mock_config, mock_logger, mock_utils, mocker: MockerFixture):
    mock_client = mocker.MagicMock()
    engine = GeminiEngine("Gemini", "gemini-test", client=mock_client)
    return engine


@pytest.fixture
def openai_engine(mock_config, mock_logger, mock_utils, mocker: MockerFixture):
    mock_client = mocker.MagicMock()
    engine = OpenAIEngine("GPT", "gpt-test", mock_client)
    return engine


@pytest.fixture
def claude_engine(mock_config, mock_logger, mock_utils, mocker: MockerFixture):
    mock_client = mocker.MagicMock()
    engine = ClaudeEngine("Claude", "claude-test", mock_client)
    return engine


class TestGeminiEngine:
    def _make_gemini_response(
        self, mocker: MockerFixture, text="Gemini response", finish_reason_value=None
    ):
        """Create a mock response for the Gemini API"""
        mock_response = mocker.MagicMock()
        mock_response.text = text
        mock_candidate = mocker.MagicMock()
        mock_candidate.finish_reason = finish_reason_value
        mock_response.candidates = (
            [mock_candidate] if finish_reason_value is not None else []
        )
        return mock_response

    def test_call_returns_response(self, gemini_engine, mocker: MockerFixture):
        client = gemini_engine.get_client()
        mock_response = self._make_gemini_response(mocker, "Gemini response")
        client.models.generate_content.return_value = mock_response

        result = gemini_engine.call("Hello, Gemini!")

        assert result == "Gemini response"
        assert len(gemini_engine.history) == 2
        assert gemini_engine.history[0]["role"] == "user"
        assert gemini_engine.history[1]["role"] == "model"
        client.models.generate_content.assert_called_once()
        assert client.models.generate_content.call_args.kwargs["model"] == "gemini-test"
        assert any(
            p.text == "Hello, Gemini!"
            for c in client.models.generate_content.call_args.kwargs["contents"]
            for p in c.parts
        )

    def test_call_with_system_prompt(self, gemini_engine, mocker: MockerFixture):
        gemini_engine.system_prompt = "You are helpful."
        client = gemini_engine.get_client()
        mock_response = self._make_gemini_response(mocker, "OK")
        client.models.generate_content.return_value = mock_response

        result = gemini_engine.call("Hi")
        assert result == "OK"
        gen_config = client.models.generate_content.call_args.kwargs["config"]
        assert gen_config.system_instruction == "You are helpful."

    def test_call_api_error_raises(
        self, gemini_engine, mocker: MockerFixture, mock_logger
    ):
        client = gemini_engine.get_client()
        client.models.generate_content.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="API down"):
            gemini_engine.call("fail")
        mock_logger.error.assert_called_once()
        assert "Gemini API Error Detail: API down" in mock_logger.error.call_args[0][0]

    @pytest.mark.filterwarnings("ignore::pytest_mock.PytestMockWarning")
    def test_call_continues_on_max_tokens(
        self, gemini_engine, mocker: MockerFixture, mock_console_lock, mock_utils
    ):
        mocker.patch.object(gemini_engine, "max_output_tokens", 50)
        client = gemini_engine.get_client()
        gemini_engine.max_turns = 1  # Easy to trim history

        # 1st response: hits max tokens (simulated with finish_reason as string "MAX_TOKENS")
        mock_response_1 = self._make_gemini_response(
            mocker, "First part of the answer.", finish_reason_value="MAX_TOKENS"
        )
        # 2nd response: completes
        mock_response_2 = self._make_gemini_response(
            mocker, "Second part of the answer."
        )

        client.models.generate_content.side_effect = [mock_response_1, mock_response_2]

        result = gemini_engine.call("Long prompt")

        assert result == "First part of the answer.Second part of the answer."
        assert client.models.generate_content.call_count == 2
        assert (
            mock_console_lock.__enter__.call_count == 1
        )  # Lock is used during continuation
        assert (
            len(gemini_engine.history) == 2
        )  # Only the final user/model turns remain in history

        # Verify contents passed in the second API call
        second_call_contents = client.models.generate_content.call_args.kwargs[
            "contents"
        ]
        # Structure of `contents`: [initial user prompt, 1st response (model), continuation prompt (user)]
        assert len(second_call_contents) == 3
        assert any(
            p.text == "First part of the answer."
            for c in second_call_contents
            if c.role == "model"
            for p in c.parts
        )
        # Since _make_continue_prompt is mocked, check that the return value is included
        assert any(
            "The output was truncated due to an output limit." in p.text
            for c in second_call_contents
            if c.role == "user"
            for p in c.parts
        )

    def test_get_client(self, gemini_engine):
        client = gemini_engine.get_client()
        assert client is not None


class TestOpenAIEngine:
    def _make_openai_response(
        self, mocker: MockerFixture, content="OpenAI response", finish_reason="stop"
    ):
        """Create a mock response for the OpenAI API"""
        mock_choice = mocker.MagicMock()
        mock_choice.message.content = content
        mock_choice.finish_reason = finish_reason
        mock_response = mocker.MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response

    def test_call_returns_response(self, openai_engine, mocker: MockerFixture):
        client = openai_engine.get_client()
        client.chat.completions.create.return_value = self._make_openai_response(mocker)

        result = openai_engine.call("Hello, GPT!")

        assert result == "OpenAI response"
        assert len(openai_engine.history) == 2
        assert openai_engine.history[0]["role"] == "user"
        assert openai_engine.history[1]["role"] == "assistant"
        client.chat.completions.create.assert_called_once()
        assert client.chat.completions.create.call_args.kwargs["model"] == "gpt-test"
        assert any(
            m["content"] == "Hello, GPT!"
            for m in client.chat.completions.create.call_args.kwargs["messages"]
            if m["role"] == "user"
        )

    def test_call_with_system_prompt(self, openai_engine, mocker: MockerFixture):
        openai_engine.system_prompt = "Be helpful."
        client = openai_engine.get_client()
        client.chat.completions.create.return_value = self._make_openai_response(
            mocker, "OK"
        )

        result = openai_engine.call("Hi")
        assert result == "OK"
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be helpful."

    def test_call_api_error_raises_ai_error(
        self, openai_engine, mocker: MockerFixture, mock_logger
    ):
        client = openai_engine.get_client()
        client.chat.completions.create.side_effect = RuntimeError("API error")

        with pytest.raises(AIError, match="GPT error"):
            openai_engine.call("fail")
        mock_logger.error.assert_called_once()
        assert "GPT API Error: API error" in mock_logger.error.call_args[0][0]

    def test_call_fallback_to_max_completion_tokens(
        self, openai_engine, mocker: MockerFixture
    ):
        """Fallback to max_completion_tokens if max_tokens fails"""
        client = openai_engine.get_client()
        client.chat.completions.create.side_effect = [
            Exception("max_tokens not supported"),  # 1st call fails
            self._make_openai_response(
                mocker, "fallback ok"
            ),  # 2nd call succeeds with max_completion_tokens
        ]

        result = openai_engine.call("test fallback")
        assert result == "fallback ok"
        assert client.chat.completions.create.call_count == 2
        # Verify that max_tokens is not in the arguments for the second call
        second_call_kwargs = client.chat.completions.create.call_args_list[1].kwargs
        assert "max_completion_tokens" in second_call_kwargs
        assert (
            "max_tokens" not in second_call_kwargs
        )  # Confirm that max_tokens is not present when falling back

    @pytest.mark.filterwarnings("ignore::pytest_mock.PytestMockWarning")
    def test_call_continues_on_length_reason(
        self, openai_engine, mocker: MockerFixture, mock_console_lock, mock_utils
    ):
        # Patch instance variable to simulate max_tokens
        mocker.patch.object(openai_engine, "max_tokens", 50)
        client = openai_engine.get_client()
        openai_engine.max_turns = 1  # Easy to trim history

        # 1st response: hits length limit (simulated with finish_reason="length")
        mock_response_1 = self._make_openai_response(
            mocker, "First part.", finish_reason="length"
        )
        # 2nd response: completes
        mock_response_2 = self._make_openai_response(mocker, "Second part.")

        client.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

        result = openai_engine.call("Long prompt that needs continuation")

        assert result == "First part.Second part."
        assert client.chat.completions.create.call_count == 2
        assert (
            mock_console_lock.__enter__.call_count == 1
        )  # Lock is used during continuation
        assert (
            len(openai_engine.history) == 2
        )  # Only the final user/model turns remain in history

        # Verify that messages passed in the second API call are correct
        second_call_messages: list[ChatCompletionMessageParam] = (
            client.chat.completions.create.call_args.kwargs["messages"]
        )
        # Structure: [initial user prompt, 1st response (assistant), continuation prompt (user)]
        assert len(second_call_messages) == 3
        assert second_call_messages[1]["role"] == "assistant"
        assert second_call_messages[1]["content"] == "First part."
        assert second_call_messages[2]["role"] == "user"
        # Verify that the continuation prompt contains the mocked return value message
        assert (
            "The output was truncated due to an output limit."
            in second_call_messages[2]["content"]
        )

    def test_get_client(self, openai_engine):
        client = openai_engine.get_client()
        assert client is not None


class TestClaudeEngine:
    def _make_claude_response(
        self, mocker: MockerFixture, text="Claude response", stop_reason="end_turn"
    ):
        """Create a mock response for the Claude API"""
        # Use the actual TextBlock class to pass the isinstance check
        mock_block = TextBlock(text=text, type="text")
        mock_response = mocker.MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = stop_reason
        return mock_response

    def test_call_returns_response(self, claude_engine, mocker: MockerFixture):
        client = claude_engine.get_client()
        mock_resp = self._make_claude_response(mocker)
        client.messages.create.return_value = mock_resp

        result = claude_engine.call("Hello, Claude!")

        assert result == "Claude response"
        assert len(claude_engine.history) == 2
        assert claude_engine.history[0]["role"] == "user"
        assert claude_engine.history[1]["role"] == "assistant"
        client.messages.create.assert_called_once()
        assert client.messages.create.call_args.kwargs["model"] == "claude-test"
        assert any(
            m["content"] == "Hello, Claude!"
            for m in client.messages.create.call_args.kwargs["messages"]
            if m["role"] == "user"
        )

    def test_call_with_system_prompt(self, claude_engine, mocker: MockerFixture):
        claude_engine.system_prompt = "Be concise."
        client = claude_engine.get_client()
        mock_resp = self._make_claude_response(mocker, "Short answer")
        client.messages.create.return_value = mock_resp

        result = claude_engine.call("Hi")

        assert result == "Short answer"
        assert client.messages.create.call_args.kwargs["system"] == "Be concise."

    def test_call_api_error_raises_ai_error(
        self, claude_engine, mocker: MockerFixture, mock_logger
    ):
        client = claude_engine.get_client()
        client.messages.create.side_effect = RuntimeError("Claude API down")

        with pytest.raises(AIError, match="Claude error"):
            claude_engine.call("fail")
        mock_logger.error.assert_called_once()
        assert "Claude API Error: Claude API down" in mock_logger.error.call_args[0][0]

    @pytest.mark.filterwarnings("ignore::pytest_mock.PytestMockWarning")
    def test_call_continues_on_max_tokens(
        self, claude_engine, mocker: MockerFixture, mock_console_lock, mock_utils
    ):
        # Patch instance variable to simulate max_tokens
        mocker.patch.object(claude_engine, "max_tokens", 50)
        client = claude_engine.get_client()
        claude_engine.max_turns = 1  # Easy to trim history

        # 1st response: hits max tokens (simulated with stop_reason="max_tokens")
        mock_response_1 = self._make_claude_response(
            mocker, "First part.", stop_reason="max_tokens"
        )
        # 2nd response: completes
        mock_response_2 = self._make_claude_response(mocker, "Second part.")

        client.messages.create.side_effect = [mock_response_1, mock_response_2]

        result = claude_engine.call("Long prompt for Claude")

        assert result == "First part.Second part."
        assert client.messages.create.call_count == 2
        assert (
            mock_console_lock.__enter__.call_count == 1
        )  # Lock is used during continuation
        assert (
            len(claude_engine.history) == 2
        )  # Only the final user/model turns remain in history

        # Verify messages passed in the second API call
        second_call_messages: list[Message] = client.messages.create.call_args.kwargs[
            "messages"
        ]
        # Structure: [initial user prompt, 1st response (assistant), continuation prompt (user)]
        assert len(second_call_messages) == 3
        assert second_call_messages[1]["role"] == "assistant"
        assert second_call_messages[1]["content"] == "First part."
        assert second_call_messages[2]["role"] == "user"
        # Verify that the continuation prompt contains the mocked return value message
        assert (
            "The output was truncated due to an output limit."
            in second_call_messages[2]["content"]
        )

    def test_get_client(self, claude_engine):
        client = claude_engine.get_client()
        assert client is not None


class TestAIEngineCommon:
    def test_scrub_clears_history(self, openai_engine, mock_logger):
        openai_engine.history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        openai_engine.scrub()
        assert openai_engine.history == []
        mock_logger.info.assert_called_once_with("[*] System: GPT history cleared.")

    def test_scrub_keeps_persona(self, openai_engine):
        openai_engine.system_prompt = "I am a persona"
        openai_engine.history = [{"role": "user", "content": "hi"}]
        openai_engine.scrub()
        assert openai_engine.system_prompt == "I am a persona"
        assert openai_engine.history == []

    def test_load_persona(self, gemini_engine, mock_logger):
        gemini_engine.history = [{"role": "user", "content": "old"}]
        gemini_engine.load_persona("New persona text", "persona.txt")

        assert gemini_engine.system_prompt == "New persona text"
        assert gemini_engine.history == []
        assert gemini_engine.history == []

    def test_trim_history(self, openai_engine):
        openai_engine.max_turns = 2
        # Generate history in an alternating user/assistant message format
        openai_engine.history = [
            {"role": "user", "content": "user_msg0"},
            {"role": "assistant", "content": "assist_msg0"},
            {"role": "user", "content": "user_msg1"},
            {"role": "assistant", "content": "assist_msg1"},
            {"role": "user", "content": "user_msg2"},
            {"role": "assistant", "content": "assist_msg2"},
        ]
        assert len(openai_engine.history) == 6  # 6 messages
        openai_engine._trim_history()
        assert len(openai_engine.history) == 4  # max_turns * 2 = 4 messages
        # Ensure the latest 4 messages are retained: user_msg1, assist_msg1, user_msg2, assist_msg2
        assert openai_engine.history[0]["content"] == "user_msg1"
        assert openai_engine.history[1]["content"] == "assist_msg1"
        assert openai_engine.history[2]["content"] == "user_msg2"
        assert openai_engine.history[3]["content"] == "assist_msg2"


class TestInitializeEngines:
    @pytest.fixture(autouse=True)
    def _setup_patches_for_initialize(self, mocker: MockerFixture):
        mocker.patch("multi_ai_cli.engines.get_api_key", return_value="mock_key")
        mock_os_makedirs = mocker.patch("multi_ai_cli.engines.os.makedirs")
        # Since engines is a global dictionary and initialize_engines calls engines.clear(), we don't need new_callable=dict
        # However, for safety to ensure other tests don't modify engines, we mock with a new dictionary each time
        mock_engines_dict = mocker.patch(
            "multi_ai_cli.engines.engines", new_callable=dict
        )
        mock_config = mocker.patch("multi_ai_cli.engines.config")
        mock_config.get.side_effect = lambda section, option, fallback: {
            ("MODELS", "gemini_model"): "gemini-flash",
            ("MODELS", "gpt_model"): "gpt-4",
            ("MODELS", "claude_model"): "claude-sonnet",
            ("MODELS", "grok_model"): "grok-latest",
            ("LOCAL", "model"): "llama2",
            ("LOCAL", "base_url"): "http://localhost:11434/v1",
            ("Paths", "work_efficient"): "mock_efficient_path",
            ("Paths", "work_data"): "mock_data_path",
        }.get((section, option), fallback)
        mock_config.getint.return_value = 30  # default for max_history_turns

        # Mock the client classes themselves
        mocker.patch("google.genai.Client")
        mocker.patch("openai.OpenAI")
        mocker.patch("anthropic.Anthropic")

        # Mock builtins.print to make SystemExit outputs testable
        mock_builtins_print = mocker.patch("builtins.print")

        return mock_engines_dict, mock_config, mock_os_makedirs, mock_builtins_print

    def test_initialize_success(
        self, _setup_patches_for_initialize, mocker: MockerFixture
    ):
        mock_engines, mock_config, mock_os_makedirs, _ = _setup_patches_for_initialize
        initialize_engines()

        assert "gemini" in mock_engines
        assert isinstance(mock_engines["gemini"], GeminiEngine)
        assert mock_engines["gemini"].model_name == "gemini-flash"

        assert "gpt" in mock_engines
        assert isinstance(mock_engines["gpt"], OpenAIEngine)
        assert mock_engines["gpt"].model_name == "gpt-4"

        assert "claude" in mock_engines
        assert isinstance(mock_engines["claude"], ClaudeEngine)
        assert mock_engines["claude"].model_name == "claude-sonnet"

        assert "grok" in mock_engines
        assert isinstance(mock_engines["grok"], OpenAIEngine)
        assert mock_engines["grok"].model_name == "grok-latest"

        assert "local" in mock_engines
        assert isinstance(mock_engines["local"], OpenAIEngine)
        assert mock_engines["local"].model_name == "llama2"

        # Check makedirs calls
        mock_os_makedirs.assert_any_call("mock_efficient_path", exist_ok=True)
        mock_os_makedirs.assert_any_call("mock_data_path", exist_ok=True)

    def test_initialize_error_exits(
        self, _setup_patches_for_initialize, mocker: MockerFixture, mock_logger
    ):
        mock_engines, mock_config, _, mock_builtins_print = (
            _setup_patches_for_initialize
        )
        mocker.patch(
            "multi_ai_cli.engines.get_api_key", side_effect=Exception("No key found")
        )

        with pytest.raises(SystemExit) as exc_info:
            initialize_engines()
        assert exc_info.value.code == 1
        mock_builtins_print.assert_any_call("[!] Startup Error: No key found")
        mock_logger.error.assert_called_once_with(
            "Engine initialization failed: No key found"
        )
