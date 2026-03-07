# src/multi_ai_cli/engines.py
"""
AI engine implementations for Multi-AI CLI.
Contains base abstract class and concrete engines for Gemini, GPT, Claude, Grok, and local models.
"""

import os
import sys
from abc import ABC, abstractmethod

from .config import DEFAULT_MAX_HISTORY_TURNS, config, get_api_key, logger, engines
from .utils import _console_lock, _get_cfg_int, _make_continue_prompt, _tail_of


class AIError(Exception):
    """Custom exception for AI-related errors."""

    pass


class AIEngine(ABC):
    """Base abstract class for all AI model implementations."""

    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name
        self.system_prompt = ""
        self.history = []
        self.max_turns = config.getint(
            "MODELS", "max_history_turns", fallback=DEFAULT_MAX_HISTORY_TURNS
        )

    def _trim_history(self):
        """Keep conversation history within the allowed turn limit."""
        max_msgs = self.max_turns * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    @abstractmethod
    def call(self, prompt: str) -> str:
        """Send prompt to the AI and return the response text."""
        pass

    def scrub(self):
        """Clear short-term memory (history) while keeping persona."""
        self.history = []
        logger.info(f"[*] System: {self.name} history cleared.")

    def load_persona(self, prompt_text: str, filename: str):
        """Set new system prompt (persona) and reset history."""
        self.system_prompt = prompt_text
        self.history = []
        self._after_persona_loaded()
        logger.info(f"[*] System: {self.name} persona loaded from '{filename}'.")

    def _after_persona_loaded(self):
        """Hook called after loading persona."""
        pass


class GeminiEngine(AIEngine):
    """Implementation for Google Gemini models using the new google-genai SDK."""

    def __init__(self, name: str, model_name: str, client):
        super().__init__(name, model_name)
        self.client = client  # genai.Client
        self.max_output_tokens = _get_cfg_int(
            config, "MODELS", "gemini_max_output_tokens", fallback=8192
        )
        self.model_name = model_name

    def _after_persona_loaded(self):
        """Hook: called after loading persona. No need for rebuild in new SDK."""
        pass

    def _to_gemini_part(self, content: str):
        """Convert plain text to a Gemini 'parts' entry."""
        return [{"text": content}]

    def _hit_output_limit(self, response, answer_chunk: str) -> bool:
        """Detect whether the response was truncated by output limits."""
        finish_reason = None
        try:
            # 新しいSDKの構造に合わせて取得を試みる
            if hasattr(response, "candidates") and response.candidates:
                finish_reason = response.candidates[0].finish_reason
        except Exception:
            pass

        # MAX_TOKENS（または整数値の 2）なら文字数制限に引っかかったと判定
        finish_name = getattr(finish_reason, "name", str(finish_reason))
        if finish_name == "MAX_TOKENS" or finish_reason == 2 or finish_reason == "2":
            return True

        # フォールバック: バッククォートの数が奇数だったり、途切れそうな文字で終わっている場合
        if answer_chunk.count("```") % 2 == 1:
            return True
        if answer_chunk.rstrip().endswith((",", ":", "(", "[", "{")):
            return True

        return False

    def call(self, prompt: str) -> str:
        self._trim_history()

        contents = []
        if self.system_prompt:
            contents.append({"role": "model", "parts": [{"text": self.system_prompt}]})

        for msg in self.history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                {"role": role, "parts": self._to_gemini_part(msg["content"])}
            )

        contents.append({"role": "user", "parts": self._to_gemini_part(prompt)})

        full_answer = ""
        max_rounds = _get_cfg_int(
            config, "MODELS", "auto_continue_max_rounds", fallback=5
        )
        tail_chars = _get_cfg_int(
            config, "MODELS", "auto_continue_tail_chars", fallback=1200
        )

        gen_config = {"max_output_tokens": self.max_output_tokens}

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=gen_config,
                )
                answer_chunk = response.text or ""
                full_answer += answer_chunk

                if self._hit_output_limit(response, answer_chunk):
                    with _console_lock:
                        print(
                            f"[*] Gemini is continuing (round {round_idx}/{max_rounds})...",
                            end="\r",
                            flush=True,
                        )

                    contents.append(
                        {"role": "model", "parts": self._to_gemini_part(answer_chunk)}
                    )

                    eff_tail_chars = max(
                        300, int(tail_chars * (0.8 ** (round_idx - 1)))
                    )
                    tail = _tail_of(full_answer, eff_tail_chars)
                    continue_prompt = _make_continue_prompt(tail)
                    contents.append(
                        {"role": "user", "parts": self._to_gemini_part(continue_prompt)}
                    )
                    continue

                break

            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                raise

        else:
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


