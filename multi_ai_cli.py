import os
import sys
import argparse
import configparser
import logging
from logging.handlers import RotatingFileHandler
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic

# --------------------------------------------------
# 1. Argparse & Config Management
# --------------------------------------------------
parser = argparse.ArgumentParser(description="Multi-AI CLI (Quad Engine Edition)")
parser.add_argument("--no-log", action="store_true", help="Disable logging for this session (Stealth Mode)")
args = parser.parse_args()

INI_FILE = "multi_ai_cli.ini"

if not os.path.exists(INI_FILE):
    print(f"[!] Error: '{INI_FILE}' not found in the current directory.")
    print("    Please place the configuration file in your working directory.")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(INI_FILE, encoding='utf-8')

# --------------------------------------------------
# 2. Logging System Setup
# --------------------------------------------------
should_log = config.getboolean("logging", "enabled", fallback=True) and not args.no_log

logger = logging.getLogger("MultiAI")
logger.setLevel(logging.DEBUG) # ベースレベル。ハンドラ側でフィルタする

if should_log:
    log_dir = config.get("logging", "log_dir", fallback="logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    base_filename = config.get("logging", "base_filename", fallback="chat.log")
    log_path = os.path.join(log_dir, base_filename)
    
    max_bytes = config.getint("logging", "max_bytes", fallback=10485760)
    backup_count = config.getint("logging", "backup_count", fallback=5)
    
    log_level_str = config.get("logging", "log_level", fallback="INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    handler.setLevel(log_level)
    
    # フォーマット: [HH:MM:SS] メッセージ本文
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

# --------------------------------------------------
# 3. API Clients Initialization
# --------------------------------------------------
try:
    genai.configure(api_key=config.get("API_KEYS", "gemini_api_key"))
    client_gpt = OpenAI(api_key=config.get("API_KEYS", "openai_api_key"))
    client_claude = Anthropic(api_key=config.get("API_KEYS", "anthropic_api_key"))
    client_grok = OpenAI(
        api_key=config.get("API_KEYS", "grok_api_key"),
        base_url="https://api.x.ai/v1"
    )

    gemini_model_name = config.get("MODELS", "gemini_model", fallback="gemini-2.5-flash")
    gpt_model_name = config.get("MODELS", "gpt_model", fallback="gpt-4o-mini")
    claude_model_name = config.get("MODELS", "claude_model", fallback="claude-3-5-sonnet-20241022")
    grok_model_name = config.get("MODELS", "grok_model", fallback="grok-4-latest")
except Exception as e:
    print(f"[!] Config Error: {e}")
    sys.exit(1)

# Paths
efficient_dir = config.get("Paths", "work_efficient", fallback="prompts")
data_dir = config.get("Paths", "work_data", fallback="work_data")

for d in [efficient_dir, data_dir]:
    if not os.path.exists(d):
        os.makedirs(d)

def resolve_path(filename, category="data"):
    base = efficient_dir if category == "efficient" else data_dir
    return os.path.join(base, filename)

# --------------------------------------------------
# 4. AI Model Interface & History
# --------------------------------------------------
gemini_model = genai.GenerativeModel(gemini_model_name)
gemini_chat = gemini_model.start_chat(history=[])

gpt_system_prompt = ""
gpt_history = []

claude_system_prompt = ""
claude_history = []

grok_system_prompt = ""
grok_history = []

def call_gemini(prompt):
    try:
        response = gemini_chat.send_message(prompt)
        logger.debug(f"[DEBUG] Gemini Raw Response: {response}")
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return f"Gemini Error: {e}"

def call_gpt(prompt):
    global gpt_history
    messages = []
    if gpt_system_prompt:
        messages.append({"role": "system", "content": gpt_system_prompt})
    messages.extend(gpt_history)
    messages.append({"role": "user", "content": prompt})
    try:
        response = client_gpt.chat.completions.create(model=gpt_model_name, messages=messages)
        logger.debug(f"[DEBUG] GPT Raw Response: {response}")
        answer = response.choices[0].message.content
        gpt_history.append({"role": "user", "content": prompt})
        gpt_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        logger.error(f"GPT Error: {e}")
        return f"GPT Error: {e}"

def call_claude(prompt):
    global claude_history
    try:
        messages = list(claude_history)
        messages.append({"role": "user", "content": prompt})
        
        response = client_claude.messages.create(
            model=claude_model_name,
            max_tokens=8192,
            system=claude_system_prompt if claude_system_prompt else "",
            messages=messages
        )
        logger.debug(f"[DEBUG] Claude Raw Response: {response}")
        answer = response.content[0].text
        claude_history.append({"role": "user", "content": prompt})
        claude_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        logger.error(f"Claude Error: {e}")
        return f"Claude Error: {e}"

def call_grok(prompt):
    global grok_history
    messages = []
    if grok_system_prompt:
        messages.append({"role": "system", "content": grok_system_prompt})
    messages.extend(grok_history)
    messages.append({"role": "user", "content": prompt})
    try:
        response = client_grok.chat.completions.create(model=grok_model_name, messages=messages)
        logger.debug(f"[DEBUG] Grok Raw Response: {response}")
        answer = response.choices[0].message.content
        grok_history.append({"role": "user", "content": prompt})
        grok_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        logger.error(f"Grok Error: {e}")
        return f"Grok Error: {e}"

# --------------------------------------------------
# 5. Main UI & Loop
# --------------------------------------------------
def print_welcome_banner():
    print(f"==================================================")
    print(f"  Multi-AI CLI v0.4.0 (Quad Engine + HUD Edition)")
    print(f"  Gemini: {gemini_model_name}")
    print(f"  GPT   : {gpt_model_name}")
    print(f"  Claude: {claude_model_name}")
    print(f"  Grok  : {grok_model_name}")
    print(f"==================================================")
    print(f"[*] Paths: Efficient='{efficient_dir}', Data='{data_dir}'")
    print(f"[*] Commands: @gemini, @gpt, @claude, @grok, @efficient, @scrub, exit")
    log_status = "Disabled (Stealth Mode)" if not should_log else f"Enabled (tail -f logs/chat.log)"
    print(f"[*] Logging: {log_status}")
    print(f"==================================================\n")

print_welcome_banner()

while True:
    try:
        user_input = input("% ").strip()
        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]:
            print("\n[*] Shutting down the Quad Engine... Goodbye!")
            logger.info("--- Session Ended ---")
            break

        parts = user_input.split()
        cmd = parts[0].lower()

        # Command: @scrub (Memory Reset)
        if cmd in ["@scrub", "@flush"]:
            target = parts[1].lower() if len(parts) > 1 else "all"
            if target in ["all", "gemini"]:
                gemini_chat = gemini_model.start_chat(history=[])
                print("[*] Gemini memory scrubbed.")
                logger.info("[*] System: Gemini memory scrubbed.")
            if target in ["all", "gpt"]:
                gpt_history = [{"role": "system", "content": gpt_system_prompt}] if gpt_system_prompt else []
                print("[*] GPT memory scrubbed.")
                logger.info("[*] System: GPT memory scrubbed.")
            if target in ["all", "claude"]:
                claude_history = []
                print("[*] Claude memory scrubbed.")
                logger.info("[*] System: Claude memory scrubbed.")
            if target in ["all", "grok"]:
                grok_history = [{"role": "system", "content": grok_system_prompt}] if grok_system_prompt else []
                print("[*] Grok memory scrubbed.")
                logger.info("[*] System: Grok memory scrubbed.")
            continue

        # Command: @efficient (System Prompt Injection)
        if cmd == "@efficient":
            if len(parts) < 2:
                print("[!] Usage: @efficient [gemini/gpt/claude/grok/all] filename.txt")
                continue
            
            target = parts[1].lower() if parts[1].lower() in ["gemini", "gpt", "claude", "grok"] else "all"
            filename = parts[2] if target != "all" else parts[1]

            try:
                with open(resolve_path(filename, "efficient"), "r", encoding="utf-8") as f:
                    prompt_text = f.read()
                
                if target in ["all", "gemini"]:
                    gemini_model = genai.GenerativeModel(gemini_model_name, system_instruction=prompt_text)
                    gemini_chat = gemini_model.start_chat(history=[])
                    print(f"[*] Gemini persona loaded: '{filename}'.")
                    logger.info(f"[*] System: Gemini persona loaded from '{filename}'.")
                if target in ["all", "gpt"]:
                    gpt_system_prompt = prompt_text
                    gpt_history = [{"role": "system", "content": gpt_system_prompt}]
                    print(f"[*] GPT persona loaded: '{filename}'.")
                    logger.info(f"[*] System: GPT persona loaded from '{filename}'.")
                if target in ["all", "claude"]:
                    claude_system_prompt = prompt_text
                    claude_history = []
                    print(f"[*] Claude persona loaded: '{filename}'.")
                    logger.info(f"[*] System: Claude persona loaded from '{filename}'.")
                if target in ["all", "grok"]:
                    grok_system_prompt = prompt_text
                    grok_history = [{"role": "system", "content": grok_system_prompt}]
                    print(f"[*] Grok persona loaded: '{filename}'.")
                    logger.info(f"[*] System: Grok persona loaded from '{filename}'.")
            except Exception as e:
                print(f"[!] File Error: {e}")
                logger.error(f"[!] File Error parsing persona: {e}")
            continue

        # Command: AI Interactions
        if cmd in ["@gemini", "@gpt", "@claude", "@grok"]:
            target_ai = cmd
            ai_name_clean = target_ai.upper().replace('@', '')
            input_file = None
            output_file = None
            
            if "read" in parts:
                idx = parts.index("read")
                if idx + 1 < len(parts): input_file = parts[idx + 1]
            if "write" in parts:
                idx = parts.index("write")
                if idx + 1 < len(parts): output_file = parts[idx + 1]

            prompt_main = " ".join([p for p in parts[1:] if p not in ["read", "write", input_file, output_file]])

            if input_file:
                try:
                    with open(resolve_path(input_file, "data"), "r", encoding="utf-8") as f:
                        file_content = f.read()
                        prompt_main += "\n\n[Attached File Content]:\n" + file_content
                except Exception as e:
                    print(f"[!] Read Error: {e}")
                    logger.error(f"[!] Read Error: {e}")
                    continue

            # --- HUD LOGGING (User) ---
            logger.info(f"@User ({ai_name_clean}): {prompt_main}")

            # Thinking Message
            print(f"[*] {ai_name_clean} is thinking...", end="\r", flush=True)

            # Call specific AI
            if target_ai == "@gemini": result = call_gemini(prompt_main)
            elif target_ai == "@gpt": result = call_gpt(prompt_main)
            elif target_ai == "@claude": result = call_claude(prompt_main)
            elif target_ai == "@grok": result = call_grok(prompt_main)

            print(" " * 50, end="\r", flush=True) # Clear line

            # --- HUD LOGGING (AI Response) ---
            logger.info(f"@{ai_name_clean}: {result}")

            # Output Formatting
            final_result = result
            code_block_marker = chr(96) * 3
            if output_file and code_block_marker in result:
                lines = result.splitlines()
                if lines and lines[0].startswith(code_block_marker): lines = lines[1:]
                if lines and lines[-1].startswith(code_block_marker): lines = lines[:-1]
                final_result = "\n".join(lines)

            if output_file:
                try:
                    with open(resolve_path(output_file, "data"), "w", encoding="utf-8") as f:
                        f.write(final_result)
                    print(f"[*] Result written to '{data_dir}/{output_file}'.")
                    logger.info(f"[*] System: Result saved to '{data_dir}/{output_file}'.")
                except Exception as e:
                    print(f"[!] Write Error: {e}")
                    logger.error(f"[!] Write Error: {e}")
            else:
                print(f"\n--- {ai_name_clean} ---\n{result}\n")

    except KeyboardInterrupt:
        print("\n[!] Process interrupted. Type 'exit' to quit.")
    except Exception as e:
        print(f"[!] Error: {e}")
        logger.error(f"[!] Main Loop Error: {e}")
