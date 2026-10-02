"""
Configuration and logging management for Multi-AI CLI.

This module handles loading the INI configuration, setting up the global
logger with rotation support, and providing utilities to retrieve
API keys from environment variables or the config file.

After the AgentDefinition/AgentInstance separation, this module no longer
creates or holds AIEngine instances. Engine instantiation is handled by
AgentFactory and AgentSession.
"""

import configparser
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any

config = configparser.ConfigParser()
logger = logging.getLogger("MultiAI")
is_log_enabled = False

# Legacy SDK type mapping for old-format INI files.
# Populated by _load_legacy_config() and consumed by AgentSession.
legacy_sdk_map: dict[str, str] | None = None

# Flag indicating whether the loaded config is new format.
is_new_config_format: bool = False

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


def _resolve_api_key_for_agent(agent_def: Any) -> str | None:
    """
    Resolve the API key from an AgentDefinition.

    Priority:
    1. api_key_ref → retrieved from [API_KEYS] (with environment variable override)
    2. None if api_key_ref is not specified (allows auth-free endpoints)

    Args:
        agent_def: AgentDefinition instance.

    Returns:
        str | None: Resolved API key, or None if not specified.

    Raises:
        ValueError: If api_key_ref is specified but cannot be resolved.
    """
    if agent_def.api_key_ref:
        ref = agent_def.api_key_ref
        env_var = ref.upper()
        return get_api_key(ref, env_var)
    return None


def _detect_new_config_format() -> bool:
    """
    Determine whether at least one [AGENT.*] section exists in the INI.

    Returns:
        bool: True if new-format sections are detected.
    """
    for section in config.sections():
        if section.startswith("AGENT."):
            return True
    return False


def _load_registries() -> None:
    """
    Parse the new-format INI and build the agent registry and runtime settings.
    Reads [AGENT.*] sections directly and creates AgentDefinition instances.
    Validation is also performed here.

    Raises:
        ValueError: If validation fails for any agent definition.
    """
    from .registry import (
        VALID_ADAPTER_TYPES,
        AgentDefinition,
        agent_registry,
        runtime_settings,
        validate_agent_alias,
    )

    # ── [RUNTIME] ──
    if config.has_section("RUNTIME"):
        runtime_settings.max_history_turns = config.getint(
            "RUNTIME", "max_history_turns", fallback=30
        )
        runtime_settings.auto_continue_max_rounds = config.getint(
            "RUNTIME", "auto_continue_max_rounds", fallback=5
        )
        runtime_settings.auto_continue_tail_chars = config.getint(
            "RUNTIME", "auto_continue_tail_chars", fallback=1200
        )

    # ── [AGENT.*] ──
    for section in config.sections():
        if not section.startswith("AGENT."):
            continue
        agent_key = section[len("AGENT.") :].lower()

        # Alias validation
        validate_agent_alias(agent_key)

        # Required fields
        adapter = config.get(section, "adapter", fallback="").strip().lower()
        if not adapter:
            raise ValueError(f"Agent '{agent_key}': 'adapter' field is required.")
        if adapter not in VALID_ADAPTER_TYPES:
            raise ValueError(
                f"Agent '{agent_key}': invalid adapter '{adapter}'. "
                f"Valid: {VALID_ADAPTER_TYPES}"
            )

        server = config.get(section, "server", fallback="").strip()
        if not server:
            raise ValueError(f"Agent '{agent_key}': 'server' field is required.")

        engine = config.get(section, "engine", fallback="").strip()
        if not engine:
            raise ValueError(f"Agent '{agent_key}': 'engine' field is required.")

        # Optional fields
        api_key_ref = (
            config.get(section, "api_key_ref", fallback="").strip().lower() or None
        )
        role = config.get(section, "role", fallback="").strip() or None

        max_output_tokens_str = config.get(
            section, "max_output_tokens", fallback=""
        ).strip()
        max_output_tokens: int | None = None
        if max_output_tokens_str:
            try:
                max_output_tokens = int(max_output_tokens_str)
            except ValueError:
                raise ValueError(
                    f"Agent '{agent_key}': 'max_output_tokens' must be an integer, "
                    f"got '{max_output_tokens_str}'."
                )
            if max_output_tokens < 1:
                raise ValueError(
                    f"Agent '{agent_key}': 'max_output_tokens' must be >= 1, "
                    f"got {max_output_tokens}."
                )

        # Validate api_key_ref existence if specified
        if api_key_ref:
            if not config.has_option("API_KEYS", api_key_ref):
                env_var = api_key_ref.upper()
                if not os.environ.get(env_var):
                    raise ValueError(
                        f"Agent '{agent_key}': api_key_ref '{api_key_ref}' "
                        f"not found in [API_KEYS] and env '{env_var}' not set."
                    )

        agent_def = AgentDefinition(
            agent_key=agent_key,
            adapter=adapter,
            server=server,
            engine=engine,
            api_key_ref=api_key_ref,
            role=role,
            max_output_tokens=max_output_tokens,
        )
        agent_registry.register(agent_def)


