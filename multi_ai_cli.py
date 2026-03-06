import argparse
import configparser
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import RotatingFileHandler
from pathlib import Path

# AI SDKs
import google.generativeai as genai
from anthropic import Anthropic
from openai import OpenAI

# Optional: load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ==================================================
# Constants & Configuration
# ==================================================
VERSION = "0.11.0"
DEFAULT_LOG_MAX_BYTES = 10485760
DEFAULT_LOG_BACKUP_COUNT = 5
DEFAULT_MAX_HISTORY_TURNS = 30

# File extension to runner mapping for @sh -r
RUNNER_MAP = {
    ".py": ["python3"],
    ".sh": ["bash"],
    ".rb": ["ruby"],
    ".js": ["node"],
    ".ts": ["npx", "ts-node"],
    ".pl": ["perl"],
    ".lua": ["lua"],
    ".r": ["Rscript"],
    ".R": ["Rscript"],
}

# ==================================================
# Thread-Safe Console Lock
# ==================================================
_console_lock = threading.Lock()

# --------------------------------------------------
# 1. Argparse & Config Management
# --------------------------------------------------
parser = argparse.ArgumentParser(
    description=f"Multi-AI CLI v{VERSION} (Raw-by-Default Write Mode)"
)
parser.add_argument(
    "--no-log",
    action="store_true",
    help="Disable logging for this session (Stealth Mode)",
)
parser.add_argument("--version", action="version", version=f"Multi-AI CLI v{VERSION}")
args = parser.parse_args()

INI_FILE = "multi_ai_cli.ini"

if not os.path.exists(INI_FILE):
    print(f"[!] Error: '{INI_FILE}' not found in the current directory.")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(INI_FILE, encoding="utf-8-sig")


# --------------------------------------------------
# 2. Logging & Utility
# --------------------------------------------------
class AIError(Exception):
    """Custom exception for AI service and processing errors."""

    pass


