"""
AI engine implementations for Multi-AI CLI.

Contains base abstract class and concrete engines for Gemini, GPT,
Claude, Grok, and local models.
"""

from abc import ABC, abstractmethod
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import MessageParam, TextBlock
from google import genai
from google.genai import types
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .config import DEFAULT_MAX_HISTORY_TURNS, logger
from .registry import runtime_settings
from .utils import _console_lock, _make_continue_prompt, _tail_of


class AIError(Exception):
    """Custom exception for AI-related errors."""

    pass


class AIEngine(ABC):
    """Base abstract class for all AI model implementations."""

    def __init__(self, name: str, model_name: str) -> None:
        """
        Initializes an AI engine.

        Args:
            name (str): The name of the AI engine.
            model_name (str): The name of the specific model being used.
        """
        self.name = name
        self.model_name = model_name
        self.system_prompt = ""
        self.history: list[dict[str, str]] = []
        # max_turns is overwritten in _build_agent_engines() in config.py
        self.max_turns = DEFAULT_MAX_HISTORY_TURNS
        # Temporary execution-scoped flag to suppress interactive
        # progress/status output to stdout (e.g. auto-continue messages).
        # Set to True only during filter mode execution.
        # This may later be replaced by per-call execution options.
        self.filter_mode = False

    def _trim_history(self) -> None:
        """Keeps conversation history within the allowed turn limit."""
        max_msgs = self.max_turns * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    @abstractmethod
    def call(self, prompt: str) -> str:
        """Sends prompt to the AI and returns the response text."""
        pass

    def scrub(self) -> None:
        """Clears short-term memory (history) while keeping persona."""
        self.history = []
        logger.info(f"[*] System: {self.name} history cleared.")

    def load_persona(self, prompt_text: str, filename: str) -> None:
        """
        Sets new system prompt (persona) and resets history.

        Args:
            prompt_text (str): The new system prompt to load.
            filename (str): The filename from which the persona is loaded.
        """
        self.system_prompt = prompt_text
        self.history = []
        self._after_persona_loaded()
        logger.info(f"[*] System: {self.name} persona loaded from '{filename}'.")

    def _after_persona_loaded(self) -> None:
        """Hook called after loading persona. Override in subclasses if needed."""
        pass

    @abstractmethod
    def get_client(self) -> Any:
        """
        Gets the underlying AI client instance.

        Returns:
            Any: The API client instance for the specific engine.
        """
        pass


class GeminiEngine(AIEngine):
    """Implementation for Google Gemini models using the new google-genai SDK."""

    def __init__(
        self,
        name: str,
        model_name: str,
        client: genai.Client,
    ) -> None:
        """
        Initializes a Gemini engine.

        Args:
            name (str): The name of the AI engine.
            model_name (str): The name of the specific Gemini model being used.
            client (genai.Client): The Google GenAI client instance to use
                for communications.
        """
        super().__init__(name, model_name)
        self.client = client
        # max_output_tokens is externally configured from _build_agent_engines()
        self.max_output_tokens = 8192

    def get_client(self) -> genai.Client:
        """
        Gets the Google GenAI client instance.

        Returns:
            genai.Client: The Google GenAI client instance.
        """
        return self.client

    def _after_persona_loaded(self) -> None:
        """Hook: called after loading persona. No need for rebuild in new SDK."""
        pass

    def _hit_output_limit(self, response: Any, answer_chunk: str) -> bool:
        """
        Detects whether the response was truncated by output limits.

        Args:
            response: The response object from the Gemini API call.
            answer_chunk (str): The latest chunk of the answer generated.

        Returns:
            bool: True if output limit was hit, otherwise False.
        """
        finish_reason = None
        try:
            if hasattr(response, "candidates") and response.candidates:
                finish_reason = response.candidates[0].finish_reason
        except Exception:
            pass

        finish_name = getattr(finish_reason, "name", str(finish_reason))

        if finish_name == "MAX_TOKENS" or finish_reason == 2 or finish_reason == "2":
            return True

        if answer_chunk.count("```") % 2 == 1:
            return True
        if answer_chunk.rstrip().endswith((",", ":", "(", "[", "{")):
            return True

        return False

    def call(self, prompt: str) -> str:
        """
        Calls the Gemini model with a user prompt, managing conversation
        history and implementing auto-continuation for long responses.

        Auto-continue progress output is suppressed when filter_mode is True.

        Args:
            prompt (str): The user input to send to the Gemini model.

        Returns:
            str: The complete AI-generated response text.

        Raises:
            Exception: If there is an error during the Gemini API call.
        """
        self._trim_history()

        contents = []
        for msg in self.history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role, parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        )

        gen_config = types.GenerateContentConfig(
            max_output_tokens=self.max_output_tokens,
            system_instruction=self.system_prompt if self.system_prompt else None,
        )

        full_answer = ""
        max_rounds = runtime_settings.auto_continue_max_rounds
        tail_chars = runtime_settings.auto_continue_tail_chars

        client = self.get_client()

        for round_idx in range(1, max_rounds + 1):
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=gen_config,
                )

                answer_chunk = response.text if response.text else ""
                full_answer += answer_chunk

                if self._hit_output_limit(response, answer_chunk):
                    # Suppress progress output when filter_mode is active
                    if not self.filter_mode:
                        with _console_lock:
                            print(
                                f"[*] {self.name} continuing ({round_idx}/{max_rounds})...",
                                end="\r",
                                flush=True,
                            )

                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=answer_chunk)],
                        )
                    )
                    tail = _tail_of(
                        full_answer,
                        max(300, int(tail_chars * (0.8 ** (round_idx - 1)))),
                    )
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(text=_make_continue_prompt(tail))
                            ],
                        )
                    )
                    continue

                break
            except Exception as e:
                logger.error(f"Gemini API Error Detail: {e}")
                raise

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "model", "content": full_answer})
        self._trim_history()

        return full_answer


