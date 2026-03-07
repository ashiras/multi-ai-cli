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

# Global variables (managed carefully)
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
    Load the INI configuration file into the global config object.

    Args:
        ini_path (str): The path to the INI file to be loaded.

    """
    global config, INI_PATH
    config.read(ini_path, encoding="utf-8-sig")
    INI_PATH = ini_path


def setup_logger(no_log: bool = False) -> None:
    """
    Initialize the logging system based on INI settings and CLI flags.

    This function updates the global logger and the is_log_enabled flag based on
    the contents of the INI file and provided command line arguments.

    Args:
        no_log (bool, optional): If True, logging will be disabled. Defaults to False.

    """
    global logger, is_log_enabled

    # Determine if logging should be enabled
    should_log = config.getboolean("logging", "enabled", fallback=True) and not no_log
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers if any
    if logger.handlers:
        logger.handlers.clear()

    if should_log:
        log_dir = config.get("logging", "log_dir", fallback="logs")
        os.makedirs(log_dir, exist_ok=True)

        base_filename = config.get("logging", "base_filename", fallback="chat.log")
        log_path = os.path.join(log_dir, base_filename)

        # Configure log rotation settings
        max_bytes = config.getint(
            "logging", "max_bytes", fallback=DEFAULT_LOG_MAX_BYTES
        )
        backup_count = config.getint(
            "logging", "backup_count", fallback=DEFAULT_LOG_BACKUP_COUNT
        )

        log_level_str = config.get("logging", "log_level", fallback="INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Set up a rotating file handler
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(log_level)

        # Set the formatting for log messages
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        # Add a null handler if logging is disabled
        logger.addHandler(logging.NullHandler())

    is_log_enabled = should_log


def get_api_key(opt: str, env_var: str) -> str:
    """
    Retrieve API key from environment variable (priority) or INI file.

    If the API key is not found in both sources, a ValueError is raised.

    Args:
        opt (str): The option name to fetch from the INI file.
        env_var (str): The environment variable name to check.

    Raises:
        ValueError: If the API key is not found in either the INI or environment variable.

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
    Initialize all AI clients and engine instances.

    This function sets up client instances for various AI engines based on
    configuration details and environment variables. It populates the global
    engines dictionary with engine instances.

    Raises:
        SystemExit: If there is an error during the startup.

    """
    global engines

    try:
        # Import necessary client libraries
        from anthropic import Anthropic
        from google import genai
        from openai import OpenAI

        # Configure each AI client with their respective API keys
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
        # Other Engine classes can also be imported here if needed

        # Populate the engines dictionary with engine instances
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

        # Create necessary directories for work
        for d_opt in ["work_efficient", "work_data"]:
            d_default = "prompts" if "efficient" in d_opt else "work_data"
            os.makedirs(config.get("Paths", d_opt, fallback=d_default), exist_ok=True)

    except Exception as e:
        print(f"[!] Startup Error: {e}")
        sys.exit(1)
