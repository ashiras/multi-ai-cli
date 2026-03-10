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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .engines import AIEngine

config = configparser.ConfigParser()
logger = logging.getLogger("MultiAI")
is_log_enabled = False

agent_engines: dict[str, Any] = {}

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


def _resolve_api_key(engine_def: Any) -> str:
    """
    Resolve the API key from an EngineDefinition.

    Priority:
    1. engine_def.api_key (inline specification)
    2. api_key_ref → retrieved from [API_KEYS] (with environment variable override)

    Args:
        engine_def: EngineDefinition instance.

    Returns:
        str: Resolved API key.

    Raises:
        ValueError: If no API key can be resolved.
    """
    if engine_def.api_key:
        return engine_def.api_key

    if engine_def.api_key_ref:
        ref = engine_def.api_key_ref
        # The environment variable name is the uppercase version of ref
        env_var = ref.upper()
        return get_api_key(ref, env_var)

    raise ValueError(f"Engine '{engine_def.name}' has no api_key or api_key_ref.")


def _detect_new_config_format() -> bool:
    """
    Determine whether at least one [ENGINE.*] or [AGENT.*] section exists in the INI.

    Returns:
        bool: True if new-format sections are detected.
    """
    for section in config.sections():
        if section.startswith("ENGINE.") or section.startswith("AGENT."):
            return True
    return False


def _load_registries() -> None:
    """
    Parse the new-format INI and build the three registries and runtime settings.
    Validation is also performed here.

    Raises:
        ValueError: If validation fails for any engine or agent definition.
    """
    from .registry import (
        VALID_ENGINE_TYPES,
        AgentDefinition,
        EngineDefinition,
        agent_registry,
        engine_registry,
        model_registry,
        runtime_settings,
        validate_agent_name,
        validate_namespace_engine_consistency,
    )

    # ── [MODELS] ──
    if config.has_section("MODELS"):
        for alias, model_string in config.items("MODELS"):
            model_registry.register(alias, model_string.strip())

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

    # ── [ENGINE.*] ──
    for section in config.sections():
        if not section.startswith("ENGINE."):
            continue
        engine_name = section[len("ENGINE.") :].lower()

        engine_type = config.get(section, "type", fallback="").strip().lower()
        if engine_type not in VALID_ENGINE_TYPES:
            raise ValueError(
                f"Engine '{engine_name}': invalid type '{engine_type}'. "
                f"Valid: {VALID_ENGINE_TYPES}"
            )

        api_key_ref = (
            config.get(section, "api_key_ref", fallback="").strip().lower() or None
        )
        api_key_inline = config.get(section, "api_key", fallback="").strip() or None
        model_ref = (
            config.get(section, "model_ref", fallback="").strip().lower() or None
        )
        model_inline = config.get(section, "model", fallback="").strip() or None
        base_url = config.get(section, "base_url", fallback="").strip() or None
        max_output_tokens = config.getint(section, "max_output_tokens", fallback=4096)

        # Check that model_ref exists
        if model_ref and not model_registry.has(model_ref):
            raise ValueError(
                f"Engine '{engine_name}': model_ref '{model_ref}' "
                f"not found in [MODELS]."
            )

        # Check that api_key_ref exists (within the API_KEYS section)
        if api_key_ref:
            if not config.has_option("API_KEYS", api_key_ref):
                env_var = api_key_ref.upper()
                if not os.environ.get(env_var):
                    raise ValueError(
                        f"Engine '{engine_name}': api_key_ref '{api_key_ref}' "
                        f"not found in [API_KEYS] and env '{env_var}' not set."
                    )

        engine_def = EngineDefinition(
            name=engine_name,
            type=engine_type,
            api_key_ref=api_key_ref,
            api_key=api_key_inline,
            model_ref=model_ref,
            model=model_inline,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
        )
        engine_registry.register(engine_def)

    # ── [AGENT.*] ──
    for section in config.sections():
        if not section.startswith("AGENT."):
            continue
        agent_key = section[len("AGENT.") :].lower()

        # Name validation
        namespace, role = validate_agent_name(agent_key)

        engine_name = config.get(section, "engine", fallback="").strip().lower()
        if not engine_name:
            raise ValueError(f"Agent '{agent_key}': 'engine' field is required.")
        if not engine_registry.has(engine_name):
            raise ValueError(f"Agent '{agent_key}': engine '{engine_name}' not found.")

        # Check namespace-engine family consistency
        engine_def = engine_registry.get(engine_name)
        validate_namespace_engine_consistency(agent_key, namespace, engine_def)

        agent_def = AgentDefinition(
            agent_key=agent_key,
            engine_name=engine_name,
            namespace=namespace,
            role=role,
        )
        agent_registry.register(agent_def)


