"""Tests for multi_ai_cli.registry module."""

import pytest

from multi_ai_cli.registry import (
    AGENT_ALIAS_PATTERN,
    DEFAULT_MAX_OUTPUT_TOKENS,
    VALID_ADAPTER_TYPES,
    AgentDefinition,
    AgentRegistry,
    RuntimeSettings,
    agent_registry,
    reset_registries,
    runtime_settings,
    validate_agent_alias,
)


class TestAgentDefinition:
    def test_creation(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        assert ad.agent_key == "test"
        assert ad.adapter == "openai-compatible"
        assert ad.server == "http://localhost"
        assert ad.engine == "gpt-4"
        assert ad.api_key_ref is None
        assert ad.role is None
        assert ad.max_output_tokens is None

    def test_display_label(self):
        ad = AgentDefinition(
            agent_key="reviewer",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        assert ad.display_label == "@reviewer"

    def test_frozen(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        with pytest.raises(AttributeError):
            ad.agent_key = "changed"

    def test_optional_fields(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
            api_key_ref="my_key",
            role="coder",
            max_output_tokens=8192,
        )
        assert ad.api_key_ref == "my_key"
        assert ad.role == "coder"
        assert ad.max_output_tokens == 8192


class TestRuntimeSettings:
    def test_defaults(self):
        rs = RuntimeSettings()
        assert rs.max_history_turns == 30
        assert rs.auto_continue_max_rounds == 5
        assert rs.auto_continue_tail_chars == 1200

    def test_custom_values(self):
        rs = RuntimeSettings(
            max_history_turns=50,
            auto_continue_max_rounds=10,
            auto_continue_tail_chars=2000,
        )
        assert rs.max_history_turns == 50
        assert rs.auto_continue_max_rounds == 10
        assert rs.auto_continue_tail_chars == 2000


class TestAgentRegistry:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register_and_get(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        self.registry.register(ad)
        assert self.registry.get("test") is ad

    def test_register_duplicate_raises(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        self.registry.register(ad)
        with pytest.raises(ValueError, match="Duplicate"):
            self.registry.register(ad)

    def test_get_missing_raises(self):
        with pytest.raises(ValueError, match="not defined"):
            self.registry.get("nonexistent")

    def test_has(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        assert not self.registry.has("test")
        self.registry.register(ad)
        assert self.registry.has("test")

    def test_keys(self):
        for key in ["alpha", "beta", "gamma"]:
            self.registry.register(
                AgentDefinition(
                    agent_key=key,
                    adapter="openai-compatible",
                    server="http://localhost",
                    engine="gpt-4",
                )
            )
        keys = self.registry.keys()
        assert set(keys) == {"alpha", "beta", "gamma"}

    def test_all_agents_returns_copy(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        self.registry.register(ad)
        all_agents = self.registry.all_agents()
        assert "test" in all_agents
        # Modifying the copy should not affect the registry
        all_agents["extra"] = ad
        assert not self.registry.has("extra")

    def test_clear(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        self.registry.register(ad)
        self.registry.clear()
        assert not self.registry.has("test")
        assert self.registry.keys() == []

    def test_register_empty_string_fields(self):
        # Edge case: verify registry accepts agents with empty string fields
        # as the dataclass does not enforce non-empty constraint on non-keys
        ad = AgentDefinition(
            agent_key="test",
            adapter="",
            server="",
            engine="",
        )
        self.registry.register(ad)
        assert self.registry.get("test").adapter == ""
        assert self.registry.get("test").server == ""
        assert self.registry.get("test").engine == ""

    def test_register_with_unvalidated_alias(self):
        # Ensure registry does not implicitly call validate_agent_alias upon registration
        # unless explicit application logic is expected.
        invalid_key = "Invalid Name!"
        ad = AgentDefinition(
            agent_key=invalid_key,
            adapter="openai-compatible",
            server="http://localhost",
            engine="gpt-4",
        )
        # Currently registration is a pure storage mechanism
        self.registry.register(ad)
        assert self.registry.has(invalid_key)


class TestValidateAgentAlias:
    def test_valid_aliases(self):
        for alias in ["gpt", "claude-3", "my_agent", "agent-1", "a"]:
            validate_agent_alias(alias)  # Should not raise

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_agent_alias("")

    def test_invalid_aliases_raise(self):
        for alias in [
            "Agent1",
            "my agent",
            "agent!",
            "abc.def",
            "@test",
            "UPPER",
            "Space ",
        ]:
            with pytest.raises(ValueError, match="Invalid agent name"):
                validate_agent_alias(alias)


class TestResetRegistries:
    def test_reset(self):
        agent_registry.register(
            AgentDefinition(
                agent_key="tmp",
                adapter="openai-compatible",
                server="http://localhost",
                engine="gpt-4",
            )
        )
        runtime_settings.max_history_turns = 99
        runtime_settings.auto_continue_max_rounds = 99
        runtime_settings.auto_continue_tail_chars = 99

        reset_registries()

        assert not agent_registry.has("tmp")
        assert runtime_settings.max_history_turns == 30
        assert runtime_settings.auto_continue_max_rounds == 5
        assert runtime_settings.auto_continue_tail_chars == 1200


class TestConstants:
    def test_valid_adapter_types(self):
        assert "openai-compatible" in VALID_ADAPTER_TYPES

    def test_default_max_output_tokens(self):
        assert DEFAULT_MAX_OUTPUT_TOKENS == 4096

    def test_agent_alias_pattern(self):
        assert AGENT_ALIAS_PATTERN.match("hello-world_123")
        assert not AGENT_ALIAS_PATTERN.match("Hello")
        assert not AGENT_ALIAS_PATTERN.match("")