def setup_logger():
    """
    Initializes the logging system based on INI settings and CLI flags.
    Returns a tuple of (logger_instance, is_enabled_boolean).
    """
    should_log = (
        config.getboolean("logging", "enabled", fallback=True) and not args.no_log
    )
    _logger = logging.getLogger("MultiAI")
    _logger.setLevel(logging.DEBUG)

    if _logger.handlers:
        _logger.handlers.clear()

    if should_log:
        log_dir = config.get("logging", "log_dir", fallback="logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            print(f"[!] Logging Error: Could not create log directory '{log_dir}': {e}")
            sys.exit(1)

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
        _logger.addHandler(handler)
    else:
        _logger.addHandler(logging.NullHandler())
    return _logger, should_log


logger, is_log_enabled = setup_logger()


def secure_resolve_path(filename, category="data"):
    """
    Resolves a file path while preventing directory traversal attacks.
    Ensures the target file stays within the configured base directory.
    """
    section_map = {"efficient": "work_efficient", "data": "work_data"}
    default_map = {"efficient": "prompts", "data": "work_data"}

    config_key = section_map.get(category, "work_data")
    default_dir = default_map.get(category, "work_data")

    base_dir = config.get("Paths", config_key, fallback=default_dir)

    abs_base = os.path.abspath(base_dir)
    target_path = os.path.abspath(os.path.join(abs_base, filename))

    if not os.path.commonpath([abs_base, target_path]) == abs_base:
        raise PermissionError(
            f"Security Alert: Directory traversal blocked for '{filename}'"
        )

    return target_path


# --------------------------------------------------
# 2.5 Editor Integration
# --------------------------------------------------
def open_editor_for_prompt():
    """
    Opens the user's preferred editor ($EDITOR or vi) with a temporary file.
    Returns the content written by the user, or None if cancelled/empty.

    Flow:
      1. Create a temporary file with a helpful comment header
      2. Launch $EDITOR (fallback: vi)
      3. Read back the file contents (stripping comment lines)
      4. Clean up the temp file
      5. Return the prompt text or None
    """
    editor_raw = os.environ.get("EDITOR", "vi").strip() or "vi"
    editor_cmd = shlex.split(editor_raw)

    MARKER = "# ==================== END HEADER ===================="
    header = (
        "# ====================================================\n"
        "# Multi-AI CLI - Editor Mode\n"
        "# ====================================================\n"
        "# Write your prompt below. Lines starting with '#' are\n"
        "# ignored (treated as comments).\n"
        "#\n"
        "# Save and quit the editor to send your prompt.\n"
        "# Leave empty (or only comments) to cancel.\n"
        f"{MARKER}\n"
        "\n"
    )

    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="ai_prompt_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None
            f.write(header)

        result = subprocess.run(editor_cmd + [tmp_path])

        if result.returncode != 0:
            logger.warning(f"Editor exited with non-zero status: {result.returncode}")
            print(f"[!] Editor exited with error (code {result.returncode}).")
            return None

        with open(tmp_path, encoding="utf-8") as f:
            raw_content = f.read()

        lines = raw_content.splitlines()

        if MARKER in lines:
            idx = lines.index(MARKER) + 1
            content = "\n".join(lines[idx:]).lstrip("\n").strip()
        else:
            content_lines = []
            started = False
            for line in lines:
                if not started:
                    if line.lstrip().startswith("#") or not line.strip():
                        continue
                    started = True
                content_lines.append(line)
            content = "\n".join(content_lines).strip()
        if not content:
            print("[*] Editor prompt is empty. Request cancelled.")
            logger.info("[*] Editor mode: empty prompt, cancelled.")
            return None

        preview_lines = content.splitlines()
        if len(preview_lines) <= 5:
            preview = content
        else:
            preview = (
                "\n".join(preview_lines[:5])
                + f"\n... ({len(preview_lines)} lines total)"
            )

        print(
            f"[*] Editor prompt captured ({len(content)} chars, {len(preview_lines)} lines):"
        )
        print("--- Preview ---")
        print(preview)
        print("--- End Preview ---")

        return content

    except FileNotFoundError:
        print(f"[!] Editor '{editor_cmd[0]}' not found. Set $EDITOR to your preferred editor.")
        print("    Example: export EDITOR=nano")
        logger.error(f"Editor not found: {editor_cmd[0]}")
        return None
    except Exception as e:
        print(f"[!] Editor error: {e}")
        logger.error(f"Editor error: {e}")
        return None
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning(f"Could not remove temp file {tmp_path}: {e}")


# --------------------------------------------------
# 3. AI Engine Abstraction
# --------------------------------------------------
class AIEngine(ABC):
    """Base class for all AI model implementations."""

    def __init__(self, name, model_name):
        self.name = name
        self.model_name = model_name
        self.system_prompt = ""
        self.history = []
        self.max_turns = config.getint(
            "MODELS", "max_history_turns", fallback=DEFAULT_MAX_HISTORY_TURNS
        )

    def _trim_history(self):
        """Keeps the conversation history within the turn limit."""
        max_msgs = self.max_turns * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

    @abstractmethod
    def call(self, prompt):
        """Sends a prompt to the AI and returns the response string."""
        pass

    def scrub(self):
        """Clears the short-term memory (history) but keeps the persona."""
        self.history = []
        logger.info(f"[*] System: {self.name} history cleared.")

    def load_persona(self, prompt_text, filename):
        """Sets the system prompt and resets the history."""
        self.system_prompt = prompt_text
        self.history = []
        self._after_persona_loaded()
        logger.info(f"[*] System: {self.name} persona loaded from '{filename}'.")

    def _after_persona_loaded(self):
        pass


# ==================================================
# Auto-continue helpers (shared)
# ==================================================
def _get_cfg_int(section: str, key: str, fallback: int) -> int:
    """Read an int config value safely with a fallback."""
    try:
        return config.getint(section, key, fallback=fallback)
    except Exception:
        return fallback


def _make_continue_prompt(tail: str) -> str:
    """
    Build a continuation instruction anchored by the tail of the previous output.
    Using a fenced block avoids quote/escape issues and improves alignment.
    """
    return (
        "The output was truncated due to an output limit.\n"
        "Continue EXACTLY from where you stopped.\n"
        "Rules:\n"
        "- Do NOT repeat any earlier content.\n"
        "- Do NOT add greetings, headings, apologies, or explanations.\n"
        "- Output ONLY the continuation.\n\n"
        "Here is the tail of your last output for alignment:\n"
        "```tail\n"
        f"{tail}\n"
        "```\n"
    )


def _tail_of(text: str, n: int) -> str:
    """Return the last n characters of text (or the whole text if shorter)."""
    if not text:
        return ""
    return text[-n:] if len(text) > n else text


# ==================================================
# Engines
# ==================================================
class GeminiEngine(AIEngine):
    """Google Gemini specific implementation."""

    def __init__(self, name, model_name):
        super().__init__(name, model_name)
        self.max_output_tokens = _get_cfg_int(
            "MODELS", "gemini_max_output_tokens", fallback=8192
        )
        self.rebuild_model()

    def rebuild_model(self):
        instr = self.system_prompt if self.system_prompt else None
        self.model = genai.GenerativeModel(self.model_name, system_instruction=instr)

    def scrub(self):
        super().scrub()

    def _after_persona_loaded(self):
        self.rebuild_model()

    def _to_gemini_part(self, content: str):
        """Convert plain text to a Gemini 'parts' entry with better SDK compatibility."""
        return [{"text": content}]

    def _hit_output_limit(self, response, answer_chunk: str) -> bool:
        """Detect whether the response was truncated by output limits (with fallbacks)."""
        finish_reason = None
        try:
            finish_reason = response.candidates[0].finish_reason
        except Exception:
            finish_reason = None

        finish_name = getattr(finish_reason, "name", "")
        if (finish_name == "MAX_TOKENS") or (finish_reason == 2):
            return True

        # Fallback heuristics when finish_reason is unavailable/unstable.
        if answer_chunk.count("```") % 2 == 1:
            return True
        if answer_chunk.rstrip().endswith((",", ":", "(", "[", "{")):
            return True

        return False

    def call(self, prompt):
        self._trim_history()

        # Build stateless request history for this call.
        current_history = []
        for msg in self.history:
            role = "user" if msg["role"] == "user" else "model"
            current_history.append(
                {"role": role, "parts": self._to_gemini_part(msg["content"])}
            )

        current_history.append({"role": "user", "parts": self._to_gemini_part(prompt)})

        full_answer = ""

        max_rounds = _get_cfg_int("MODELS", "auto_continue_max_rounds", fallback=5)
        tail_chars = _get_cfg_int("MODELS", "auto_continue_tail_chars", fallback=1200)

        gen_config = genai.types.GenerationConfig(
            max_output_tokens=self.max_output_tokens
        )

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self.model.generate_content(
                    current_history, generation_config=gen_config
                )
                answer_chunk = getattr(response, "text", "") or ""
                full_answer += answer_chunk

                logger.debug(f"[DEBUG] Gemini chunk received. round: {round_idx}")

                if self._hit_output_limit(response, answer_chunk):
                    with _console_lock:
                        print(
                            f"[*] Gemini is continuing (hit max_output_tokens, round {round_idx}/{max_rounds})...",
                            end="\r",
                            flush=True,
                        )

                    current_history.append(
                        {"role": "model", "parts": self._to_gemini_part(answer_chunk)}
                    )

                    eff_tail_chars = max(
                        300, int(tail_chars * (0.8 ** (round_idx - 1)))
                    )
                    tail = _tail_of(full_answer, eff_tail_chars)

                    continue_prompt = _make_continue_prompt(tail)
                    current_history.append(
                        {"role": "user", "parts": self._to_gemini_part(continue_prompt)}
                    )
                    continue

                break

            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                raise AIError(f"Gemini error: {e}")

        else:
            logger.warning(
                "[!] Gemini hit max auto-continue rounds. Response might be truncated."
            )
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


class OpenAIEngine(AIEngine):
    """OpenAI-compatible implementation (GPT, Grok)."""

    def __init__(self, name, model_name, client, max_tokens_key="openai_max_tokens"):
        super().__init__(name, model_name)
        self.client = client
        self.max_tokens = _get_cfg_int("MODELS", max_tokens_key, fallback=4096)

    def _create_completion(self, messages):
        """Call API with max_tokens, fallback to max_completion_tokens if needed."""
        try:
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
            )
        except TypeError:
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=self.max_tokens,
            )

    def call(self, prompt):
        self._trim_history()

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        full_answer = ""
        max_rounds = _get_cfg_int("MODELS", "auto_continue_max_rounds", fallback=5)
        tail_chars = _get_cfg_int("MODELS", "auto_continue_tail_chars", fallback=1200)

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self._create_completion(messages)

                choice = response.choices[0]
                answer_chunk = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", None)

                full_answer += answer_chunk
                logger.debug(
                    f"[DEBUG] {self.name} chunk received. finish_reason: {finish_reason}, round: {round_idx}"
                )

                if finish_reason == "length":
                    with _console_lock:
                        print(
                            f"[*] {self.name} is continuing (hit length limit, round {round_idx}/{max_rounds})...",
                            end="\r",
                            flush=True,
                        )

                    messages.append({"role": "assistant", "content": answer_chunk})

                    tail = _tail_of(full_answer, tail_chars)
                    continue_prompt = _make_continue_prompt(tail)
                    messages.append({"role": "user", "content": continue_prompt})
                    continue

                break

            except Exception as e:
                logger.error(f"{self.name} API Error: {e}")
                raise AIError(f"{self.name} error: {e}")

        else:
            logger.warning(
                f"[!] {self.name} hit max auto-continue rounds. Response might be truncated."
            )
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


