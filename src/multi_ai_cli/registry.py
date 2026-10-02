"""
Agent/Engine registry and data models.

This module provides the core data structures and validation logic
for the Agent definition architecture. It contains no dependencies
on other internal modules to avoid circular imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── Constants ──

VALID_ADAPTER_TYPES = {"openai-compatible"}

AGENT_ALIAS_PATTERN = re.compile(r"^[a-z0-9_-]+$")

DEFAULT_MAX_OUTPUT_TOKENS = 4096


# ── Data classes ──


@dataclass
class AgentDefinition:
    """Agent definition containing all execution parameters.

    An agent is a logical alias that binds a name to an adapter,
    server endpoint, engine (model), and optional authentication
    and configuration.
    """

    agent_key: str  # CLI alias (e.g., "reviewer", "local", "coder")
    adapter: str  # Connection method (e.g., "openai-compatible")
    server: str  # API endpoint base URL
    engine: str  # Model name / engine identifier
    api_key_ref: str | None = None  # Key name in [API_KEYS]
    role: str | None = None  # Arbitrary role string
    max_output_tokens: int | None = None  # Response token limit

    @property
    def display_label(self) -> str:
        """Generate a display label: @<agent_key>."""
        return f"@{self.agent_key}"


@dataclass
class RuntimeSettings:
    """Global runtime settings."""

    max_history_turns: int = 30
    auto_continue_max_rounds: int = 5
    auto_continue_tail_chars: int = 1200


# ── Registry classes ──


class AgentRegistry:
    """Management of agent definitions loaded from [AGENT.*] sections."""

    def __init__(self) -> None:
        """agent_key -> AgentDefinition mapping."""
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent_def: AgentDefinition) -> None:
        """Register an agent definition."""
        if agent_def.agent_key in self._agents:
            raise ValueError(f"Duplicate agent definition: '{agent_def.agent_key}'.")
        self._agents[agent_def.agent_key] = agent_def

    def get(self, agent_key: str) -> AgentDefinition:
        """Get the agent definition for the given key."""
        if agent_key not in self._agents:
            raise ValueError(f"Agent '{agent_key}' is not defined.")
        return self._agents[agent_key]

    def has(self, agent_key: str) -> bool:
        """Check if an agent with the given key is registered."""
        return agent_key in self._agents

    def all_agents(self) -> dict[str, AgentDefinition]:
        """Return a copy of all registered agent definitions."""
        return dict(self._agents)

    def keys(self) -> list[str]:
        """Return a list of all registered agent keys."""
        return list(self._agents.keys())

    def clear(self) -> None:
        """Remove all registered agents (clear the registry)."""
        self._agents.clear()


# ── Validation functions ──


def validate_agent_alias(agent_key: str) -> None:
    """
    Validate the agent alias format.

    Agent names must consist of lowercase alphanumeric characters,
    hyphens, and underscores only.

    Args:
        agent_key: The agent alias to validate.

    Raises:
        ValueError: If the alias is empty or contains invalid characters.
    """
    if not agent_key:
        raise ValueError("Agent name must not be empty.")
    if not AGENT_ALIAS_PATTERN.match(agent_key):
        raise ValueError(
            f"Invalid agent name '{agent_key}'. Allowed pattern: ^[a-z0-9_-]+$"
        )


def validate_no_duplicate_agents_in_parallel(agent_keys: list[str]) -> None:
    """
    Validate that the same agent is not duplicated within a parallel block.

    Raises:
        ValueError: If duplicates exist
    """
    seen: set[str] = set()
    for key in agent_keys:
        if key in seen:
            raise ValueError(
                f"Duplicate agent '@{key}' in parallel block. "
                f"An agent is stateful and cannot run concurrently with itself."
            )
        seen.add(key)


# ── Global registry instances ──

agent_registry = AgentRegistry()
runtime_settings = RuntimeSettings()


def reset_registries() -> None:
    """Reset all registries and runtime settings."""
    agent_registry.clear()
    runtime_settings.max_history_turns = 30
    runtime_settings.auto_continue_max_rounds = 5
    runtime_settings.auto_continue_tail_chars = 1200
