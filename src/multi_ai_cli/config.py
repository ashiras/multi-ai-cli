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


def setup_config(ini_path: str):
    """Load the INI configuration file into the global config object."""
    global config, INI_PATH
    config.read(ini_path, encoding="utf-8-sig")
    INI_PATH = ini_path


def setup_logger(no_log: bool = False):
    """
    Initialize the logging system based on INI settings and CLI flags.
    Updates global logger and is_log_enabled.
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
    """Retrieve API key from environment variable (priority) or INI file."""
    val = os.getenv(env_var) or config.get("API_KEYS", opt, fallback="").strip()
    if not val:
        raise ValueError(
            f"API key '{opt}' is missing in {INI_PATH} "
            f"and environment variable '{env_var}' is not set."
        )
    return val


def initialize_engines():
    """Initialize all AI clients and engine instances."""
    global engines

    try:
        import google.generativeai as genai
        from anthropic import Anthropic
        from openai import OpenAI

        genai.configure(api_key=get_api_key("gemini_api_key", "GEMINI_API_KEY"))
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
        # 必要なら他のEngineクラスもここでインポート

        engines.update(
            {
                "gemini": GeminiEngine(
                    "Gemini",
                    config.get("MODELS", "gemini_model", fallback="gemini-2.5-flash"),
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

        # ディレクトリ作成
        for d_opt in ["work_efficient", "work_data"]:
            d_default = "prompts" if "efficient" in d_opt else "work_data"
            os.makedirs(config.get("Paths", d_opt, fallback=d_default), exist_ok=True)

    except Exception as e:
        print(f"[!] Startup Error: {e}")
        sys.exit(1)