class ClaudeEngine(AIEngine):
    """Anthropic Claude specific implementation."""

    def __init__(self, name, model_name, client):
        super().__init__(name, model_name)
        self.client = client
        self.max_tokens = _get_cfg_int("MODELS", "claude_max_tokens", fallback=8192)

    def call(self, prompt):
        self._trim_history()

        messages = list(self.history) + [{"role": "user", "content": prompt}]
        full_answer = ""

        max_rounds = _get_cfg_int("MODELS", "auto_continue_max_rounds", fallback=5)
        tail_chars = _get_cfg_int("MODELS", "auto_continue_tail_chars", fallback=1200)

        for round_idx in range(1, max_rounds + 1):
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt if self.system_prompt else "",
                    messages=messages,
                )

                answer_chunk = ""
                if getattr(response, "content", None):
                    answer_chunk = getattr(response.content[0], "text", "") or ""

                stop_reason = getattr(response, "stop_reason", None)

                full_answer += answer_chunk
                logger.debug(
                    f"[DEBUG] Claude chunk received. stop_reason: {stop_reason}, round: {round_idx}"
                )

                if stop_reason == "max_tokens":
                    with _console_lock:
                        print(
                            f"[*] Claude is continuing (hit max_tokens, round {round_idx}/{max_rounds})...",
                            end="\r",
                            flush=True,
                        )

                    messages.append({"role": "assistant", "content": answer_chunk})

                    tail = _tail_of(full_answer, tail_chars)
                    continue_prompt = _make_continue_prompt(tail)
                    messages.append({"role": "user", "content": continue_prompt})
                    continue

                break

            except Exception as e:
                logger.error(f"Claude API Error: {e}")
                raise AIError(f"Claude error: {e}")

        else:
            logger.warning(
                "[!] Claude hit max auto-continue rounds. Response might be truncated."
            )
            full_answer += "\n\n[TRUNCATED: auto-continue limit reached]\n"

        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": full_answer})
        self._trim_history()

        return full_answer


