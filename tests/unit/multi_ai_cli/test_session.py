"""Tests for multi_ai_cli.session module."""

from unittest.mock import MagicMock

import pytest

from multi_ai_cli.registry import AgentDefinition, AgentRegistry
from multi_ai_cli.session import AgentSession


def _make_registry(*keys):
    """Helper to create a registry with given keys."""
    registry = AgentRegistry()
    for key in keys:
        registry.register(
            AgentDefinition(
                agent_key=key,
                adapter="openai-compatible",
                server="http://localhost",
                engine="gpt-4",
            )
        )
    return registry


class TestAgentSession:
    def test_get_agent_creates_on_first_call(self):
        registry = _make_registry("test")
        factory = MagicMock()
        engine = MagicMock()
        factory.create.return_value = engine

        session = AgentSession(registry=registry, factory=factory)
        result = session.get_agent("test")
        assert result is engine
        factory.create.assert_called_once()

    def test_get_agent_returns_same_instance(self):
        registry = _make_registry("test")
        factory = MagicMock()
        engine = MagicMock()
        factory.create.return_value = engine

        session = AgentSession(registry=registry, factory=factory)
        first = session.get_agent("test")
        second = session.get_agent("test")
        assert first is second
        assert factory.create.call_count == 1

    def test_get_agent_unknown_raises(self):
        registry = _make_registry("test")
        factory = MagicMock()
        session = AgentSession(registry=registry, factory=factory)
        with pytest.raises(ValueError, match="not defined"):
            session.get_agent("unknown")

    def test_has_agent(self):
        registry = _make_registry("test")
        factory = MagicMock()
        factory.create.return_value = MagicMock()

        session = AgentSession(registry=registry, factory=factory)
        assert not session.has_agent("test")
        session.get_agent("test")
        assert session.has_agent("test")

    def test_all_loaded_agents(self):
        registry = _make_registry("a", "b")
        factory = MagicMock()
        factory.create.return_value = MagicMock()

        session = AgentSession(registry=registry, factory=factory)
        assert session.all_loaded_agents() == {}

        session.get_agent("a")
        loaded = session.all_loaded_agents()
        assert "a" in loaded
        assert "b" not in loaded

    def test_all_loaded_returns_copy(self):
        registry = _make_registry("test")
        factory = MagicMock()
        factory.create.return_value = MagicMock()

        session = AgentSession(registry=registry, factory=factory)
        session.get_agent("test")
        loaded = session.all_loaded_agents()
        loaded["extra"] = "something"
        assert not session.has_agent("extra")

    def test_scrub_all(self):
        registry = _make_registry("a", "b")
        factory = MagicMock()

        engine_a = MagicMock()
        engine_b = MagicMock()
        factory.create.side_effect = [engine_a, engine_b]

        session = AgentSession(registry=registry, factory=factory)
        session.get_agent("a")
        session.get_agent("b")

        scrubbed = session.scrub()
        assert set(scrubbed) == {"a", "b"}
        engine_a.scrub.assert_called_once()
        engine_b.scrub.assert_called_once()

    def test_scrub_specific(self):
        registry = _make_registry("a", "b")
        factory = MagicMock()

        engine_a = MagicMock()
        engine_b = MagicMock()
        factory.create.side_effect = [engine_a, engine_b]

        session = AgentSession(registry=registry, factory=factory)
        session.get_agent("a")
        session.get_agent("b")

        scrubbed = session.scrub("a")
        assert scrubbed == ["a"]
        engine_a.scrub.assert_called_once()
        engine_b.scrub.assert_not_called()

    def test_scrub_not_loaded(self):
        registry = _make_registry("a")
        factory = MagicMock()
        session = AgentSession(registry=registry, factory=factory)

        scrubbed = session.scrub("a")
        assert scrubbed == []

    def test_agent_keys_from_registry(self):
        registry = _make_registry("x", "y", "z")
        factory = MagicMock()
        session = AgentSession(registry=registry, factory=factory)
        keys = session.agent_keys()
        assert set(keys) == {"x", "y", "z"}

    def test_is_valid_agent(self):
        registry = _make_registry("valid")
        factory = MagicMock()
        session = AgentSession(registry=registry, factory=factory)
        assert session.is_valid_agent("valid")
        assert not session.is_valid_agent("invalid")

    def test_create_child_session(self):
        registry = _make_registry("test")
        factory = MagicMock()
        factory.create.return_value = MagicMock()

        parent = AgentSession(registry=registry, factory=factory)
        parent.get_agent("test")

        child = parent.create_child_session()
        assert not child.has_agent("test")
        assert child.is_valid_agent("test")
        assert child.agent_keys() == parent.agent_keys()

    def test_legacy_sdk_map(self):
        registry = _make_registry("gpt")
        factory = MagicMock()
        engine = MagicMock()
        factory.create_legacy.return_value = engine

        session = AgentSession(
            registry=registry,
            factory=factory,
            legacy_sdk_map={"gpt": "openai"},
        )
        result = session.get_agent("gpt")
        assert result is engine
        factory.create_legacy.assert_called_once()
        factory.create.assert_not_called()

    def test_legacy_sdk_map_fallback(self):
        registry = _make_registry("custom")
        factory = MagicMock()
        engine = MagicMock()
        factory.create.return_value = engine

        session = AgentSession(
            registry=registry,
            factory=factory,
            legacy_sdk_map={"gpt": "openai"},
        )
        result = session.get_agent("custom")
        assert result is engine
        factory.create.assert_called_once()
        factory.create_legacy.assert_not_called()

    def test_child_session_inherits_legacy_map(self):
        registry = _make_registry("gpt")
        factory = MagicMock()
        factory.create_legacy.return_value = MagicMock()

        parent = AgentSession(
            registry=registry,
            factory=factory,
            legacy_sdk_map={"gpt": "openai"},
        )
        child = parent.create_child_session()
        child.get_agent("gpt")
        factory.create_legacy.assert_called()
