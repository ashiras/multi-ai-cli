import os
import sys
import argparse
import configparser
import logging
import shutil
import tempfile
import subprocess
from logging.handlers import RotatingFileHandler
from abc import ABC, abstractmethod

# AI SDKs
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic

# ==================================================
# Constants & Configuration
# ==================================================
VERSION = "0.5.5"
DEFAULT_LOG_MAX_BYTES = 10485760
DEFAULT_LOG_BACKUP_COUNT = 5
DEFAULT_MAX_HISTORY_TURNS = 30

# --------------------------------------------------
# 1. Argparse & Config Management
# --------------------------------------------------
parser = argparse.ArgumentParser(
    description=f"Multi-AI CLI v{VERSION} (Editor Support Update)"
)
parser.add_argument(
    "--no-log",
    action="store_true",
    help="Disable logging for this session (Stealth Mode)",
)
parser.add_argument(
    "--version", action="version", version=f"Multi-AI CLI v{VERSION}"
)
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
            print(
                f"[!] Logging Error: Could not create log directory '{log_dir}': {e}"
            )
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
# 2.5 Editor Integration (NEW in v0.5.5)
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
    editor = os.environ.get("EDITOR", "vi")

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

        result = subprocess.run([editor, tmp_path])

        if result.returncode != 0:
            logger.warning(
                f"Editor exited with non-zero status: {result.returncode}"
            )
            print(f"[!] Editor exited with error (code {result.returncode}).")
            return None

        with open(tmp_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        lines = raw_content.splitlines()

        if MARKER in lines:
            idx = lines.index(MARKER) + 1
            content = "\n".join(lines[idx:]).lstrip("\n").strip()
        else:
            # Fallback: drop only the initial comment/header block (+ blank lines)
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
        print(
            f"[!] Editor '{editor}' not found. Set $EDITOR to your preferred editor."
        )
        print(f"    Example: export EDITOR=nano")
        logger.error(f"Editor not found: {editor}")
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
        logger.info(f"[*] System: {self.name} persona loaded from '{filename}'.")


class GeminiEngine(AIEngine):
    """Google Gemini specific implementation."""

    def __init__(self, name, model_name):
        super().__init__(name, model_name)
        self.rebuild_model()

    def rebuild_model(self):
        instr = self.system_prompt if self.system_prompt else None
        self.model = genai.GenerativeModel(
            self.model_name, system_instruction=instr
        )
        self.chat = self.model.start_chat(history=[])

    def load_persona(self, prompt_text, filename):
        super().load_persona(prompt_text, filename)
        self.rebuild_model()

    def scrub(self):
        super().scrub()
        self.chat = self.model.start_chat(history=[])

    def call(self, prompt):
        try:
            response = self.chat.send_message(prompt)
            logger.debug(
                f"[DEBUG] Gemini response received. Char count: {len(response.text)}"
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            raise AIError(f"Gemini error: {e}")


class OpenAIEngine(AIEngine):
    """OpenAI-compatible implementation (GPT, Grok)."""

    def __init__(self, name, model_name, client):
        super().__init__(name, model_name)
        self.client = client

    def call(self, prompt):
        self._trim_history()
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name, messages=messages
            )
            answer = response.choices[0].message.content
            logger.debug(
                f"[DEBUG] {self.name} response received. Char count: {len(answer)}"
            )

            self.history.append({"role": "user", "content": prompt})
            self.history.append({"role": "assistant", "content": answer})
            self._trim_history()
            return answer
        except Exception as e:
            logger.error(f"{self.name} API Error: {e}")
            raise AIError(f"{self.name} error: {e}")


class ClaudeEngine(AIEngine):
    """Anthropic Claude specific implementation."""

    def __init__(self, name, model_name, client):
        super().__init__(name, model_name)
        self.client = client
        self.max_tokens = config.getint("MODELS", "claude_max_tokens", fallback=8192)

    def call(self, prompt):
        self._trim_history()
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=self.max_tokens,
                system=self.system_prompt if self.system_prompt else "",
                messages=self.history + [{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text
            logger.debug(
                f"[DEBUG] Claude response received. Char count: {len(answer)}"
            )

            self.history.append({"role": "user", "content": prompt})
            self.history.append({"role": "assistant", "content": answer})
            self._trim_history()
            return answer
        except Exception as e:
            logger.error(f"Claude API Error: {e}")
            raise AIError(f"Claude error: {e}")


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

    engines = {
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
    }

    for d_opt in ["work_efficient", "work_data"]:
        d_default = "prompts" if "efficient" in d_opt else "work_data"
        d_path = config.get("Paths", d_opt, fallback=d_default)
        os.makedirs(d_path, exist_ok=True)

except Exception as e:
    print(f"[!] Startup Error: {e}")
    sys.exit(1)


# --------------------------------------------------
# 5. Main Loop & UI
# --------------------------------------------------
def print_welcome_banner():
    """Displays the startup banner with model info and available commands."""
    print("==================================================")
    print(f"  Multi-AI CLI v{VERSION} (Editor Support)")
    for name, eng in engines.items():
        print(f"  {eng.name:<6}: {eng.model_name}")
    print("==================================================")
    log_status = (
        "Disabled (Stealth)"
        if not is_log_enabled
        else "Enabled (tail -f logs/chat.log)"
    )
    print(f"[*] Logging: {log_status}")
    print("[*] Commands: @model, @efficient, @scrub, exit")
    print("[*] Editor:   @model -e | --edit  (uses $EDITOR or vi)")
    print("[*] Flags:    -r <file> (read)  -w <file> (write)")
    print()


def clear_thinking_line():
    """Clears the 'thinking' status line in the terminal."""
    cols = shutil.get_terminal_size().columns
    print(" " * (cols - 1), end="\r", flush=True)


def extract_code_block(text):
    """
    If the response contains a fenced code block, extract its contents.
    Used when writing output to a file with -w flag.
    """
    if "```" not in text:
        return text

    try:
        blocks = text.split("```")
        if len(blocks) >= 3:
            block_lines = blocks[1].splitlines()
            # Skip the language identifier line (e.g., ```python)
            if block_lines and len(block_lines[0].strip()) < 15:
                return "\n".join(block_lines[1:])
            else:
                return "\n".join(block_lines)
    except Exception:
        pass
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
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        for name, engine in engines.items():
            if target in ["all", name]:
                engine.load_persona(content, filename)
                print(f"[*] {engine.name} persona loaded: '{filename}'.")
    except Exception as e:
        print(f"[!] Persona loading failed: {e}")


def parse_ai_flags(parts):
    """
    Parses flags from the command parts for AI interaction.

    Recognized flags:
      --read  / -r <file>  : Read input file
      --write / -w <file>  : Write output file
      --edit  / -e         : Open editor for prompt input

    Returns:
      (input_file, output_file, use_editor, prompt_text)
    """
    input_file = None
    output_file = None
    use_editor = False
    indices_to_remove = {0}  # Always remove the @model token

    # Parse --read / -r and --write / -w (each takes one argument)
    for flag, short, attr_name in [
        ("--read", "-r", "read"),
        ("--write", "-w", "write"),
    ]:
        kw = flag if flag in parts else (short if short in parts else None)
        if kw:
            idx = parts.index(kw)
            if idx + 1 < len(parts):
                if attr_name == "read":
                    input_file = parts[idx + 1]
                else:
                    output_file = parts[idx + 1]
                indices_to_remove.update({idx, idx + 1})
            else:
                print(f"[!] Flag '{kw}' requires a filename argument.")
                return None, None, False, None

    # Parse --edit / -e (no argument)
    for edit_flag in ("--edit", "-e"):
        if edit_flag in parts:
            idx = parts.index(edit_flag)
            use_editor = True
            indices_to_remove.add(idx)

    # Build prompt from remaining parts
    prompt_text = " ".join(
        [parts[i] for i in range(len(parts)) if i not in indices_to_remove]
    )

    return input_file, output_file, use_editor, prompt_text


def handle_ai_interaction(parts):
    """
    Handles a single AI interaction command.

    Supports:
      @model <prompt>                  : Direct prompt
      @model -e                        : Editor mode
      @model -e -r input.txt           : Editor + file read
      @model -e -w output.txt          : Editor + file write
      @model <prompt> -r in -w out     : All flags combined
    """
    target_key = parts[0].lower().replace("@", "")
    engine = engines[target_key]

    # --- Parse all flags ---
    parsed = parse_ai_flags(parts)
    input_file, output_file, use_editor, prompt_main = parsed

    # If flag parsing returned None for prompt, there was an error
    if prompt_main is None:
        return

    # --- Editor mode ---
    if use_editor:
        editor_content = open_editor_for_prompt()
        if editor_content is None:
            return

        if prompt_main.strip():
            prompt_main = prompt_main.strip() + "\n\n" + editor_content
        else:
            prompt_main = editor_content

    # --- Attach input file ---
    if input_file:
        try:
            filepath = secure_resolve_path(input_file, "data")
            with open(filepath, "r", encoding="utf-8") as f:
                file_content = f.read()
            prompt_main += f"\n\n[Attached File]:\n{file_content}"
        except Exception as e:
            print(f"[!] Error reading input file: {e}")
            return

    # --- Validate prompt ---
    if not prompt_main.strip():
        print("[!] No prompt to send. Provide text, use -e, or use -r.")
        return

    # --- Send to AI ---
    logger.info(f"@User ({engine.name}): {prompt_main}")
    print(f"[*] {engine.name} is thinking...", end="\r", flush=True)
    logger.info(f"[*] {engine.name} is thinking...")

    try:
        result = engine.call(prompt_main)
        clear_thinking_line()
        logger.info(f"@{engine.name}: {result}")
        logger.info("-" * 40)

        if output_file:
            final_out = extract_code_block(result)
            out_path = secure_resolve_path(output_file, "data")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(final_out.strip())
            print(f"[*] Result saved to '{output_file}'.")
        else:
            print(f"\n--- {engine.name} ---\n{result}\n")

    except AIError as e:
        clear_thinking_line()
        print(f"[!] AI Engine Error: {e}")


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

        parts = user_input.split()
        cmd = parts[0].lower()

        # --- Command routing ---
        if cmd in ["@scrub", "@flush"]:
            handle_scrub(parts)
            continue

        if cmd == "@efficient":
            handle_efficient(parts)
            continue

        target_key = cmd.replace("@", "")
        if target_key in engines:
            handle_ai_interaction(parts)
            continue

        # --- Unknown command ---
        print(f"[!] Unknown command: '{cmd}'")
        print(
            f"    Available: {', '.join('@' + k for k in engines.keys())}, "
            f"@efficient, @scrub, exit"
        )

    except KeyboardInterrupt:
        print("\n[!] Session interrupted. Type 'exit' to quit.")
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        logger.error(f"Main Loop Critical Error: {e}")