# --------------------------------------------------
# 4. Global Initialization
# --------------------------------------------------
try:

    def get_api_key(opt, env_var):
        """Fetches API key from env var or INI file. Env var takes priority."""
        val = os.getenv(env_var) or config.get("API_KEYS", opt, fallback="").strip()
        if not val:
            raise ValueError(
                f"API key '{opt}' is missing in {INI_FILE} "
                f"and environment variable '{env_var}' is not set."
            )
        return val

    genai.configure(api_key=get_api_key("gemini_api_key", "GEMINI_API_KEY"))
    client_gpt = OpenAI(api_key=get_api_key("openai_api_key", "OPENAI_API_KEY"))
    client_claude = Anthropic(
        api_key=get_api_key("anthropic_api_key", "ANTHROPIC_API_KEY")
    )
    client_grok = OpenAI(
        api_key=get_api_key("grok_api_key", "GROK_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    local_base = config.get("LOCAL", "base_url", fallback="http://localhost:11434/v1")
    local_model = config.get("LOCAL", "model", fallback="qwen2.5-coder:14b")
    local_key = config.get("LOCAL", "api_key", fallback="ollama").strip() or "ollama"
    client_local = OpenAI(
        api_key=local_key,
        base_url=local_base,
    )

    engines = {
        "gemini": GeminiEngine(
            "Gemini",
            config.get("MODELS", "gemini_model", fallback="gemini-2.5-flash"),
        ),
        "gpt": OpenAIEngine(
            "GPT",
            config.get("MODELS", "gpt_model", fallback="gpt-4o-mini"),
            client_gpt,
            max_tokens_key="openai_max_tokens",
        ),
        "claude": ClaudeEngine(
            "Claude",
            config.get("MODELS", "claude_model", fallback="claude-3-5-sonnet-20241022"),
            client_claude,
        ),
        "grok": OpenAIEngine(
            "Grok",
            config.get("MODELS", "grok_model", fallback="grok-4-latest"),
            client_grok,
            max_tokens_key="grok_max_tokens",
        ),
        "local": OpenAIEngine(
            "Local",
            local_model,
            client_local,
            max_tokens_key="local_max_tokens"
        ),
    }

    for d_opt in ["work_efficient", "work_data"]:
        d_default = "prompts" if "efficient" in d_opt else "work_data"
        d_path = config.get("Paths", d_opt, fallback=d_default)
        os.makedirs(d_path, exist_ok=True)

except Exception as e:
    print(f"[!] Startup Error: {e}")
    sys.exit(1)

# --------------------------------------------------
# 5. CLI Input Parsing & Prompt Assembly
# --------------------------------------------------

# ---- Write-mode constants ----
WRITE_MODE_RAW = "raw"
WRITE_MODE_CODE = "code"


class ParsedInput:
    """
    Data class holding the result of CLI input parsing.

    Attributes:
        a1          : Context / title text (bare words, no flags)
        message     : Text provided via -m flag
        read_files  : List of filenames provided via repeated -r flags
        write_file  : Single output filename provided via -w / -w:code / -w:raw
        write_mode  : One of WRITE_MODE_RAW or WRITE_MODE_CODE
        use_editor  : Whether -e / --edit was specified
    """

    def __init__(self):
        self.a1 = ""
        self.message = ""
        self.read_files = []
        self.write_file = None
        self.write_mode = WRITE_MODE_RAW
        self.use_editor = False


def _parse_write_flag(token):
    """
    Parse a write flag token and return (modifier, is_write_flag).

    Supported forms:
      -w          -> (WRITE_MODE_RAW, True)
      --write     -> (WRITE_MODE_RAW, True)
      -w:raw      -> (WRITE_MODE_RAW, True)
      --write:raw -> (WRITE_MODE_RAW, True)
      -w:code     -> (WRITE_MODE_CODE, True)
      --write:code-> (WRITE_MODE_CODE, True)
      anything else -> (None, False)
    """
    pattern = r"^(?:-w|--write)(?::(\w+))?$"
    m = re.match(pattern, token)
    if not m:
        return None, False

    modifier = m.group(1)

    if modifier is None:
        return WRITE_MODE_RAW, True
    elif modifier == "raw":
        return WRITE_MODE_RAW, True
    elif modifier == "code":
        return WRITE_MODE_CODE, True
    else:
        print(f"[!] Unknown write modifier ':{modifier}'. Valid: :raw, :code")
        return None, False


def parse_cli_input(parts):
    """
    Parse the token list produced by splitting the user's input line.

    Returns
    -------
    ParsedInput | None
        None signals a parsing error that was already printed to the user.
    """
    parsed = ParsedInput()
    indices_to_skip = {0}

    i = 1
    while i < len(parts):
        token = parts[i]

        # --- -r / --read (repeatable) ---
        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            parsed.read_files.append(parts[i + 1])
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # --- -w / -w:code / -w:raw / --write / --write:code / --write:raw ---
        write_mode, is_write = _parse_write_flag(token)
        if is_write:
            if write_mode is None:
                return None
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a filename argument.")
                return None
            if parsed.write_file is not None:
                print(
                    f"[!] Warning: write flag specified more than once. "
                    f"Overwriting '{parsed.write_file}' with '{parts[i + 1]}'."
                )
            parsed.write_file = parts[i + 1]
            parsed.write_mode = write_mode
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # --- -m / --message (repeatable, single-token value each time) ---
        if token in ("-m", "--message"):
            if i + 1 >= len(parts):
                print(f"[!] Flag '{token}' requires a text argument.")
                return None
            msg_val = parts[i + 1]
            if parsed.message:
                parsed.message += " " + msg_val
            else:
                parsed.message = msg_val
            indices_to_skip.update({i, i + 1})
            i += 2
            continue

        # --- -e / --edit (boolean) ---
        if token in ("-e", "--edit"):
            parsed.use_editor = True
            indices_to_skip.add(i)
            i += 1
            continue

        # --- ordinary token (contributes to a1) ---
        i += 1

    # Build a1 from remaining tokens
    a1_tokens = [parts[j] for j in range(len(parts)) if j not in indices_to_skip]
    parsed.a1 = " ".join(a1_tokens)

    return parsed


def build_ai_prompt(parsed, editor_content=None):
    """
    Assemble the final prompt string sent to the AI engine.

    Construction priority (fixed order):
      1. a1  -- Context / title
      2. a2  -- Message (-m)
      3. e   -- Editor content
      4. Files -- Contents of files supplied via -r
    """
    sections = []

    if parsed.a1.strip():
        sections.append(parsed.a1.strip())

    if parsed.message.strip():
        sections.append(parsed.message.strip())

    if editor_content and editor_content.strip():
        sections.append(editor_content.strip())

    if parsed.read_files:
        file_sections = []
        for filename in parsed.read_files:
            try:
                filepath = secure_resolve_path(filename, "data")
                with open(filepath, encoding="utf-8") as f:
                    file_content = f.read()
                file_sections.append(
                    f"--- [File: {filename}] ---\n"
                    f"{file_content}\n"
                    f"--- [End of File: {filename}] ---"
                )
            except Exception as e:
                raise AIError(f"Error reading input file '{filename}': {e}")

        if file_sections:
            sections.append("\n\n".join(file_sections))

    return "\n\n".join(sections)


# --------------------------------------------------
# 5.5 Main Loop Helpers & UI (Thread-Safe)
# --------------------------------------------------
def safe_print(*args_print, **kwargs):
    """Thread-safe wrapper around print using the global console lock."""
    with _console_lock:
        print(*args_print, **kwargs)


def print_welcome_banner():
    """Displays the startup banner with model info and available commands."""
    print("==================================================")
    print(f"  Multi-AI CLI v{VERSION} (Raw-by-Default Write Mode)")
    for name, eng in engines.items():
        print(f"  {eng.name:<6}: {eng.model_name}")
    print("==================================================")
    log_status = (
        "Disabled (Stealth)"
        if not is_log_enabled
        else "Enabled (tail -f logs/chat.log)"
    )
    print(f"[*] Logging: {log_status}")
    print("[*] Commands: @model, @efficient, @scrub, @sequence, @sh, exit")
    print("[*] Editor:   @model -e | --edit  (uses $EDITOR or vi)")
    print("[*] Sequence: @sequence -e  (multi-step pipeline via editor)")
    print("[*]           Use '->' to chain steps in editor mode")
    print("[*]           Use '[ cmd1 || cmd2 ]' for parallel execution")
    print('[*] Shell:    @sh "command"  |  @sh -r script.py  |  @sh "cmd" -w out.json')
    print("[*]           @sh --shell \"echo $HOME | grep user\"  (pipes/env expansion)")
    print("[*] Write:    -w <file>       (save full response -- raw, default)")
    print("[*]           -w:code <file>  (extract code blocks only)")
    print("[*]           -w:raw <file>   (explicit raw, same as -w)")
    print('[*] Flags:    -r <file> (read, repeatable)  -m "<msg>" (message)')
    print()


def clear_thinking_line():
    """Clears the 'thinking' status line in the terminal."""
    with _console_lock:
        cols = shutil.get_terminal_size(fallback=(80, 20)).columns
        print(" " * (cols - 1), end="\r", flush=True)


def extract_code_block(text):
    """
    Extracts all fenced code blocks from the given text and concatenates them.

    Used by -w:code mode to strip explanatory prose and return only code.
    If no fenced code blocks are found, returns the original text as a fallback.
    """
    if "```" not in text:
        return text

    lines = text.splitlines()
    extracted_blocks = []
    current_block = []
    in_block = False

    for line in lines:
        if line.startswith("```"):
            if not in_block:
                in_block = True
            else:
                if line.strip() == "```":
                    in_block = False
                    extracted_blocks.append("\n".join(current_block))
                    current_block = []
                else:
                    current_block.append(line)
        else:
            if in_block:
                current_block.append(line)

    if in_block and current_block:
        extracted_blocks.append("\n".join(current_block))

    if extracted_blocks:
        return "\n\n".join(extracted_blocks)

    return text


def handle_scrub(parts):
    """Handles the @scrub / @flush command."""
    target = parts[1].lower() if len(parts) > 1 else "all"
    valid_targets = set(engines.keys()) | {"all"}
    if target not in valid_targets:
        print(f"[!] Invalid target '{target}'. Valid: {', '.join(valid_targets)}")
        return

    for name, engine in engines.items():
        if target in ["all", name]:
            engine.scrub()
            print(f"[*] {engine.name} memory scrubbed.")


def handle_efficient(parts):
    """Handles the @efficient command for loading persona files."""
    if len(parts) < 2:
        print("[!] Usage: @efficient [target/all] <filename.txt>")
        return

    if parts[1].lower() in (list(engines.keys()) + ["all"]):
        target = parts[1].lower()
        filename = parts[2] if len(parts) > 2 else None
    else:
        target = "all"
        filename = parts[1]

    if not filename:
        print("[!] Error: Persona filename is required.")
        return

    try:
        filepath = secure_resolve_path(filename, "efficient")
        with open(filepath, encoding="utf-8") as f:
            content = f.read().strip()
        for name, engine in engines.items():
            if target in ["all", name]:
                engine.load_persona(content, filename)
                print(f"[*] {engine.name} persona loaded: '{filename}'.")
    except Exception as e:
        print(f"[!] Persona loading failed: {e}")


# --------------------------------------------------
# 5.6 @sh Command Handler (Shell Orchestration)
# --------------------------------------------------
class ParsedShInput:
    """
    Data class holding the result of @sh input parsing.

    Attributes:
        command     : Raw command string for direct execution (quoted argument)
        run_file    : Filename to execute via auto-detected runner (-r)
        write_file  : Output filename for capturing execution artifacts (-w)
        use_shell   : Whether --shell flag was specified (enables shell=True)
    """

    def __init__(self):
        self.command = None
        self.run_file = None
        self.write_file = None
        self.use_shell = False


def _parse_sh_input(parts):
    """
    Parse @sh command tokens into a structured ParsedShInput.

    Syntax: @sh ["command"] [-r file] [-w output_file] [--shell]

    Rules:
      - parts[0] is '@sh' and is skipped.
      - -r <file>: Specifies a file from data/ to execute with an auto-detected runner.
      - -w <file>: Specifies the output capture file. .json -> structured JSON,
                    otherwise -> Markdown-like text.
      - --shell:   Enables shell=True for pipes, env expansion, etc.
      - Bare (unflagged) tokens are joined as the raw command string.

    Returns
    -------
    ParsedShInput | None
        None signals a parsing error (already printed to user).
    """
    parsed = ParsedShInput()
    bare_tokens = []

    i = 1  # Skip '@sh'
    while i < len(parts):
        token = parts[i]

        if token in ("-r", "--read"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None
            if parsed.run_file is not None:
                print(f"[!] @sh: -r specified more than once. Using '{parts[i + 1]}'.")
            parsed.run_file = parts[i + 1]
            i += 2
            continue

        if token in ("-w", "--write"):
            if i + 1 >= len(parts):
                print(f"[!] @sh: Flag '{token}' requires a filename argument.")
                return None
            if parsed.write_file is not None:
                print(f"[!] @sh: -w specified more than once. Using '{parts[i + 1]}'.")
            parsed.write_file = parts[i + 1]
            i += 2
            continue

        if token == "--shell":
            parsed.use_shell = True
            i += 1
            continue

        # Bare token -> part of the command string
        bare_tokens.append(token)
        i += 1

    if bare_tokens:
        parsed.command = " ".join(bare_tokens)

    return parsed


def _resolve_runner(filename):
    """
    Determine the appropriate runner command for a given filename based on extension.

    Returns
    -------
    list[str] | None
        The runner prefix as a list (e.g., ['python3']), or None if no mapping exists.
    """
    ext = Path(filename).suffix.lower()
    # Handle case-sensitive .R extension explicitly
    if Path(filename).suffix == ".R":
        ext = ".R"
    return RUNNER_MAP.get(ext)


def _build_sh_command(parsed):
    """
    Build the final command list (or string for shell mode) from parsed @sh input.

    Resolves -r files from the data/ blackboard directory and maps them to
    the appropriate runner. For direct commands, uses shlex.split() for safe
    parsing (unless --shell is specified).

    Returns
    -------
    tuple[list[str] | str, bool] | None
        (cmd, use_shell) -- cmd is a list for non-shell mode or a string for
        shell mode. Returns None on error (already printed).
    """
    if parsed.run_file and parsed.command:
        print("[!] @sh: Cannot use both -r <file> and a direct command simultaneously.")
        return None

    if not parsed.run_file and not parsed.command:
        print("[!] @sh: No command or file specified.")
        print('    Usage: @sh "command" | @sh -r script.py [-w output] [--shell]')
        return None

    if parsed.run_file:
        # Resolve the file from the data/ blackboard
        try:
            filepath = secure_resolve_path(parsed.run_file, "data")
        except PermissionError as e:
            print(f"[!] @sh: {e}")
            return None

        if not os.path.isfile(filepath):
            print(f"[!] @sh: File not found: '{parsed.run_file}' (resolved: {filepath})")
            return None

        runner = _resolve_runner(parsed.run_file)
        if runner is None:
            ext = Path(parsed.run_file).suffix
            print(f"[!] @sh: No runner mapped for extension '{ext}'.")
            print(f"    Supported: {', '.join(sorted(RUNNER_MAP.keys()))}")
            return None

        cmd = runner + [filepath]
        return cmd, parsed.use_shell

    # Direct command execution
    if parsed.use_shell:
        # Pass raw string to shell for pipes, env expansion, etc.
        return parsed.command, True

    # Safe parsing via shlex.split()
    try:
        cmd = shlex.split(parsed.command)
    except ValueError as e:
        print(f"[!] @sh: Command parse error (mismatched quotes?): {e}")
        return None

    if not cmd:
        print("[!] @sh: Empty command after parsing.")
        return None

    return cmd, False


def _format_artifact_text(cmd_display, exit_code, stdout, stderr, duration_ms):
    """
    Format execution results as a human-readable Markdown-like text artifact.
    """
    status = "SUCCESS" if exit_code == 0 else "FAILURE"
    lines = [
        "# Shell Execution Artifact",
        "",
        f"- **Command:** `{cmd_display}`",
        f"- **Status:** {status}",
        f"- **Exit Code:** {exit_code}",
        f"- **Duration:** {duration_ms:.1f}ms",
        "",
    ]

    if stdout.strip():
        lines.extend([
            "## stdout",
            "```",
            stdout.rstrip(),
            "```",
            "",
        ])
    else:
        lines.append("## stdout\n_(empty)_\n")

    if stderr.strip():
        lines.extend([
            "## stderr",
            "```",
            stderr.rstrip(),
            "```",
            "",
        ])
    else:
        lines.append("## stderr\n_(empty)_\n")

    return "\n".join(lines)


def _format_artifact_json(cmd_display, exit_code, stdout, stderr, duration_ms):
    """
    Format execution results as a structured JSON artifact.
    """
    artifact = {
        "command": cmd_display,
        "status": "success" if exit_code == 0 else "failure",
        "exit_code": exit_code,
        "duration_ms": round(duration_ms, 1),
        "stdout": stdout,
        "stderr": stderr,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    return json.dumps(artifact, indent=2, ensure_ascii=False)


def handle_sh(parts):
    """
    Handles the @sh command: local shell orchestration.

    Syntax: @sh ["command"] [-r file] [-w output_file] [--shell]

    Modes:
      - Direct execution: @sh "ls -la" or @sh ls -la
      - Run file:         @sh -r script.py
      - Output capture:   @sh "command" -w result.json  (or .txt/.md)
      - Shell mode:       @sh --shell "echo $HOME | wc -c"

    Security:
      - Uses shlex.split() by default (no shell injection).
      - shell=True only when --shell is explicitly passed.
      - Inherits environment variables from the parent process.

    Artifact formalization:
      - Every execution yields: status, exit_code, stdout, stderr, duration.
      - -w with .json extension -> structured JSON artifact.
      - -w with other extensions -> readable Markdown-like text artifact.
    """
    # Parse the @sh-specific arguments
    parsed = _parse_sh_input(parts)
    if parsed is None:
        return False

    # Build the command to execute
    build_result = _build_sh_command(parsed)
    if build_result is None:
        return False

    cmd, use_shell = build_result

    # Build a display string for logging and output
    cmd_display = shlex.join(cmd) if isinstance(cmd, list) else cmd

    logger.info(f"@sh: Executing '{cmd_display}' (shell={use_shell})")
    print(f"[*] @sh: Executing: {cmd_display}")
    if use_shell:
        print("[*] @sh: --shell mode enabled (shell=True)")

    # Execute via subprocess.run()
    start_time = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            shell=use_shell,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute safety timeout
        )
    except FileNotFoundError as e:
        print(f"[!] @sh: Command not found: {e}")
        logger.error(f"@sh: Command not found: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("[!] @sh: Command timed out (300s limit).")
        logger.error(f"@sh: Timeout for '{cmd_display}'")
        return False
    except PermissionError as e:
        print(f"[!] @sh: Permission denied: {e}")
        logger.error(f"@sh: Permission denied: {e}")
        return False
    except Exception as e:
        print(f"[!] @sh: Execution error: {e}")
        logger.error(f"@sh: Execution error: {e}")
        return False

    end_time = time.monotonic()
    duration_ms = (end_time - start_time) * 1000

    exit_code = result.returncode
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    # Determine status label
    status_icon = "✓" if exit_code == 0 else "✗"
    status_label = "SUCCESS" if exit_code == 0 else "FAILURE"

    logger.info(
        f"@sh: Completed '{cmd_display}' -> exit_code={exit_code}, "
        f"duration={duration_ms:.1f}ms, stdout={len(stdout)}chars, stderr={len(stderr)}chars"
    )

    # Display results to console
    print(f"[{status_icon}] @sh: {status_label} (exit code: {exit_code}, {duration_ms:.1f}ms)")

    if stdout.strip():
        display_stdout = stdout.rstrip()
        max_console_lines = 50
        stdout_lines = display_stdout.splitlines()
        if len(stdout_lines) > max_console_lines:
            truncated = "\n".join(stdout_lines[:max_console_lines])
            print(f"--- stdout ({len(stdout_lines)} lines, showing first {max_console_lines}) ---")
            print(truncated)
            print(f"--- (truncated, {len(stdout_lines) - max_console_lines} more lines) ---")
        else:
            print("--- stdout ---")
            print(display_stdout)
            print("--- end stdout ---")

    if stderr.strip():
        display_stderr = stderr.rstrip()
        stderr_lines = display_stderr.splitlines()
        max_stderr_lines = 30
        if len(stderr_lines) > max_stderr_lines:
            truncated = "\n".join(stderr_lines[:max_stderr_lines])
            print(f"--- stderr ({len(stderr_lines)} lines, showing first {max_stderr_lines}) ---")
            print(truncated)
            print(f"--- (truncated, {len(stderr_lines) - max_stderr_lines} more lines) ---")
        else:
            print("--- stderr ---")
            print(display_stderr)
            print("--- end stderr ---")

    # Write artifact if -w was specified
    if parsed.write_file:
        try:
            out_path = secure_resolve_path(parsed.write_file, "data")

            if parsed.write_file.lower().endswith(".json"):
                artifact = _format_artifact_json(
                    cmd_display, exit_code, stdout, stderr, duration_ms
                )
            else:
                artifact = _format_artifact_text(
                    cmd_display, exit_code, stdout, stderr, duration_ms
                )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(artifact)
                f.flush()
                os.fsync(f.fileno())

            fmt_label = "JSON" if parsed.write_file.lower().endswith(".json") else "text"
            print(f"[*] @sh: Artifact saved to '{parsed.write_file}' (format: {fmt_label}).")
            logger.info(
                f"@sh: Artifact written to '{parsed.write_file}' "
                f"(format: {fmt_label}, chars: {len(artifact)})"
            )
        except PermissionError as e:
            print(f"[!] @sh: Cannot write artifact: {e}")
            logger.error(f"@sh: Artifact write blocked: {e}")
        except Exception as e:
            print(f"[!] @sh: Error writing artifact: {e}")
            logger.error(f"@sh: Artifact write error: {e}")
    exit_code = result.returncode
    return exit_code == 0  # Return True on success, False on failure 

# --------------------------------------------------
# 5.7 AI Interaction Handler
# --------------------------------------------------
def handle_ai_interaction(parts):
    """
    Handles a single AI interaction command.

    Supports Pattern B parsing with write-mode modifiers:
      @model <context> -m <msg> -r file1.py -r file2.py -w out.txt -e
      @model "prompt" -w:code script.py
      @model "prompt" -w:raw  notes.md

    Write behavior ("Raw by Default"):
      -w <file>       : Saves FULL AI response exactly as received (raw).
      -w:raw <file>   : Same as -w (explicit alias).
      -w:code <file>  : Extracts fenced code blocks only, strips prose.

    Prompt construction priority:
      a1 (context) -> a2 (-m message) -> e (editor) -> Files (-r)

    Returns
    -------
    bool
        True if the interaction completed successfully, False otherwise.
    """
    target_key = parts[0].lower().replace("@", "")
    engine = engines[target_key]

    # --- Step 1: Parse CLI input into structured data ---
    parsed = parse_cli_input(parts)
    if parsed is None:
        return False

    # --- Step 2: Editor mode ---
    editor_content = None
    if parsed.use_editor:
        editor_content = open_editor_for_prompt()
        if editor_content is None:
            return False

    # --- Step 3: Build the prompt in fixed priority order ---
    try:
        prompt_main = build_ai_prompt(parsed, editor_content)
    except AIError as e:
        safe_print(f"[!] {e}")
        return False

    # --- Step 4: Validate prompt ---
    if not prompt_main.strip():
        safe_print("[!] No prompt to send. Provide text, use -e, -m, or -r.")
        return False

    # --- Step 5: Send to AI ---
    logger.info(f"@User ({engine.name}): {prompt_main}")
    with _console_lock:
        print(f"[*] {engine.name} is thinking...", end="\r", flush=True)
    logger.info(f"[*] {engine.name} is thinking...")

    try:
        result = engine.call(prompt_main)
        clear_thinking_line()
        logger.info(f"@{engine.name}: {result}")
        logger.info("-" * 40)

        if parsed.write_file:
            if parsed.write_mode == WRITE_MODE_CODE:
                final_out = extract_code_block(result)
                mode_label = "code-extracted"
            else:
                final_out = result
                mode_label = "raw"

            out_path = secure_resolve_path(parsed.write_file, "data")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(final_out.strip())
                f.flush()
                os.fsync(f.fileno())
            safe_print(
                f"[*] Result saved to '{parsed.write_file}' (mode: {mode_label})."
            )
            logger.info(
                f"[*] File written: '{parsed.write_file}' "
                f"(mode: {mode_label}, chars: {len(final_out.strip())})"
            )
        else:
            safe_print(f"\n--- {engine.name} ---\n{result}\n")

        return True

    except AIError as e:
        clear_thinking_line()
        safe_print(f"[!] AI Engine Error: {e}")
        return False


# --------------------------------------------------
# 5.8 @sequence Command Handler
# --------------------------------------------------
def smart_split_steps(text):
    """
    Splits editor content into discrete steps using the '->' delimiter,
    while respecting quoted strings (Smart Splitting).
    """
    steps = []
    current = []
    in_quote = None
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        # Handle escape sequences (backslash)
        if ch == "\\" and i + 1 < length:
            current.append(ch)
            current.append(text[i + 1])
            i += 2
            continue

        # Handle quote state toggling
        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
            i += 1
            continue

        # Check for '->' delimiter only when outside quotes
        if in_quote is None and ch == "-" and i + 1 < length and text[i + 1] == ">":
            steps.append("".join(current))
            current = []
            i += 2
            continue

        current.append(ch)
        i += 1

    steps.append("".join(current))
    return steps


def smart_split_parallel(text):
    """
    Splits a string by the '||' operator while respecting quoted strings.
    """
    segments = []
    current = []
    in_quote = None
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        # Handle escape sequences (backslash)
        if ch == "\\" and i + 1 < length:
            current.append(ch)
            current.append(text[i + 1])
            i += 2
            continue

        # Handle quote state toggling
        if ch in ('"', "'"):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
            current.append(ch)
            i += 1
            continue

        # Check for '||' delimiter only when outside quotes
        if in_quote is None and ch == "|" and i + 1 < length and text[i + 1] == "|":
            segments.append("".join(current))
            current = []
            i += 2
            continue

        current.append(ch)
        i += 1

    segments.append("".join(current))
    return segments


def normalize_step(step_text):
    """
    Normalizes a single step's raw text for tokenization.
    Removes comments, strips whitespace, collapses spaces.
    """
    lines = step_text.splitlines()
    filtered = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        filtered.append(stripped)

    normalized = " ".join(filtered)
    while "  " in normalized:
        normalized = normalized.replace("  ", " ")
    return normalized.strip()


def detect_parallel_block(normalized_text):
    """
    Detects whether a normalized step text is a parallel block wrapped
    in '[' and ']' brackets.
    """
    stripped = normalized_text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        return True, inner
    return False, stripped


def parse_sequence_steps(editor_content):
    """
    Parses the full editor content into a nested list of tokenized step commands.

    Returns
    -------
    list[list[list[str]]] | None
        Nested list: outer=sequential steps, middle=parallel tasks, inner=tokens.
        Returns None if any parsing or validation error occurs.
    """
    raw_steps = smart_split_steps(editor_content)

    parsed_steps = []
    global_step_idx = 0

    VALID_COMMANDS = set(engines.keys()) | {"sh", "scrub", "flush", "efficient"}

    for raw in raw_steps:
        normalized = normalize_step(raw)

        if not normalized:
            continue

        global_step_idx += 1

        is_parallel, inner_text = detect_parallel_block(normalized)

        if is_parallel:
            parallel_segments = smart_split_parallel(inner_text)
            parallel_tasks = []

            for seg_idx, segment in enumerate(parallel_segments, start=1):
                seg_normalized = normalize_step(segment)
                if not seg_normalized:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: "
                        f"Empty task in parallel block."
                    )
                    logger.error(
                        f"@sequence step {global_step_idx}, "
                        f"parallel task {seg_idx}: empty"
                    )
                    return None

                try:
                    tokens = shlex.split(seg_normalized)
                except ValueError as e:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: "
                        f"Parse error (mismatched quotes?): {e}"
                    )
                    logger.error(
                        f"@sequence step {global_step_idx}, "
                        f"parallel task {seg_idx} shlex error: {e}"
                    )
                    return None

                if not tokens:
                    continue

                cmd_key = tokens[0].lower().replace("@", "")
                
                if cmd_key not in VALID_COMMANDS:
                    print(
                        f"[!] Step {global_step_idx}, parallel task {seg_idx}: "
                        f"Unknown command/model '{tokens[0]}'"
                    )
                    print(
                        f"    Available commands: "
                        f"{', '.join('@' + k for k in sorted(VALID_COMMANDS))}"
                    )
                    logger.warning(
                        f"@sequence step {global_step_idx}, "
                        f"parallel task {seg_idx}: unknown command '{tokens[0]}'"
                    )
                    return None

                if not tokens[0].startswith("@"):
                    tokens[0] = "@" + tokens[0]

                parallel_tasks.append(tokens)

            if not parallel_tasks:
                print(
                    f"[!] Step {global_step_idx}: "
                    f"No valid tasks found in parallel block."
                )
                return None

            parsed_steps.append(parallel_tasks)

        else:
            try:
                tokens = shlex.split(normalized)
            except ValueError as e:
                print(
                    f"[!] Step {global_step_idx}: Parse error (mismatched quotes?): {e}"
                )
                logger.error(f"@sequence step {global_step_idx} shlex error: {e}")
                return None

            if not tokens:
                continue

            cmd_key = tokens[0].lower().replace("@", "")
            if cmd_key not in VALID_COMMANDS:
                print(
                    f"[!] Step {global_step_idx}: "
                    f"Unknown command/model '{tokens[0]}'"
                )
                print(
                    f"    Available commands: "
                    f"{', '.join('@' + k for k in sorted(VALID_COMMANDS))}"
                )
                logger.warning(
                    f"@sequence step {global_step_idx}: unknown command '{tokens[0]}'"
                )
                return None

            if not tokens[0].startswith("@"):
                tokens[0] = "@" + tokens[0]

            parsed_steps.append([tokens])

    return parsed_steps


# --------------------------------------------------
# 5.9 Command Dispatcher
# --------------------------------------------------
def dispatch_command(parts):
    """
    入力されたトークンのリストを受け取り、適切なハンドラにルーティングする。
    成功すれば True を、失敗または不明なコマンドであれば False を返す。
    （Sequence実行時のCascade Stop判定に利用）
    """
    cmd = parts[0].lower()

    if cmd in ["@scrub", "@flush"]:
        handle_scrub(parts)
        return True
        
    if cmd == "@efficient":
        handle_efficient(parts)
        return True
        
    if cmd == "@sequence":
        handle_sequence(parts)
        return True
        
    if cmd == "@sh":
        return handle_sh(parts)

    target_key = cmd.replace("@", "")
    if target_key in engines:
        return handle_ai_interaction(parts)

    print(f"[!] Unknown command: '{cmd}'")
    print(
        f"    Available: {', '.join('@' + k for k in engines.keys())}, "
        f"@efficient, @scrub, @sequence, @sh, exit"
    )
    return False


def handle_sequence(parts):
    """
    Handles the @sequence command with Sequential and Parallel Execution support.

    Usage: @sequence -e | @sequence --edit
    """
    # --- Step 1: Require -e flag ---
    has_edit_flag = any(token in ("-e", "--edit") for token in parts[1:])
    if not has_edit_flag:
        print("[!] Usage: @sequence -e")
        print("    The -e (--edit) flag is required to open the editor.")
        return

    # --- Step 2: Open editor ---
    logger.info("[*] @sequence: Opening editor for sequential pipeline input.")
    editor_content = open_editor_for_prompt()
    if editor_content is None:
        return

    # --- Step 3: Parse into steps ---
    parsed_steps = parse_sequence_steps(editor_content)
    if parsed_steps is None:
        return

    if not parsed_steps:
        print("[!] No valid steps found in sequence. Cancelled.")
        return

    total = len(parsed_steps)

    # Single sequential step
    if total == 1 and len(parsed_steps[0]) == 1:
        tokens = parsed_steps[0][0]
        step_summary = shlex.join(tokens)
        print(f"[*] @sequence executing (single step): {step_summary}")
        logger.info(f"[*] @sequence single step: {step_summary}")
        success = dispatch_command(tokens)
        if not success:
            print("[!] Single-step sequence failed.")
        return

    # --- Step 4: Execution Pipeline ---
    print(f"[*] Sequence Execution: {total} steps detected.")
    print("=" * 50)
    logger.info(f"[*] @sequence: Starting pipeline with {total} steps.")

    for idx, step_tasks in enumerate(parsed_steps, start=1):
        num_tasks = len(step_tasks)
        is_parallel = num_tasks > 1

        if is_parallel:
            # --- Parallel Execution Block ---
            task_summaries = [shlex.join(t) for t in step_tasks]
            print(f"[*] Executing Step {idx}/{total} [PARALLEL: {num_tasks} tasks]...")
            for t_idx, summary in enumerate(task_summaries, start=1):
                print(f"    Task {t_idx}: {summary}")
            logger.info(
                f"[*] @sequence Step {idx}/{total}: "
                f"Parallel block with {num_tasks} tasks."
            )

            results = {}
            with ThreadPoolExecutor(max_workers=num_tasks) as executor:
                future_to_task = {}
                for t_idx, task_tokens in enumerate(step_tasks, start=1):
                    future = executor.submit(dispatch_command, task_tokens)
                    future_to_task[future] = t_idx

                for future in as_completed(future_to_task):
                    t_idx = future_to_task[future]
                    try:
                        success = future.result()
                        results[t_idx] = success
                    except Exception as e:
                        logger.error(
                            f"[!] @sequence Step {idx}, Task {t_idx} exception: {e}"
                        )
                        results[t_idx] = False

            # Check results: all must succeed for the block to pass
            all_succeeded = all(results.values())
            failed_tasks = [t_idx for t_idx, ok in results.items() if not ok]

            if not all_succeeded:
                safe_print(
                    f"[!] Step {idx}/{total} PARALLEL BLOCK FAILED. "
                    f"Failed tasks: {failed_tasks}"
                )
                safe_print(
                    f"[!] Cascade Stop: {total - idx} remaining step(s) skipped."
                )
                logger.error(
                    f"[!] @sequence Cascade Stop at step {idx}/{total} "
                    f"(parallel). Failed tasks: {failed_tasks}. "
                    f"{total - idx} step(s) skipped."
                )
                return

            safe_print(
                f"[✓] Step {idx}/{total} completed successfully "
                f"(all {num_tasks} parallel tasks done)."
            )

        else:
            # --- Sequential (single task) Execution ---
            tokens = step_tasks[0]
            step_summary = shlex.join(tokens)
            print(f"[*] Executing Step {idx}/{total}...")
            print(f"    Command: {step_summary}")
            logger.info(f"[*] @sequence Step {idx}/{total}: {step_summary}")

            success = dispatch_command(tokens)

            if not success:
                print(f"[!] Step {idx}/{total} failed. Halting sequence.")
                print(f"[!] Cascade Stop: {total - idx} remaining step(s) skipped.")
                logger.error(
                    f"[!] @sequence Cascade Stop at step {idx}/{total}. "
                    f"{total - idx} step(s) skipped."
                )
                return

            print(f"[✓] Step {idx}/{total} completed successfully.")

        if idx < total:
            print("-" * 50)

    # --- Pipeline complete ---
    print("=" * 50)
    print(f"[✓] Sequence Execution complete. All {total} steps succeeded.")
    logger.info(f"[*] @sequence: Pipeline complete. All {total} steps succeeded.")


# --------------------------------------------------
# 6. Main Event Loop
# --------------------------------------------------
print_welcome_banner()

while True:
    try:
        user_input = input("% ").strip()
        
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            logger.info("--- Session Ended ---")
            break

        try:
            parts = shlex.split(user_input)
        except ValueError as e:
            print(f"[!] Parse error: {e}")
            continue
            
        if not parts:
            continue

        dispatch_command(parts)

    except KeyboardInterrupt:
        print("\n[!] Session interrupted. Type 'exit' to quit.")
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        logger.error(f"Main Loop Critical Error: {e}")