class OpenAIEngine(AIEngine):
    """Implementation for OpenAI-compatible APIs (GPT, Grok, Local)."""

    def __init__(
        self,
        name: str,
        model_name: str,
        client: OpenAI,
    ) -> None:
        """
        Initializes an OpenAI-compatible engine.

        Args:
            name (str): The name of the AI engine.
            model_name (str): The name of the specific OpenAI model being used.
            client (OpenAI): The OpenAI client instance to use for API calls.
        """
        super().__init__(name, model_name)
        self.client = client
        # max_tokens is externally configured from _build_agent_engines()
        self.max_tokens = 4096

    def get_client(self) -> OpenAI:
        """
        Gets the OpenAI client instance.

        Returns:
            OpenAI: The OpenAI client instance.
        """
        return self.client

    def _create_completion(self, messages: list[ChatCompletionMessageParam]) -> Any:
        """
        Calls chat completions with ``max_tokens`` fallback.

        Attempts to create a completion using ``max_tokens`` first. If that
        fails, falls back to using ``max_completion_tokens``.

        Args:
            messages (list[ChatCompletionMessageParam]): The messages to send
                to the chat API.

        Returns:
            Any: The response object from the API call.
        """
        client = self.get_client()
        try:
            return client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
            )
        except Exception:
            return client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=self.max_tokens,
            )

    def call(self, prompt: str) -> str:
        """
        Calls the OpenAI engine with a user prompt, managing conversation
        history and implementing auto-continuation for long responses.

        Auto-continue progress output is suppressed when filter_mode is True.

        Args:
            prompt (str): The user input to send to the OpenAI model.

        Returns:
            str: The complete AI-generated response text.

        Raises:
            AIError: If there is an error during the OpenAI API call.
        """
        self._trim_history()

        messages: list[ChatCompletionMessageParam] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        for msg in self.history:
            messages.append(cast(ChatCompletionMessageParam, msg))

        messages.append({"role": "user", "content": prompt})

        full_answer = ""
        max_rounds = runtime_settings.auto_continue_max_rounds
        tail_chars = runtime_settings.auto_continue_tail_chars

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self._create_completion(messages)
                choice = response.choices[0]
                answer_chunk = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", None)

                full_answer += answer_chunk

                if finish_reason == "length":
                    # Suppress progress output when filter_mode is active
                    if not self.filter_mode:
                        with _console_lock:
                            print(
                                f"[*] {self.name} is continuing ({round_idx}/{max_rounds})...",
                                end="\r",
                                flush=True,
                            )

                    messages.append({"role": "assistant", "content": answer_chunk})
                    tail = _tail_of(full_answer, tail_chars)
                    messages.append(
                        {"role": "user", "content": _make_continue_prompt(tail)}
                    )
                    continue

                break
            except Exception as e:
                logger.error(f"{self.name} API Error: {e}")
                raise AIError(f"{self.name} error: {e}")

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()
        return full_answer


class ClaudeEngine(AIEngine):
    """Implementation for Anthropic Claude models."""

    def __init__(self, name: str, model_name: str, client: Anthropic) -> None:
        """
        Initializes a Claude engine.

        Args:
            name (str): The name of the AI engine.
            model_name (str): The name of the specific Claude model being used.
            client (Anthropic): The Anthropic client instance to use for
                communications.
        """
        super().__init__(name, model_name)
        self.client = client
        # max_tokens is externally configured from _build_agent_engines()
        self.max_tokens = 8192

    def get_client(self) -> Anthropic:
        """
        Gets the Anthropic client instance.

        Returns:
            Anthropic: The Anthropic client instance.
        """
        return self.client

    def call(self, prompt: str) -> str:
        """
        Calls the Claude model with a user prompt, managing conversation
        history and implementing auto-continuation for long responses.

        Auto-continue progress output is suppressed when filter_mode is True.

        Args:
            prompt (str): The user input to send to the Claude model.

        Returns:
            str: The complete AI-generated response text.

        Raises:
            AIError: If there is an error during the Claude API call.
        """
        self._trim_history()

        messages: list[MessageParam] = []
        for msg in self.history:
            messages.append(cast(MessageParam, msg))
        messages.append({"role": "user", "content": prompt})

        full_answer = ""
        max_rounds = runtime_settings.auto_continue_max_rounds
        tail_chars = runtime_settings.auto_continue_tail_chars

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt if self.system_prompt else "",
                    messages=messages,
                )

                answer_chunk = "".join(
                    block.text
                    for block in response.content
                    if isinstance(block, TextBlock)
                )

                stop_reason = getattr(response, "stop_reason", None)
                full_answer += answer_chunk

                if stop_reason == "max_tokens":
                    # Suppress progress output when filter_mode is active
                    if not self.filter_mode:
                        with _console_lock:
                            print(
                                f"[*] {self.name} is continuing ({round_idx}/{max_rounds})...",
                                end="\r",
                                flush=True,
                            )

                    messages.append({"role": "assistant", "content": answer_chunk})
                    tail = _tail_of(full_answer, tail_chars)
                    continue_prompt = _make_continue_prompt(tail)
                    messages.append({"role": "user", "content": continue_prompt})
                    continue

                break
            except Exception as e:
                logger.error(f"Claude API Error: {e}")
                raise AIError(f"Claude error: {e}")

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()
        return full_answer
