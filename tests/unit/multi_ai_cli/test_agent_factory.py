"""Tests for multi_ai_cli.agent_factory module."""

from unittest.mock import patch

import pytest

from multi_ai_cli.agent_factory import AgentFactory
from multi_ai_cli.registry import DEFAULT_MAX_OUTPUT_TOKENS, AgentDefinition


class TestAgentFactory:
    def setup_method(self):
        self.factory = AgentFactory()

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="test_key")
    def test_create_openai_compatible(self, mock_resolve):
        """Test that create() returns a working OpenAIEngine instance."""
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost:11434/v1",
            engine="llama3",
            api_key_ref="test_key",
        )
        result = self.factory.create(ad)

        # Verify the returned engine has correct properties
        from multi_ai_cli.engines import OpenAIEngine

        assert isinstance(result, OpenAIEngine)
        assert result.name == "@test"
        assert result.model_name == "llama3"

    def test_create_unsupported_adapter(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="unsupported",
            server="http://localhost",
            engine="model",
        )
        with pytest.raises(ValueError, match="unsupported adapter"):
            self.factory.create(ad)

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="key")
    def test_create_caches_client(self, mock_resolve):
        """Client should be created once and reused for same server+key."""
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="model",
            api_key_ref="k",
        )
        engine1 = self.factory.create(ad)
        engine2 = self.factory.create(ad)

        # Both engines should share the same underlying client
        assert engine1.get_client() is engine2.get_client()
        # But engines themselves are distinct instances
        assert engine1 is not engine2

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="key")
    def test_create_applies_max_output_tokens(self, mock_resolve):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="model",
            max_output_tokens=16384,
        )
        result = self.factory.create(ad)
        # OpenAIEngine uses max_tokens attribute
        assert result.max_tokens == 16384

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="key")
    def test_create_default_max_output_tokens(self, mock_resolve):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="model",
        )
        result = self.factory.create(ad)
        assert result.max_tokens == DEFAULT_MAX_OUTPUT_TOKENS


class TestAgentFactoryLegacy:
    def setup_method(self):
        self.factory = AgentFactory()

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="key")
    def test_create_legacy_openai(self, mock_resolve):
        ad = AgentDefinition(
            agent_key="gpt",
            adapter="openai-compatible",
            server="https://api.openai.com/v1",
            engine="gpt-4o",
            api_key_ref="openai_api_key",
        )
        result = self.factory.create_legacy(ad, "openai")

        from multi_ai_cli.engines import OpenAIEngine

        assert isinstance(result, OpenAIEngine)
        assert result.name == "@gpt"
        assert result.model_name == "gpt-4o"

    def test_create_legacy_unsupported(self):
        ad = AgentDefinition(
            agent_key="test",
            adapter="openai-compatible",
            server="http://localhost",
            engine="model",
        )
        with pytest.raises(ValueError, match="Unsupported SDK type"):
            self.factory.create_legacy(ad, "unsupported_sdk")

    @patch("multi_ai_cli.config._resolve_api_key_for_agent", return_value="key")
    def test_create_legacy_caches_client(self, mock_resolve):
        ad = AgentDefinition(
            agent_key="gpt",
            adapter="openai-compatible",
            server="https://api.openai.com/v1",
            engine="gpt-4o",
            api_key_ref="openai_api_key",
        )
        engine1 = self.factory.create_legacy(ad, "openai")
        engine2 = self.factory.create_legacy(ad, "openai")
        assert engine1.get_client() is engine2.get_client()
        assert engine1 is not engine2
