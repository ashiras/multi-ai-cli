# multi-ai-cli
A lightweight CLI to orchestrate Gemini, GPT, Claude, and Grok using your local files as a shared blackboard.

## 🐉 Multi-AI CLI (v0.4.1 Quad-Engine + HUD Edition)
Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room.

Multi-AI CLI is a lightweight, zero-friction command-line tool designed to seamlessly orchestrate the world's leading AI engines: **Google Gemini**, **OpenAI GPT**, **Anthropic Claude**, and **xAI Grok**.

Built on the philosophy of **"Command & Monitor"**, it allows you to iterate, design, and code at the speed of thought. By using local files as a "shared blackboard," agents can collaborate, cross-check, and implement complex architectures while you monitor the entire conversation flow in real-time through a dedicated HUD.

## ✨ Features
- **🎼 Quad-Engine Symphony**: Instantly switch between `@gemini`, `@gpt`, `@claude`, and `@grok` within the same session.
- **📺 HUD Monitoring (Live Log)**: Monitor the "AI conversation" in a separate terminal window using `tail -f`. Perfect for a professional, hacker-like development environment.
- **📂 Direct File I/O**: Use `read` and `write` keywords to let agents interact with your local files. It automatically strips Markdown code blocks (```) upon writing.
- **🎭 Persona Injection (@efficient)**: Inject system prompts (e.g., "Senior Architect", "Security Auditor") from local text files on the fly.
- **🧹 Memory Control (@scrub)**: Flush the context window of specific AIs or all at once when the conversation gets muddy.
- **🕶️ Stealth Mode**: Use the `--no-log` flag to suppress file output for private or sensitive sessions.

## 🍎 Installation (macOS / Linux)

To use `multi-ai` from any directory, follow these steps:

1. **Download the binary** from the [Latest Release](https://github.com/ashiras/multi-ai-cli/releases).
2. **Add execution permission**:
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
Note: On macOS, if you see a "developer cannot be verified" warning, go to System Settings > Privacy & Security and click "Allow Anyway".
   
## 🛠 Setup
1. Configuration File (Required)
Place a multi_ai_cli.ini file in your working directory. The CLI will not launch without it, ensuring your API keys and settings are intentionally scoped per project.

```Ini, TOML
[API_KEYS]
gemini_api_key = ...
openai_api_key = ...
anthropic_api_key = ...
grok_api_key = ...

[MODELS]
gemini_model = gemini-2.5-flash
gpt_model = gpt-4o-mini
claude_model = claude-3-5-sonnet-20241022
grok_model = grok-4-latest

[logging]
enabled = true
log_dir = logs
base_filename = chat.log
log_level = INFO

[Paths]
work_efficient = prompts
work_data = work_data
```

2. Directory Structure
Upon launch, the CLI will automatically generate the required directories based on your .ini file.

```Plaintext
your_project/
├── multi-ai_cli.ini    <-- Required config file
├── prompts/            <-- Put your persona prompts (.txt) here
└── data/               <-- AI read/write files (.py, .txt, etc.) are saved here
```

3. HUD Workflow (Optional but Recommended)

Open a second terminal window and run:

```bash
tail -f logs/chat.log
```

Now you can watch the AI's "thought process" and full responses in real-time while keeping your main CLI terminal clean for commands.

## 💻 Command Reference
Once launched, you will see the % prompt.

### Basic Interaction & I/O
- `@gemini`, `@gpt`, `@claude`, `@grok` `<prompt>`: Send a message to the specific AI.
- ... read <filename> : Appends the content of a file (from the data/ dir) to your prompt.
- ... write <filename> : Saves the AI's response directly to a file (in the data/ dir).

### Examples:

```Bash
% @gemini "Explain the root cause of this error." read error.log
% @gpt "Write a Python script for a ToDo app based on this spec." write app.py
```

### Stealth Mode

```bash
# Launch without logging to file
% python3 multi_ai_cli.py --no-log
```

### Advanced Commands
- `@efficient [target/all]` <filename>: <filename>
  - Loads a text file from the `prompts/` directory and sets it as the system prompt (persona) for the specified AI. Note: This also resets the AI's memory.
  - Example: `% @efficient gemini architect.txt`
- `@scrub [target/all]`
  - Clears the conversation history (memory) of the specified AI. Defaults to all if no target is specified.
  - Example: `% @scrub gpt`
- `exit` or `quit`
  - Shuts down the CLI.

## 📖 The "Quad-Agent" Workflow Pattern
Leverage the unique strengths of each model in a single workflow:
1. **Design (Gemini)**:
`% @gemini "Propose a scalable architecture for a real-time chat app." write arch.txt`

2. **Review (Claude)**:
`% @claude "Review this architecture for potential security flaws." read arch.txt write security_review.txt`

3. **Implement (GPT)**:
`% @gpt "Implement the server-side logic in Python based on the design and review." read arch.txt read security_review.txt write server.py`

4. **Refine (Grok)**:
`% @grok "Optimize the implementation for high concurrency." read server.py write server_optimized.py`

Created as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.
