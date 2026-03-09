"""
Configuration and logging management for Multi-AI CLI.

This module handles loading the INI configuration, setting up the global
logger with rotation support, and providing utilities to retrieve
API keys from environment variables or the config file.
"""

import configparser
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

config = configparser.ConfigParser()
logger = logging.getLogger("MultiAI")
is_log_enabled = False
engines = {}

DEFAULT_LOG_MAX_BYTES = 10485760
DEFAULT_LOG_BACKUP_COUNT = 5
DEFAULT_MAX_HISTORY_TURNS = 30

INI_PATH = None


def setup_config(ini_path: str) -> None:
    """
    Loads the INI configuration file into the global ``config`` object
    and sets the global ``INI_PATH`` variable to the path of the loaded file.

    Args:
        ini_path (str): The path to the INI file to be loaded.
    """
    global config, INI_PATH
    config.read(ini_path, encoding="utf-8-sig")
    INI_PATH = ini_path


def setup_logger(no_log: bool = False) -> None:
    """
    Initializes the logging system based on INI settings and CLI flags.

    It clears any existing log handlers, creates the log directory if it
    doesn't exist, and configures a rotating file handler based on the
    INI settings. Updates the global ``logger`` and the ``is_log_enabled``
    flag accordingly.

    Args:
        no_log (bool, optional): If True, logging will be disabled.
            Defaults to False.
    """
    global logger, is_log_enabled

    should_log = config.getboolean("logging", "enabled", fallback=True) and not no_log
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        logger.handlers.clear()

    if should_log:
        log_dir = config.get("logging", "log_dir", fallback="logs")
        os.makedirs(log_dir, exist_ok=True)

        base_filename = config.get("logging", "base_filename", fallback="chat.log")
        log_path = os.path.join(log_dir, base_filename)

        max_bytes = config.getint(
            "logging", "max_bytes", fallback=DEFAULT_LOG_MAX_BYTES
        )
        backup_count = config.getint(
            "logging", "backup_count", fallback=DEFAULT_LOG_BACKUP_COUNT
        )

        log_level_str = config.get("logging", "log_level", fallback="INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(log_level)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        logger.addHandler(logging.NullHandler())

    is_log_enabled = should_log


def get_api_key(opt: str, env_var: str) -> str:
    """
    Retrieves API key from environment variable (priority) or INI file.

    Raises a ValueError if the API key is not found in both sources.

    Args:
        opt (str): The option name to fetch from the INI file.
        env_var (str): The environment variable name to check.

    Raises:
        ValueError: If the API key is not found in either the INI or
            environment variable.

    Returns:
        str: The API key for the specified option.
    """
    val = os.getenv(env_var) or config.get("API_KEYS", opt, fallback="").strip()
    if not val:
        raise ValueError(
            f"API key '{opt}' is missing in {INI_PATH} "
            f"and environment variable '{env_var}' is not set."
        )
    return val


def initialize_engines() -> None:
    """
    Initializes all AI clients and engine instances.

    It sets up client instances for various AI engines based on
    configuration details and environment variables, populates the global
    ``engines`` dictionary, and creates necessary work directories.

    Raises:
        SystemExit: If there is an error during the startup.
    """
    global engines

    try:
        from anthropic import Anthropic
        from google import genai
        from openai import OpenAI

        client_gemini = genai.Client(
            api_key=get_api_key("gemini_api_key", "GEMINI_API_KEY")
        )
        client_gpt = OpenAI(api_key=get_api_key("openai_api_key", "OPENAI_API_KEY"))
        client_claude = Anthropic(
            api_key=get_api_key("anthropic_api_key", "ANTHROPIC_API_KEY")
        )
        client_grok = OpenAI(
            api_key=get_api_key("grok_api_key", "GROK_API_KEY"),
            base_url="https://api.x.ai/v1",
        )
        local_base = config.get(
            "LOCAL", "base_url", fallback="http://localhost:11434/v1"
        )
        local_model = config.get("LOCAL", "model", fallback="qwen2.5-coder:14b")
        client_local = OpenAI(api_key="ollama", base_url=local_base)

        from .engines import ClaudeEngine, GeminiEngine, OpenAIEngine

        engines.update(
            {
                "gemini": GeminiEngine(
                    "Gemini",
                    config.get("MODELS", "gemini_model", fallback="gemini-2.5-flash"),
                    client_gemini,
                ),
                "gpt": OpenAIEngine(
                    "GPT",
                    config.get("MODELS", "gpt_model", fallback="gpt-4o-mini"),
                    client_gpt,
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
                ),
                "local": OpenAIEngine("Local", local_model, client_local),
            }
        )

        for d_opt in ["work_efficient", "work_data"]:
            d_default = "prompts" if "efficient" in d_opt else "work_data"
            os.makedirs(config.get("Paths", d_opt, fallback=d_default), exist_ok=True)

    except Exception as e:
        print(f"[!] Startup Error: {e}")
        sys.exit(1)


def get_figma_token() -> str:
    """
    Retrieves the Figma personal access token from an environment
    variable (priority) or the INI configuration file.

    Raises:
        ValueError: If the token is not found in either source.

    Returns:
        str: The Figma access token.
    """
    return get_api_key("figma_access_token", "FIGMA_ACCESS_TOKEN")
