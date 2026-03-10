"""
Agent/Engine registry and data models.

This module provides the core data structures and validation logic
for the Agent/Engine separation architecture. It contains no dependencies
on other internal modules to avoid circular imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── Constants ──

ALLOWED_NAMESPACES = {"gpt", "claude", "gemini", "grok", "local"}
ALLOWED_ROLES = {"code", "review", "plan", "doc", "chat", "test", "image"}

VALID_ENGINE_TYPES = {"openai", "gemini", "anthropic", "grok", "local_openai"}

# namespace → set of allowed engine types
NAMESPACE_ENGINE_FAMILY: dict[str, set[str]] = {
    "gpt": {"openai"},
    "claude": {"anthropic"},
    "gemini": {"gemini"},
    "grok": {"grok"},
    "local": {"local_openai"},
}

# Display capitalization rules by namespace
NAMESPACE_DISPLAY: dict[str, str] = {
    "gpt": "GPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "grok": "Grok",
    "local": "Local",
}

AGENT_NAME_PATTERN = re.compile(r"^([a-z]+)(?:\.([a-z]+))?$")


# ── Data classes ──


@dataclass
class EngineDefinition:
    """Physical execution backend definition."""

    name: str  # ENGINE section name (e.g., "openai_main")
    type: str  # "openai" | "gemini" | "anthropic" | "grok" | "local_openai"
    api_key_ref: str | None = None  # Key name in [API_KEYS]
    api_key: str | None = None  # Inline API key (for local, etc.)
    model_ref: str | None = None  # Alias name in [MODELS]
    model: str | None = None  # Inline direct specification
    base_url: str | None = None
    max_output_tokens: int = 4096


@dataclass
class AgentDefinition:
    """Logical agent definition."""

    agent_key: str  # "gpt", "gpt.doc", "gemini.chat", etc.
    engine_name: str  # Bound engine name (ENGINE section name)
    namespace: str = ""  # Parsed: "gpt", "claude", etc.
    role: str | None = None  # Parsed: "doc", "plan", etc. (None if absent)

    @property
    def display_label(self) -> str:
        """Generate a display label: GPT.doc, Claude.plan, etc."""
        ns_display = NAMESPACE_DISPLAY.get(self.namespace, self.namespace.capitalize())
        if self.role:
            return f"{ns_display}.{self.role}"
        return ns_display


@dataclass
class RuntimeSettings:
    """Global runtime settings."""

    max_history_turns: int = 30
    auto_continue_max_rounds: int = 5
    auto_continue_tail_chars: int = 1200


# ── Registry classes ──


class ModelRegistry:
    """Model alias catalog loaded from the [MODELS] section."""

    def __init__(self) -> None:
        """Initialize an empty model registry."""
        self._aliases: dict[str, str] = {}

    def register(self, alias: str, model_string: str) -> None:
        """Register a model alias pointing to its real model identifier/string."""
        self._aliases[alias] = model_string

    def resolve(self, alias: str) -> str:
        """Resolve an alias to its corresponding model string/identifier."""
        if alias not in self._aliases:
            raise ValueError(f"Model alias '{alias}' not found in [MODELS].")
        return self._aliases[alias]

    def has(self, alias: str) -> bool:
        """Check if the given model alias is registered."""
        return alias in self._aliases

    def all_aliases(self) -> dict[str, str]:
        """Return a copy of all currently registered alias → model mappings."""
        return dict(self._aliases)

    def clear(self) -> None:
        """Remove all registered model aliases from the registry."""
        self._aliases.clear()


class EngineRegistry:
    """Management of engine definitions loaded from [ENGINE.*] sections."""

    def __init__(self) -> None:
        """Initialize an empty model registry."""
        self._engines: dict[str, EngineDefinition] = {}

    def register(self, engine_def: EngineDefinition) -> None:
        """Register an engine definition using its name as the key."""
        self._engines[engine_def.name] = engine_def

    def get(self, name: str) -> EngineDefinition:
        """Retrieve the engine definition by name."""
        if name not in self._engines:
            raise ValueError(f"Engine '{name}' not found.")
        return self._engines[name]

    def has(self, name: str) -> bool:
        """Check whether an engine with the given name is registered."""
        return name in self._engines

    def all_engines(self) -> dict[str, EngineDefinition]:
        """Return a copy of all currently registered engine definitions."""
        return dict(self._engines)

    def clear(self) -> None:
        """Remove all registered engines from the registry."""
        self._engines.clear()


class AgentRegistry:
    """Management of agent definitions loaded from [AGENT.*] sections."""

    def __init__(self) -> None:
        """agent_key -> AgentDefinition mapping."""
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent_def: AgentDefinition) -> None:
        """Register an agent definition."""
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


def validate_agent_name(agent_key: str) -> tuple[str, str | None]:
    """
    Validate the agent key format, namespace, and role.

    Returns:
        (namespace, role) tuple

    Raises:
        ValueError: If the name is invalid
    """
    m = AGENT_NAME_PATTERN.match(agent_key)
    if not m:
        raise ValueError(
            f"Invalid agent name '{agent_key}'. "
            f"Must be '<namespace>' or '<namespace>.<role>'."
        )
    namespace = m.group(1)
    role = m.group(2)  # None if absent

    if namespace not in ALLOWED_NAMESPACES:
        raise ValueError(
            f"Unknown namespace '{namespace}' in agent '{agent_key}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_NAMESPACES))}"
        )
    if role is not None and role not in ALLOWED_ROLES:
        raise ValueError(
            f"Unknown role '{role}' in agent '{agent_key}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_ROLES))}"
        )
    return namespace, role


def validate_namespace_engine_consistency(
    agent_key: str,
    namespace: str,
    engine_def: EngineDefinition,
) -> None:
    """
    Validate whether the namespace matches the engine type family.

    Raises:
        ValueError: If they do not match
    """
    allowed_types = NAMESPACE_ENGINE_FAMILY.get(namespace, set())
    if engine_def.type not in allowed_types:
        raise ValueError(
            f"Agent '{agent_key}' has namespace '{namespace}' but engine "
            f"'{engine_def.name}' has type '{engine_def.type}'. "
            f"Allowed engine types for '{namespace}': {allowed_types}"
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

model_registry = ModelRegistry()
engine_registry = EngineRegistry()
agent_registry = AgentRegistry()
runtime_settings = RuntimeSettings()


def reset_registries() -> None:
    """Reset all registries and runtime settings."""
    model_registry.clear()
    engine_registry.clear()
    agent_registry.clear()
    runtime_settings.max_history_turns = 30
    runtime_settings.auto_continue_max_rounds = 5
    runtime_settings.auto_continue_tail_chars = 1200
