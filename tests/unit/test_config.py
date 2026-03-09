import configparser
import os
from unittest.mock import MagicMock, patch

import pytest

from multi_ai_cli import config as app_config


class TestAppConfig:
    def setup_method(self):
        """Reset global state before each test"""
        app_config.config = configparser.ConfigParser()
        app_config.INI_PATH = None
        app_config.is_log_enabled = False
        app_config.engines = {}
        app_config.logger.handlers.clear()

    @patch("configparser.ConfigParser.read")
    def test_setup_config(self, mock_read):
        test_ini_path = "test_config.ini"
        app_config.setup_config(test_ini_path)
        assert app_config.INI_PATH == test_ini_path
        mock_read.assert_called_once_with(test_ini_path, encoding="utf-8-sig")

    @patch("multi_ai_cli.config.RotatingFileHandler")
    @patch("os.makedirs")
    def test_setup_logger_with_logging_enabled(self, mock_makedirs, mock_handler_cls):
        app_config.config.read_dict(
            {
                "logging": {
                    "enabled": "true",
                    "log_dir": "test_logs",
                    "base_filename": "test.log",
                    "max_bytes": "1024",
                    "backup_count": "2",
                    "log_level": "DEBUG",
                }
            }
        )

        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        app_config.setup_logger(no_log=False)

        assert app_config.is_log_enabled is True
        mock_makedirs.assert_called_once_with("test_logs", exist_ok=True)
        mock_handler_cls.assert_called_once_with(
            os.path.join("test_logs", "test.log"),
            maxBytes=1024,
            backupCount=2,
            encoding="utf-8",
        )
        assert mock_handler in app_config.logger.handlers

    @patch("multi_ai_cli.config.RotatingFileHandler")
    @patch("os.makedirs")
    def test_setup_logger_with_no_log_true(self, mock_makedirs, mock_handler_cls):
        """If no_log=True, logging is disabled"""
        app_config.config.read_dict({"logging": {"enabled": "true"}})

        app_config.setup_logger(no_log=True)

        assert app_config.is_log_enabled is False
        mock_makedirs.assert_not_called()
        mock_handler_cls.assert_not_called()

    @patch("multi_ai_cli.config.RotatingFileHandler")
    @patch("os.makedirs")
    def test_setup_logger_with_logging_disabled_in_ini(
        self, mock_makedirs, mock_handler_cls
    ):
        """If enabled=false in INI, logging is disabled"""
        app_config.config.read_dict({"logging": {"enabled": "false"}})

        app_config.setup_logger(no_log=False)

        assert app_config.is_log_enabled is False
        mock_makedirs.assert_not_called()
        mock_handler_cls.assert_not_called()

    @patch("os.getenv", return_value=None)
    def test_get_api_key_from_ini(self, mock_getenv):
        """If environment variable is absent, get it from INI"""
        app_config.config.read_dict({"API_KEYS": {"test_opt": "test_api_key"}})

        result = app_config.get_api_key("test_opt", "TEST_ENV_VAR")
        assert result == "test_api_key"

    @patch("os.getenv", return_value="env_api_key")
    def test_get_api_key_from_environment(self, mock_getenv):
        """If the environment variable is set, get it from the environment variable"""
        result = app_config.get_api_key("test_opt", "TEST_ENV_VAR")
        assert result == "env_api_key"

    @patch("os.getenv", return_value=None)
    def test_get_api_key_missing_raises_value_error(self, mock_getenv):
        """Raises ValueError if the API key is not found"""
        app_config.INI_PATH = "dummy.ini"
        with pytest.raises(ValueError, match="API key 'missing_opt' is missing"):
            app_config.get_api_key("missing_opt", "MISSING_ENV")

    @patch("multi_ai_cli.config.get_api_key", return_value="mock_api_key")
    @patch("os.makedirs")
    @patch("multi_ai_cli.config.engines", new_callable=dict)
    def test_initialize_engines(self, mock_engines, mock_makedirs, mock_get_api_key):
        """initialize_engines correctly registers engines"""
        mock_anthropic_cls = MagicMock()
        mock_genai_client_cls = MagicMock()
        mock_openai_cls = MagicMock()
        mock_gemini_engine = MagicMock()
        mock_openai_engine = MagicMock()
        mock_claude_engine = MagicMock()

        app_config.config.read_dict(
            {
                "MODELS": {
                    "gemini_model": "gemini-test",
                    "gpt_model": "gpt-test",
                    "claude_model": "claude-test",
                    "grok_model": "grok-test",
                },
                "LOCAL": {
                    "base_url": "http://localhost:11434/v1",
                    "model": "test-local",
                },
                "Paths": {
                    "work_efficient": "prompts",
                    "work_data": "work_data",
                },
            }
        )

        with (
            patch("anthropic.Anthropic", mock_anthropic_cls),
            patch("google.genai.Client", mock_genai_client_cls),
            patch("openai.OpenAI", mock_openai_cls),
            patch("multi_ai_cli.config.engines", mock_engines),
            patch("multi_ai_cli.engines.GeminiEngine", mock_gemini_engine),
            patch("multi_ai_cli.engines.OpenAIEngine", mock_openai_engine),
            patch("multi_ai_cli.engines.ClaudeEngine", mock_claude_engine),
        ):
            app_config.initialize_engines()

        assert "gemini" in mock_engines
        assert "gpt" in mock_engines
        assert "claude" in mock_engines
        assert "grok" in mock_engines
        assert "local" in mock_engines

    @patch("multi_ai_cli.config.get_api_key", side_effect=Exception("Startup fail"))
    @patch("builtins.print")
    def test_initialize_engines_error_exits(self, mock_print, mock_get_api_key):
        """On error in initialize_engines, sys.exit(1) is called"""
        with pytest.raises(SystemExit) as exc_info:
            app_config.initialize_engines()
        assert exc_info.value.code == 1
        mock_print.assert_called_once()
        assert "Startup Error" in mock_print.call_args[0][0]


if __name__ == "__main__":
    pytest.main()