class OpenAIEngine(AIEngine):
    """Implementation for OpenAI-compatible APIs (GPT, Grok, Local)."""

    def __init__(
        self,
        name: str,
        model_name: str,
        client,
        max_tokens_key: str = "openai_max_tokens",
    ):
        super().__init__(name, model_name)
        self.client = client
        self.max_tokens = _get_cfg_int(config, "MODELS", max_tokens_key, fallback=4096)

    def _create_completion(self, messages):
        """Call chat completions with max_tokens fallback."""
        try:
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
            )
        except TypeError:
            # Fallback for APIs that use max_completion_tokens
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=self.max_tokens,
            )

    def call(self, prompt: str) -> str:
        self._trim_history()

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        full_answer = ""
        max_rounds = _get_cfg_int(
            config, "MODELS", "auto_continue_max_rounds", fallback=5
        )
        tail_chars = _get_cfg_int(
            config, "MODELS", "auto_continue_tail_chars", fallback=1200
        )

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self._create_completion(messages)
                choice = response.choices[0]
                answer_chunk = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", None)

                full_answer += answer_chunk

                if finish_reason == "length":
                    with _console_lock:
                        print(
                            f"[*] {self.name} is continuing (hit length limit, round {round_idx}/{max_rounds})...",
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
                logger.error(f"{self.name} API Error: {e}")
                raise AIError(f"{self.name} error: {e}")

        else:
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


class ClaudeEngine(AIEngine):
    """Implementation for Anthropic Claude models."""

    def __init__(self, name: str, model_name: str, client):
        super().__init__(name, model_name)
        self.client = client
        self.max_tokens = _get_cfg_int(
            config, "MODELS", "claude_max_tokens", fallback=8192
        )

    def call(self, prompt: str) -> str:
        self._trim_history()

        messages = list(self.history) + [{"role": "user", "content": prompt}]
        full_answer = ""

        max_rounds = _get_cfg_int(
            config, "MODELS", "auto_continue_max_rounds", fallback=5
        )
        tail_chars = _get_cfg_int(
            config, "MODELS", "auto_continue_tail_chars", fallback=1200
        )

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt if self.system_prompt else "",
                    messages=messages,
                )

                answer_chunk = ""
                if response.content:
                    answer_chunk = response.content[0].text or ""

                stop_reason = getattr(response, "stop_reason", None)

                full_answer += answer_chunk

                if stop_reason == "max_tokens":
                    with _console_lock:
                        print(
                            f"[*] Claude is continuing (hit max_tokens, round {round_idx}/{max_rounds})...",
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

        else:
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


def initialize_engines():
    """Initialize all AI clients and engine instances using modern SDKs."""

    try:
        # Gemini (new google-genai SDK)
        from google import genai

        gemini_api_key = get_api_key("gemini_api_key", "GEMINI_API_KEY")
        genai_client = genai.Client(api_key=gemini_api_key)

        # OpenAI-compatible clients
        from openai import OpenAI

        client_gpt = OpenAI(api_key=get_api_key("openai_api_key", "OPENAI_API_KEY"))
        client_grok = OpenAI(
            api_key=get_api_key("grok_api_key", "GROK_API_KEY"),
            base_url="https://api.x.ai/v1",
        )
        local_base = config.get(
            "LOCAL", "base_url", fallback="http://localhost:11434/v1"
        )
        client_local = OpenAI(api_key="ollama", base_url=local_base)

        # Anthropic
        from anthropic import Anthropic

        client_claude = Anthropic(
            api_key=get_api_key("anthropic_api_key", "ANTHROPIC_API_KEY")
        )

        # Instantiate engines
        engines.clear()
        engines.update({
            "gemini": GeminiEngine(
                "Gemini",
                config.get("MODELS", "gemini_model", fallback="gemini-2.5-flash"),
                client=genai_client,
            ),
            "gpt": OpenAIEngine(
                "GPT",
                config.get("MODELS", "gpt_model", fallback="gpt-4o-mini"),
                client_gpt,
                max_tokens_key="openai_max_tokens",
            ),
            "claude": ClaudeEngine(
                "Claude",
                config.get(
                    "MODELS", "claude_model", fallback="claude-3-5-sonnet-20241022"
                ),
                client_claude,
            ),
            "grok": OpenAIEngine(
                "Grok",
                config.get("MODELS", "grok_model", fallback="grok-4-latest"),
                client_grok,
                max_tokens_key="grok_max_tokens",
            ),
            "local": OpenAIEngine(
                "Local",
                config.get("LOCAL", "model", fallback="qwen2.5-coder:14b"),
                client_local,
                max_tokens_key="local_max_tokens",
            ),
        })

        # Ensure required directories exist
        for d_opt in ["work_efficient", "work_data"]:
            d_default = "prompts" if "efficient" in d_opt else "work_data"
            os.makedirs(config.get("Paths", d_opt, fallback=d_default), exist_ok=True)

    except Exception as e:
        print(f"[!] Startup Error: {e}")
        logger.error(f"Engine initialization failed: {e}")
        sys.exit(1)
