"""Tests for multi_ai_cli.config module.

The test suite's conftest.py replaces multi_ai_cli.config in sys.modules
with a MagicMock. This test file works around that by loading the real
module directly from its source file path.
"""

import configparser
import importlib.util
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_real_config_module():
    """
    Load the real config module from its source file, bypassing any
    conftest mock that may have replaced it in sys.modules.

    Returns a fresh module object each time, completely independent
    of sys.modules['multi_ai_cli.config'].
    """
    src_path = (
        Path(__file__).resolve().parents[2] / "src" / "multi_ai_cli" / "config.py"
    )
    if not src_path.exists():
        src_path = (
            Path(__file__).resolve().parents[3] / "src" / "multi_ai_cli" / "config.py"
        )
    if not src_path.exists():
        pytest.skip(f"Cannot locate config.py source at {src_path}")

    spec = importlib.util.spec_from_file_location(
        "multi_ai_cli.config._real", str(src_path)
    )
    mod = importlib.util.module_from_spec(spec)

    saved = sys.modules.get("multi_ai_cli.config")
    sys.modules["multi_ai_cli.config"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        if saved is not None:
            sys.modules["multi_ai_cli.config"] = saved
        else:
            sys.modules.pop("multi_ai_cli.config", None)

    return mod


@pytest.fixture
def config_mod():
    """Provides a freshly loaded real config module for each test."""
    mod = _load_real_config_module()
    mod.config = configparser.ConfigParser()
    mod.logger = logging.getLogger("MultiAI.test_config_isolated")
    mod.logger.handlers.clear()
    mod.is_log_enabled = False
    mod.INI_PATH = None
    mod.legacy_sdk_map = None
    mod.is_new_config_format = False
    return mod


class TestSetupConfig:
    def test_loads_ini(self, config_mod):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("[API_KEYS]\ntest_key = abc123\n")
            tmppath = f.name

        try:
            config_mod.setup_config(tmppath)
            assert config_mod.config.get("API_KEYS", "test_key") == "abc123"
            assert config_mod.INI_PATH == tmppath
        finally:
            os.unlink(tmppath)


class TestSetupLogger:
    def test_logger_disabled(self, config_mod):
        config_mod.config.read_dict({"logging": {"enabled": "false"}})
        config_mod.setup_logger(no_log=True)
        assert config_mod.is_log_enabled is False

    def test_logger_enabled(self, config_mod):
        tmpdir = tempfile.mkdtemp()
        config_mod.config.read_dict(
            {
                "logging": {
                    "enabled": "true",
                    "log_dir": tmpdir,
                    "base_filename": "test_config.log",
                }
            }
        )
        config_mod.setup_logger(no_log=False)
        assert config_mod.is_log_enabled is True

    def test_no_log_flag_overrides(self, config_mod):
        config_mod.config.read_dict({"logging": {"enabled": "true"}})
        config_mod.setup_logger(no_log=True)
        assert config_mod.is_log_enabled is False


class TestGetApiKey:
    def test_from_ini(self, config_mod, monkeypatch):
        config_mod.config.read_dict({"API_KEYS": {"test_key": "from_ini"}})
        monkeypatch.delenv("TEST_KEY_ENV", raising=False)
        result = config_mod.get_api_key("test_key", "TEST_KEY_ENV")
        assert result == "from_ini"

    def test_from_env(self, config_mod, monkeypatch):
        config_mod.config.read_dict({"API_KEYS": {"test_key": "from_ini"}})
        monkeypatch.setenv("TEST_KEY_ENV", "from_env")
        result = config_mod.get_api_key("test_key", "TEST_KEY_ENV")
        assert result == "from_env"

    def test_env_takes_priority(self, config_mod, monkeypatch):
        config_mod.config.read_dict({"API_KEYS": {"test_key": "from_ini"}})
        monkeypatch.setenv("TEST_KEY_ENV", "env_value")
        result = config_mod.get_api_key("test_key", "TEST_KEY_ENV")
        assert result == "env_value"

    def test_missing_raises(self, config_mod, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        with pytest.raises(ValueError, match="API key"):
            config_mod.get_api_key("nonexistent_key", "MISSING_KEY")


class TestDetectNewConfigFormat:
    def test_no_agent_sections(self, config_mod):
        config_mod.config.read_dict({"API_KEYS": {"key": "val"}})
        assert config_mod._detect_new_config_format() is False

    def test_with_agent_section(self, config_mod):
        config_mod.config.read_dict(
            {
                "AGENT.test": {
                    "adapter": "openai-compatible",
                    "server": "http://localhost",
                    "engine": "gpt-4",
                }
            }
        )
        assert config_mod._detect_new_config_format() is True


class TestResolveApiKeyForAgent:
    """Test _resolve_api_key_for_agent using SimpleNamespace to avoid
    conftest mock interference with the real AgentDefinition import."""

    def _make_agent_def(self, api_key_ref=None):
        """Create a simple object with the same interface as AgentDefinition."""
        return SimpleNamespace(api_key_ref=api_key_ref)

    def test_with_ref(self, config_mod, monkeypatch):
        config_mod.config.read_dict({"API_KEYS": {"my_key": "secret123"}})
        monkeypatch.delenv("MY_KEY", raising=False)

        ad = self._make_agent_def(api_key_ref="my_key")
        result = config_mod._resolve_api_key_for_agent(ad)
        assert result == "secret123"

    def test_no_ref_returns_none(self, config_mod):
        ad = self._make_agent_def(api_key_ref=None)
        result = config_mod._resolve_api_key_for_agent(ad)
        assert result is None

    def test_empty_ref_returns_none(self, config_mod):
        ad = self._make_agent_def(api_key_ref="")
        result = config_mod._resolve_api_key_for_agent(ad)
        assert result is None

    def test_env_override(self, config_mod, monkeypatch):
        config_mod.config.read_dict({"API_KEYS": {"my_key": "secret123"}})
        monkeypatch.setenv("MY_KEY", "env_secret")

        ad = self._make_agent_def(api_key_ref="my_key")
        result = config_mod._resolve_api_key_for_agent(ad)
        assert result == "env_secret"


class TestConstants:
    def test_defaults(self, config_mod):
        assert config_mod.DEFAULT_LOG_MAX_BYTES == 10485760
        assert config_mod.DEFAULT_LOG_BACKUP_COUNT == 5
        assert config_mod.DEFAULT_MAX_HISTORY_TURNS == 30


class TestGetGitHubToken:
    def test_from_env(self, config_mod, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "gh_token_123")
        assert config_mod.get_github_token() == "gh_token_123"

    def test_from_ini(self, config_mod, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        config_mod.config.read_dict({"GITHUB": {"token": "ini_token"}})
        assert config_mod.get_github_token() == "ini_token"

    def test_missing_raises(self, config_mod, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GitHub token"):
            config_mod.get_github_token()


class TestGetGitHubApiBaseUrl:
    def test_default(self, config_mod, monkeypatch):
        monkeypatch.delenv("GITHUB_API_BASE_URL", raising=False)
        assert config_mod.get_github_api_base_url() == "https://api.github.com"

    def test_from_env(self, config_mod, monkeypatch):
        monkeypatch.setenv("GITHUB_API_BASE_URL", "https://custom.api.com/")
        assert config_mod.get_github_api_base_url() == "https://custom.api.com"

    def test_from_ini(self, config_mod, monkeypatch):
        monkeypatch.delenv("GITHUB_API_BASE_URL", raising=False)
        config_mod.config.read_dict(
            {"GITHUB": {"api_base_url": "https://gh.enterprise.com"}}
        )
        assert config_mod.get_github_api_base_url() == "https://gh.enterprise.com"
