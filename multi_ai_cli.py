import os
import sys
import configparser
import google.generativeai as genai
from openai import OpenAI

# --------------------------------------------------
# 1. Config & Directory Management
# --------------------------------------------------
INI_FILE = "multi_ai_cli.ini"

if not os.path.exists(INI_FILE):
    print(f"[!] Error: '{INI_FILE}' not found in the current directory.")
    print("    Please place the configuration file in your working directory.")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(INI_FILE, encoding='utf-8')

try:
    genai.configure(api_key=config.get("API_KEYS", "gemini_api_key"))
    client_gpt = OpenAI(api_key=config.get("API_KEYS", "openai_api_key"))
    gemini_model_name = config.get("MODELS", "gemini_model", fallback="gemini-2.0-flash")
    gpt_model_name = config.get("MODELS", "gpt_model", fallback="gpt-4o-mini")
except Exception as e:
    print(f"[!] Config Error: {e}")
    sys.exit(1)

efficient_dir = config.get("Paths", "work_efficient", fallback="prompts")
data_dir = config.get("Paths", "work_data", fallback="data")

for d in [efficient_dir, data_dir]:
    if not os.path.exists(d):
        os.makedirs(d)

def resolve_path(filename, category="data"):
    base = efficient_dir if category == "efficient" else data_dir
    return os.path.join(base, filename)

# --------------------------------------------------
# 2. AI Model Initialization
# --------------------------------------------------
gpt_system_prompt = ""
gemini_model = genai.GenerativeModel(gemini_model_name)
gemini_chat = gemini_model.start_chat(history=[])
gpt_history = []

def call_gemini(prompt):
    try:
        response = gemini_chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"Gemini Error: {e}"

def call_gpt(prompt):
    global gpt_history
    messages = []
    if gpt_system_prompt:
        messages.append({"role": "system", "content": gpt_system_prompt})
    messages.extend(gpt_history)
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client_gpt.chat.completions.create(
            model=gpt_model_name,
            messages=messages
        )
        answer = response.choices[0].message.content
        gpt_history.append({"role": "user", "content": prompt})
        gpt_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        return f"GPT Error: {e}"

# --------------------------------------------------
# 3. Main Interface & Loop
# --------------------------------------------------
def print_welcome_banner():
    print(f"==================================================")
    print(f"  Multi-AI CLI Beta")
    print(f"  Gemini: {gemini_model_name}")
    print(f"  GPT   : {gpt_model_name}")
    print(f"==================================================")
    print(f"[*] Paths initialized: Efficient='{efficient_dir}', Data='{data_dir}'")
    print(f"[*] Available Commands:")
    print(f"    @gemini <prompt> [read <file>] [write <file>]")
    print(f"    @gpt    <prompt> [read <file>] [write <file>]")
    print(f"    @efficient [gemini/gpt/all] <filename>")
    print(f"    @scrub     [gemini/gpt/all]")
    print(f"    exit / quit")
    print(f"==================================================\n")

print_welcome_banner()

while True:
    try:
        user_input = input("% ").strip()
        if not user_input: continue
        if user_input.lower() in ["exit", "quit"]:
            print("\n[*] Shutting down the AI agents... Goodbye!")
            break

        parts = user_input.split()
        cmd = parts[0].lower()

        # Command: @scrub
        if cmd in ["@scrub", "@flush"]:
            target = parts[1].lower() if len(parts) > 1 else "all"
            if target in ["all", "gemini"]:
                gemini_chat = gemini_model.start_chat(history=[])
                print("[*] Gemini memory successfully scrubbed.")
            if target in ["all", "gpt"]:
                gpt_history = [{"role": "system", "content": gpt_system_prompt}] if gpt_system_prompt else []
                print("[*] GPT memory successfully scrubbed.")
            continue

        # Command: @efficient
        if cmd == "@efficient":
            if len(parts) < 2:
                print("[!] Usage: @efficient [gemini/gpt] filename.txt")
                continue
            
            if parts[1].lower() in ["gemini", "gpt"]:
                target, filename = parts[1].lower(), parts[2]
            else:
                target, filename = "all", parts[1]

            try:
                with open(resolve_path(filename, "efficient"), "r", encoding="utf-8") as f:
                    prompt_text = f.read()
                
                if target in ["all", "gemini"]:
                    gemini_model = genai.GenerativeModel(gemini_model_name, system_instruction=prompt_text)
                    gemini_chat = gemini_model.start_chat(history=[])
                    print(f"[*] Gemini personality loaded from '{filename}'.")
                if target in ["all", "gpt"]:
                    gpt_system_prompt = prompt_text
                    gpt_history = [{"role": "system", "content": gpt_system_prompt}]
                    print(f"[*] GPT personality loaded from '{filename}'.")
            except Exception as e:
                print(f"[!] File Error: {e}")
            continue

        # Command: @gemini / @gpt
        if cmd in ["@gemini", "@gpt"]:
            target_ai = cmd
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
                        prompt_main += "\n\n[Attached File Content]:\n" + f.read()
                except Exception as e:
                    print(f"[!] Read Error: {e}")
                    continue

            # --- Thinking Message ---
            print(f"[*] {target_ai.upper().replace('@', '')} is thinking...", end="\r", flush=True)

            # AI Execution
            result = call_gemini(prompt_main) if target_ai == "@gemini" else call_gpt(prompt_main)

            # Clear Thinking Message
            print(" " * 50, end="\r", flush=True) 

            # Markdown Cleanup for 'write'
            final_result = result
            if output_file and "```" in result:
                lines = result.splitlines()
                if lines and lines[0].startswith("```"): lines = lines[1:]
                if lines and lines[-1].startswith("```"): lines = lines[:-1]
                final_result = "\n".join(lines)

            # Output Handling
            if output_file:
                try:
                    with open(resolve_path(output_file, "data"), "w", encoding="utf-8") as f:
                        f.write(final_result)
                    print(f"[*] Result successfully written to '{data_dir}/{output_file}'.")
                except Exception as e:
                    print(f"[!] Write Error: {e}")
            else:
                print(f"\n--- {target_ai.upper().replace('@', '')} Response ---\n{result}\n")

    except KeyboardInterrupt:
        print("\n[!] Process interrupted. Type 'exit' to quit.")
    except Exception as e:
        print(f"[!] Unexpected Error: {e}")
