## multi-ai-cli

A lightweight CLI to orchestrate Gemini, GPT, Claude, and Grok using your local files as a shared blackboard.

### 🐉 Multi-AI CLI (v0.5.4 Architectural Overhaul Edition)

Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room.

Multi-AI CLI is a lightweight, zero-friction command-line tool designed to seamlessly orchestrate the world's leading AI engines: **Google Gemini**, **OpenAI GPT**, **Anthropic Claude**, and **xAI Grok**.

Built on the philosophy of **"Command & Monitor"**, it allows you to iterate, design, and code at the speed of thought. By using local files as a "shared blackboard," agents can collaborate, cross-check, and implement complex architectures while you monitor the entire conversation flow in real-time through a dedicated HUD.

### ✨ Features

- **🎼 Quad-Engine Symphony**: Instantly switch between `@gemini`, `@gpt`, `@claude`, and `@grok` within the same session.
- **📺 HUD Monitoring (Live Log)**: Monitor the "AI conversation" in a separate terminal window using tail -f. Keep your workspace clean and professional.
- **📂 Smart File I/O**: Use `-r` (`--read`) and `-w` (`--write`) flags to interact with local files. It automatically extracts code blocks and handles directory scoping securely.
- **🎭 Persona Injection (@efficient)**: Inject system prompts (e.g., "Senior Architect", "Security Auditor") from local text files.
- **🧹 Memory Control (@scrub)**: Precise control over conversation history. Flush specific AI memories or all at once.
- **🔒 Security First**: Built-in protection against directory traversal and secure API key management via environment variables.
- **🕶️ Stealth Mode**: Use the `--no-log` flag to suppress file output for sensitive sessions.

### 🍎 Installation (macOS / Linux)
1. Download the binary from the [Latest Release](https://github.com/ashiras/multi-ai-cli/releases/).
2. Add execution permission:
```bash
chmod +x multi-ai
```
3. Move to your local bin directory:
```bash
sudo mv multi-ai /usr/local/bin/
```
4. Verify installation:
```bash
multi-ai --version
```

Note: On macOS, if prompted with a security warning, go to System Settings > Privacy & Security and click "Allow Anyway".

### 🛠 Setup

#### 1. API Keys & Environment Variables

You can set your API keys as environment variables (recommended) or in the `.ini` file. Environment variables take priority.
```ini
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GROK_API_KEY="..."
```

#### 2. Configuration File (`multi_ai_cli.ini`)

Place this file in your working directory to define models and paths.
```ini
[API_KEYS]
# Leave empty if using environment variables
gemini_api_key = ...
openai_api_key = ...
anthropic_api_key = ...
grok_api_key = ...

[MODELS]
gemini_model = gemini-2.5-flash
gpt_model = gpt-4o-mini
claude_model = claude-opus-4-6
grok_model = grok-4-latest
max_history_turns = 30

[logging]
enabled = true
log_dir = logs
base_filename = chat.log

[Paths]
work_efficient = prompts
work_data = data
```

#### 3. HUD Workflow (Recommended)

Open a second terminal window and run:
```bash
tail -f logs/chat.log
```

### 💻 Command Reference

#### Interaction & I/O

- `@<ai_name> <prompt>`: Send a message to `gemini`, `gpt`, `claude`, or `grok`.
- `-r <file>`, `--read <file>`: Attach file content from your data directory to the prompt.
- `-w <file>`, `--write <file>`: Save the AI's response (code-extracted) to the data directory.

#### Example:
```bash
% @claude "Refactor this function for better readability" -r utils.py -w utils_new.py
```

#### Context Management

- `@efficient [target/all] <filename>`: Loads a persona from `prompts/` and resets memory.
  - `% @efficient gpt architect.txt`
- `@scrub [target/all]`: Clears conversation history while keeping the current persona.
  - `% @scrub all`
- `exit` or `quit`: Shuts down the engines.

### 📖 The "Quad-Agent" Workflow Pattern

Leverage the unique strengths of each model in a single workflow:

1. **Design (Gemini)**:
`% @gemini "Propose a scalable architecture for a real-time chat app." -w arch.txt`
2. **Review (Claude)**:
`% @claude "Review this architecture for potential security flaws." -r arch.txt -w security_review.txt`
3. **Implement (GPT)**:
`% @gpt "Implement the server-side logic in Python based on the design and review." -r arch.txt -r security_review.txt -w server.py`

4. **Refine (Grok)**:
`% @grok "Optimize the implementation for high concurrency." -r server.py -w server_optimized.py`

Created as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.