def _load_legacy_config() -> None:
    """
    Migration compatibility layer that internally maps old-format INI files
    (without ENGINE/AGENT sections) into the new structure when detected.

    Mapping rules:
    - [MODELS] gemini_model → model alias "gemini_default" → ENGINE.gemini_default → AGENT.gemini
    - [MODELS] gpt_model    → model alias "gpt_default"    → ENGINE.openai_default → AGENT.gpt
    - [MODELS] claude_model → same pattern
    - [MODELS] grok_model   → same pattern
    - [LOCAL] → ENGINE.local_default → AGENT.local
    """
    from .registry import (
        AgentDefinition,
        EngineDefinition,
        agent_registry,
        engine_registry,
        model_registry,
        runtime_settings,
    )

    logger.warning(
        "Legacy INI format detected. Consider migrating to [ENGINE.*]/[AGENT.*] sections."
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

    # ── Legacy provider mapping ──
    legacy_providers = [
        # (old MODELS key, default model, alias name, engine name, type, namespace, api_key_ref)
        (
            "gemini_model",
            "gemini-2.5-flash",
            "gemini_default",
            "gemini_default",
            "gemini",
            "gemini",
            "gemini_api_key",
        ),
        (
            "gpt_model",
            "gpt-4o-mini",
            "gpt_default",
            "openai_default",
            "openai",
            "gpt",
            "openai_api_key",
        ),
        (
            "claude_model",
            "claude-3-5-sonnet-20241022",
            "claude_default",
            "claude_default",
            "anthropic",
            "claude",
            "anthropic_api_key",
        ),
        (
            "grok_model",
            "grok-4-latest",
            "grok_default",
            "grok_default",
            "grok",
            "grok",
            "grok_api_key",
        ),
    ]

    for (
        model_key,
        default_model,
        alias,
        eng_name,
        eng_type,
        namespace,
        api_key_ref,
    ) in legacy_providers:
        model_str = config.get("MODELS", model_key, fallback=default_model)
        model_registry.register(alias, model_str)

        # Old key names for max_output_tokens
        max_tokens_key_map = {
            "openai": "openai_max_tokens",
            "anthropic": "claude_max_tokens",
            "gemini": "gemini_max_output_tokens",
            "grok": "grok_max_tokens",
        }
        max_tokens = config.getint(
            "MODELS", max_tokens_key_map.get(eng_type, ""), fallback=4096
        )

        base_url = None
        if eng_type == "grok":
            base_url = "https://api.x.ai/v1"

        engine_def = EngineDefinition(
            name=eng_name,
            type=eng_type,
            api_key_ref=api_key_ref,
            model_ref=alias,
            base_url=base_url,
            max_output_tokens=max_tokens,
        )
        engine_registry.register(engine_def)

        agent_def = AgentDefinition(
            agent_key=namespace,
            engine_name=eng_name,
            namespace=namespace,
            role=None,
        )
        agent_registry.register(agent_def)

    # ── [LOCAL] compatibility ──
    local_base = config.get("LOCAL", "base_url", fallback="http://localhost:11434/v1")
    local_model = config.get("LOCAL", "model", fallback="qwen2.5-coder:14b")
    local_max = config.getint("MODELS", "local_max_tokens", fallback=8192)

    model_registry.register("local_default", local_model)
    engine_registry.register(
        EngineDefinition(
            name="local_default",
            type="local_openai",
            api_key="ollama",
            model_ref="local_default",
            base_url=local_base,
            max_output_tokens=local_max,
        )
    )
    agent_registry.register(
        AgentDefinition(
            agent_key="local",
            engine_name="local_default",
            namespace="local",
            role=None,
        )
    )


def _build_agent_engines() -> None:
    """
    Generate SDK clients from all agent definitions and
    register AIEngine instances in agent_engines.
    """
    global agent_engines

    from .engines import ClaudeEngine, GeminiEngine, OpenAIEngine
    from .registry import (
        agent_registry,
        engine_registry,
        model_registry,
        runtime_settings,
    )

    # SDK client cache (reused for identical credentials + base_url)
    _client_cache: dict[str, Any] = {}

    def _get_or_create_client(engine_def: Any) -> Any:
        """Create/cache an SDK client based on engine_def."""
        cache_key = (
            f"{engine_def.type}:"
            f"{engine_def.api_key_ref or ''}:"
            f"{engine_def.api_key or ''}:"
            f"{engine_def.base_url or ''}"
        )
        if cache_key in _client_cache:
            return _client_cache[cache_key]

        api_key = _resolve_api_key(engine_def)

        client: Any

        if engine_def.type == "gemini":
            from google import genai

            client = genai.Client(api_key=api_key)

        elif engine_def.type == "anthropic":
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)

        elif engine_def.type in ("openai", "grok", "local_openai"):
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": api_key}
            if engine_def.base_url:
                kwargs["base_url"] = engine_def.base_url
            elif engine_def.type == "grok":
                kwargs["base_url"] = "https://api.x.ai/v1"
            client = OpenAI(**kwargs)

        else:
            raise ValueError(f"Unknown engine type: {engine_def.type}")

        _client_cache[cache_key] = client
        return client

    agent_engines.clear()

    for agent_key, agent_def in agent_registry.all_agents().items():
        engine_def = engine_registry.get(agent_def.engine_name)

        # Resolve the model string
        if engine_def.model_ref:
            resolved_model = model_registry.resolve(engine_def.model_ref)
        elif engine_def.model:
            resolved_model = engine_def.model
        else:
            raise ValueError(
                f"Engine '{engine_def.name}' has neither model_ref nor model."
            )

        client = _get_or_create_client(engine_def)

        ai_engine: AIEngine

        # Create AIEngine instance — pass display_label to the name argument
        if engine_def.type == "gemini":
            ai_engine = GeminiEngine(
                name=agent_def.display_label,
                model_name=resolved_model,
                client=client,
            )
        elif engine_def.type == "anthropic":
            ai_engine = ClaudeEngine(
                name=agent_def.display_label,
                model_name=resolved_model,
                client=client,
            )
        elif engine_def.type in ("openai", "grok", "local_openai"):
            ai_engine = OpenAIEngine(
                name=agent_def.display_label,
                model_name=resolved_model,
                client=client,
            )
        else:
            raise ValueError(f"Cannot create engine for type: {engine_def.type}")

        # Apply max_output_tokens
        if hasattr(ai_engine, "max_output_tokens"):
            ai_engine.max_output_tokens = engine_def.max_output_tokens
        if hasattr(ai_engine, "max_tokens"):
            ai_engine.max_tokens = engine_def.max_output_tokens

        # Apply runtime settings
        ai_engine.max_turns = runtime_settings.max_history_turns

        agent_engines[agent_key] = ai_engine


def initialize_engines() -> None:
    """
    Main entry point: parse the INI and initialize all agent engines.
    Supports both new and old formats.

    Raises:
        SystemExit: If there is an error during startup.
    """
    global agent_engines

    from .registry import reset_registries

    reset_registries()
    agent_engines.clear()

    try:
        if _detect_new_config_format():
            _load_registries()
        else:
            _load_legacy_config()

        _build_agent_engines()

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