def _load_legacy_config() -> None:
    """
    Migration compatibility layer that internally maps old-format INI files
    (without AGENT sections) into the new AgentDefinition structure.

    Also populates the global legacy_sdk_map for use by AgentSession.

    Mapping rules:
    - [MODELS] gemini_model → AGENT gemini (adapter=openai-compatible, via proxy)
    - [MODELS] gpt_model    → AGENT gpt
    - [MODELS] claude_model → AGENT claude
    - [MODELS] grok_model   → AGENT grok
    - [LOCAL] → AGENT local
    """
    global legacy_sdk_map

    from .registry import (
        AgentDefinition,
        agent_registry,
        runtime_settings,
    )

    logger.warning(
        "Legacy INI format detected. Consider migrating to [AGENT.*] sections."
    )

    # ── RUNTIME compatibility: runtime values inside the old [MODELS] ──
    if config.has_section("MODELS"):
        runtime_settings.max_history_turns = config.getint(
            "MODELS", "max_history_turns", fallback=30
        )
        runtime_settings.auto_continue_max_rounds = config.getint(
            "MODELS", "auto_continue_max_rounds", fallback=5
        )
        runtime_settings.auto_continue_tail_chars = config.getint(
            "MODELS", "auto_continue_tail_chars", fallback=1200
        )

    # Initialize legacy SDK mapping
    legacy_sdk_map = {}

    # ── Legacy provider mapping ──
    # Each tuple: (old MODELS key, default model, agent_key, server, api_key_ref,
    #              max_tokens_key, default_max_tokens, sdk_type)
    legacy_providers = [
        (
            "gpt_model",
            "gpt-4o-mini",
            "gpt",
            "https://api.openai.com/v1",
            "openai_api_key",
            "openai_max_tokens",
            4096,
            "openai",
        ),
        (
            "claude_model",
            "claude-3-5-sonnet-20241022",
            "claude",
            "https://api.anthropic.com/v1",
            "anthropic_api_key",
            "claude_max_tokens",
            8192,
            "anthropic",
        ),
        (
            "gemini_model",
            "gemini-2.5-flash",
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta",
            "gemini_api_key",
            "gemini_max_output_tokens",
            8192,
            "gemini",
        ),
        (
            "grok_model",
            "grok-4-latest",
            "grok",
            "https://api.x.ai/v1",
            "grok_api_key",
            "grok_max_tokens",
            4096,
            "openai",
        ),
    ]

    for (
        model_key,
        default_model,
        agent_key,
        server,
        api_key_ref,
        max_tokens_key,
        default_max_tokens,
        sdk_type,
    ) in legacy_providers:
        model_str = config.get("MODELS", model_key, fallback=default_model)
        max_tokens = config.getint(
            "MODELS", max_tokens_key, fallback=default_max_tokens
        )

        agent_def = AgentDefinition(
            agent_key=agent_key,
            adapter="openai-compatible",
            server=server,
            engine=model_str,
            api_key_ref=api_key_ref,
            max_output_tokens=max_tokens,
        )
        agent_registry.register(agent_def)
        legacy_sdk_map[agent_key] = sdk_type

    # ── [LOCAL] compatibility ──
    local_base = config.get("LOCAL", "base_url", fallback="http://localhost:11434/v1")
    local_model = config.get("LOCAL", "model", fallback="qwen2.5-coder:14b")
    local_max = config.getint("MODELS", "local_max_tokens", fallback=8192)

    agent_registry.register(
        AgentDefinition(
            agent_key="local",
            adapter="openai-compatible",
            server=local_base,
            engine=local_model,
            max_output_tokens=local_max,
        )
    )
    legacy_sdk_map["local"] = "openai"


def initialize_engines() -> None:
    """
    Main entry point: parse the INI and load all agent definitions.

    After the AgentDefinition/AgentInstance separation, this function
    only loads definitions into the registry. It no longer creates
    AIEngine instances. Engine instantiation is deferred to AgentFactory
    and AgentSession.

    Raises:
        SystemExit: If there is an error during startup.
    """
    global is_new_config_format, legacy_sdk_map

    from .registry import reset_registries

    reset_registries()
    legacy_sdk_map = None

    try:
        is_new_config_format = _detect_new_config_format()

        if is_new_config_format:
            _load_registries()
        else:
            _load_legacy_config()

        # Create working directories (preserve existing logic)
        for d_opt in ["work_efficient", "work_data"]:
            d_default = "prompts" if "efficient" in d_opt else "work_data"
            os.makedirs(config.get("Paths", d_opt, fallback=d_default), exist_ok=True)

    except Exception as e:
        print(f"[!] Startup Error: {e}")
        logger.error(f"Engine initialization failed: {e}")
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


def get_github_token() -> str:
    """
    Retrieves the GitHub access token.

    Priority:
    1. Environment variable GITHUB_TOKEN
    2. INI [GITHUB] token

    Raises:
        ValueError: If token is not found in either source.

    Returns:
        str: The GitHub access token.
    """
    val = os.environ.get("GITHUB_TOKEN", "").strip()
    if val:
        return val

    val = config.get("GITHUB", "token", fallback="").strip()
    if val:
        return val

    ini_display = INI_PATH or "multi_ai_cli.ini"
    raise ValueError(
        f"GitHub token is missing. Set GITHUB_TOKEN environment variable "
        f"or add [GITHUB] token to {ini_display}."
    )


def get_github_api_base_url() -> str:
    """
    Retrieves the GitHub API base URL.

    Priority:
    1. Environment variable GITHUB_API_BASE_URL
    2. INI [GITHUB] api_base_url
    3. Default: https://api.github.com

    Returns:
        str: The GitHub API base URL (without trailing slash).
    """
    val = os.environ.get("GITHUB_API_BASE_URL", "").strip()
    if val:
        return val.rstrip("/")

    val = config.get("GITHUB", "api_base_url", fallback="").strip()
    if val:
        return val.rstrip("/")

    return "https://api.github.com"
