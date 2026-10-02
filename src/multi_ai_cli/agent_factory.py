"""
Agent factory for Multi-AI CLI.

Creates fresh AIEngine instances from AgentDefinition objects.
SDK clients are cached and shared across instances for efficiency,
while each AIEngine instance maintains its own independent mutable state
(history, system_prompt, filter_mode, etc.).
"""

from typing import Any

from .registry import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    AgentDefinition,
    runtime_settings,
)


class AgentFactory:
    """
    Factory that creates new AIEngine instances from AgentDefinition.

    Each call to create() returns a fresh AIEngine with independent
    mutable state. SDK clients are cached internally keyed by
    (adapter, server, api_key) to avoid redundant connections.
    """

    def __init__(self) -> None:
        self._client_cache: dict[str, Any] = {}

    def create(self, agent_def: AgentDefinition) -> Any:
        """
        Create a new AIEngine instance from an AgentDefinition.

        Each invocation returns a completely independent engine instance
        with its own history, system_prompt, and runtime flags.

        Args:
            agent_def: The agent definition to instantiate.

        Returns:
            A new AIEngine instance.

        Raises:
            ValueError: If the adapter type is unsupported.
        """
        from .engines import OpenAIEngine

        if agent_def.adapter == "openai-compatible":
            client = self._get_or_create_openai_client(agent_def)
            ai_engine = OpenAIEngine(
                name=agent_def.display_label,
                model_name=agent_def.engine,
                client=client,
            )
        else:
            raise ValueError(
                f"Agent '{agent_def.agent_key}': "
                f"unsupported adapter '{agent_def.adapter}'."
            )

        # Apply max_output_tokens
        effective_max_tokens = (
            agent_def.max_output_tokens
            if agent_def.max_output_tokens is not None
            else DEFAULT_MAX_OUTPUT_TOKENS
        )
        if hasattr(ai_engine, "max_output_tokens"):
            ai_engine.max_output_tokens = effective_max_tokens
        if hasattr(ai_engine, "max_tokens"):
            ai_engine.max_tokens = effective_max_tokens

        # Apply runtime settings
        ai_engine.max_turns = runtime_settings.max_history_turns

        return ai_engine

    def create_legacy(self, agent_def: AgentDefinition, sdk_type: str) -> Any:
        """
        Create a new AIEngine instance for legacy config format.

        Legacy agents may use Gemini, Anthropic, or OpenAI SDKs based
        on their agent_key, since the legacy format implies specific providers.

        Args:
            agent_def: The agent definition to instantiate.
            sdk_type: SDK type string ("gemini", "anthropic", or "openai").

        Returns:
            A new AIEngine instance.

        Raises:
            ValueError: If the sdk_type is unsupported.
        """
        from .engines import ClaudeEngine, GeminiEngine, OpenAIEngine

        resolved_key = self._resolve_api_key(agent_def)
        api_key = resolved_key or "dummy"
        cache_key = f"{sdk_type}:{agent_def.server}:{api_key}"

        ai_engine: Any

        if sdk_type == "gemini":
            if cache_key not in self._client_cache:
                from google import genai

                self._client_cache[cache_key] = genai.Client(api_key=api_key)
            client = self._client_cache[cache_key]
            ai_engine = GeminiEngine(
                name=agent_def.display_label,
                model_name=agent_def.engine,
                client=client,
            )
        elif sdk_type == "anthropic":
            if cache_key not in self._client_cache:
                from anthropic import Anthropic

                self._client_cache[cache_key] = Anthropic(api_key=api_key)
            client = self._client_cache[cache_key]
            ai_engine = ClaudeEngine(
                name=agent_def.display_label,
                model_name=agent_def.engine,
                client=client,
            )
        elif sdk_type == "openai":
            if cache_key not in self._client_cache:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": api_key}
                if agent_def.server:
                    kwargs["base_url"] = agent_def.server
                self._client_cache[cache_key] = OpenAI(**kwargs)
            client = self._client_cache[cache_key]
            ai_engine = OpenAIEngine(
                name=agent_def.display_label,
                model_name=agent_def.engine,
                client=client,
            )
        else:
            raise ValueError(f"Unsupported SDK type: '{sdk_type}'")

        # Apply max_output_tokens
        effective_max_tokens = (
            agent_def.max_output_tokens
            if agent_def.max_output_tokens is not None
            else DEFAULT_MAX_OUTPUT_TOKENS
        )
        if hasattr(ai_engine, "max_output_tokens"):
            ai_engine.max_output_tokens = effective_max_tokens
        if hasattr(ai_engine, "max_tokens"):
            ai_engine.max_tokens = effective_max_tokens

        # Apply runtime settings
        ai_engine.max_turns = runtime_settings.max_history_turns

        return ai_engine

    def _get_or_create_openai_client(self, agent_def: AgentDefinition) -> Any:
        """Create or retrieve a cached OpenAI SDK client."""
        resolved_key = self._resolve_api_key(agent_def)
        api_key = resolved_key or "dummy"

        cache_key = f"openai-compatible:{agent_def.server}:{api_key}"
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=agent_def.server,
        )
        self._client_cache[cache_key] = client
        return client

    @staticmethod
    def _resolve_api_key(agent_def: AgentDefinition) -> str | None:
        """Resolve API key from agent definition."""
        from .config import _resolve_api_key_for_agent

        return _resolve_api_key_for_agent(agent_def)
