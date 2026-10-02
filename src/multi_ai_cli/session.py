"""
Agent session management for Multi-AI CLI.

Provides AgentSession which holds per-session AIEngine instances,
ensuring that within a single session the same agent key returns
the same instance (preserving conversation history), while different
sessions maintain completely independent state.
"""

from typing import Any

from .agent_factory import AgentFactory
from .registry import AgentRegistry


class AgentSession:
    """
    Holds AIEngine instances for a single execution session.

    Within a session, calling get_agent() with the same key returns
    the same AIEngine instance, preserving conversation history.
    Different AgentSession instances are completely independent.

    Usage:
        session = AgentSession(registry, factory)
        engine = session.get_agent("reviewer")  # creates on first call
        engine = session.get_agent("reviewer")  # returns same instance
    """

    def __init__(
        self,
        registry: AgentRegistry,
        factory: AgentFactory,
        *,
        legacy_sdk_map: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize an AgentSession.

        Args:
            registry: The agent registry containing definitions.
            factory: The factory used to create engine instances.
            legacy_sdk_map: Optional mapping of agent_key -> sdk_type
                for legacy config format. If provided, factory.create_legacy()
                is used instead of factory.create().
        """
        self._registry = registry
        self._factory = factory
        self._instances: dict[str, Any] = {}
        self._legacy_sdk_map = legacy_sdk_map

    def get_agent(self, agent_key: str) -> Any:
        """
        Get or create an AIEngine instance for the given agent key.

        On first call for a given key, creates a new instance from
        the AgentDefinition. Subsequent calls return the same instance.

        Args:
            agent_key: The agent key to look up.

        Returns:
            The AIEngine instance for this agent in this session.

        Raises:
            ValueError: If the agent key is not registered.
        """
        if agent_key not in self._instances:
            agent_def = self._registry.get(agent_key)
            if self._legacy_sdk_map and agent_key in self._legacy_sdk_map:
                sdk_type = self._legacy_sdk_map[agent_key]
                self._instances[agent_key] = self._factory.create_legacy(
                    agent_def, sdk_type
                )
            else:
                self._instances[agent_key] = self._factory.create(agent_def)
        return self._instances[agent_key]

    def has_agent(self, agent_key: str) -> bool:
        """
        Check if an agent instance has been created in this session.

        Args:
            agent_key: The agent key to check.

        Returns:
            True if the agent has been instantiated in this session.
        """
        return agent_key in self._instances

    def all_loaded_agents(self) -> dict[str, Any]:
        """
        Return a copy of all currently instantiated agents in this session.

        Returns:
            Dictionary mapping agent keys to their AIEngine instances.
        """
        return dict(self._instances)

    def scrub(self, agent_key: str | None = None) -> list[str]:
        """
        Clear history for agent(s) in this session.

        Args:
            agent_key: Specific agent to scrub, or None for all
                loaded agents.

        Returns:
            List of agent keys that were scrubbed.
        """
        scrubbed: list[str] = []
        if agent_key is None:
            for key, engine in self._instances.items():
                engine.scrub()
                scrubbed.append(key)
        elif agent_key in self._instances:
            self._instances[agent_key].scrub()
            scrubbed.append(agent_key)
        return scrubbed

    def agent_keys(self) -> list[str]:
        """
        Return the list of agent keys known to the registry.

        This returns all defined agents, not just those instantiated
        in this session.

        Returns:
            List of all registered agent keys.
        """
        return self._registry.keys()

    def is_valid_agent(self, agent_key: str) -> bool:
        """
        Check if an agent key exists in the registry.

        Args:
            agent_key: The agent key to check.

        Returns:
            True if the agent is registered.
        """
        return self._registry.has(agent_key)

    def create_child_session(self) -> "AgentSession":
        """
        Create a new independent child session sharing the same
        registry and factory but with no loaded instances.

        Used for parallel task execution in @sequence.

        Returns:
            A new independent AgentSession.
        """
        return AgentSession(
            registry=self._registry,
            factory=self._factory,
            legacy_sdk_map=self._legacy_sdk_map,
        )
