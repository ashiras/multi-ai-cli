# multi-ai-cli
A lightweight CLI to orchestrate Gemini and GPT using your local files as a shared blackboard.

## 🐉 Multi-AI CLI (Beta)
Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room.

Multi-AI CLI is a lightweight, zero-friction command-line tool designed to seamlessly orchestrate Google Gemini and OpenAI GPT. Instead of relying on heavyweight frameworks, it uses your local files as a "shared blackboard" (Bus) for AI agents to collaborate.

Built on the philosophy of Redundancy and Cross-checking rather than rigid roles, it allows you to iterate, design, and code at the speed of thought directly from your terminal.

## ✨ Features
- 🧠 Dual-Headed Engine: Instantly switch between @gemini (e.g., for reasoning/architecture) and @gpt (e.g., for coding/implementation) within the same session.
- 📂 Direct File I/O: Use read and write keywords to let agents interact with your local files directly. It automatically strips Markdown code blocks (```) upon writing.
- 🎭 Persona Injection (@efficient): Inject system prompts (e.g., "Grumpy Scholar", "Senior Dev") from local text files on the fly.
- 🧹 Memory Control (@scrub): Flush the context window of a specific AI (or both) when the conversation gets muddy, without restarting the CLI.
- 📁 Clean Workspace: Strictly separates configuration files from your working data, keeping your project root pristine.

## 🍎 Installation (macOS / Linux)

To use `multi-ai` from any directory, follow these steps:

1. **Download the binary** from the [Latest Release](https://github.com/YOUR_USERNAME/YOUR_REPO/releases).
2. **Add execution permission**:
```bash
chmod +x multi-ai
```
3. Move to your local bin directory:
```bash
sudo mv multi-ai /usr/local/bin/
```
4. Verify installation:
Open a new terminal and type
```bash
multi-ai
```
Note: On macOS, if you see a "developer cannot be verified" warning, go to System Settings > Privacy & Security and click "Allow Anyway".
   
## 🛠 Setup
1. Configuration File (Required)
Place a multi_ai_cli.ini file in your working directory. The CLI will not launch without it, ensuring your API keys and settings are intentionally scoped per project.


```Ini, TOML
# Example: multi_ai_cli.ini
[API_KEYS]
gemini_api_key = YOUR_GEMINI_API_KEY
openai_api_key = YOUR_OPENAI_API_KEY

[MODELS]
gemini_model = gemini-2.0-flash
gpt_model = gpt-4o-mini

[Paths]
# Directories will be created automatically if they don't exist
work_efficient = prompts  # Directory for persona text files
work_data = data          # Directory for I/O files
```

2. Directory Structure
Upon launch, the CLI will automatically generate the required directories based on your .ini file.

```Plaintext
your_project/
├── multi-ai_cli.ini    <-- Required config file
├── prompts/            <-- Put your persona prompts (.txt) here
└── data/               <-- AI read/write files (.py, .txt, etc.) are saved here
```

## 💻 Command Reference
Once launched, you will see the % prompt.

### Basic Interaction & I/O
- @gemini <prompt> : Send a prompt to Gemini.
- @gpt <prompt> : Send a prompt to GPT.
- ... read <filename> : Appends the content of a file (from the data/ dir) to your prompt.
- ... write <filename> : Saves the AI's response directly to a file (in the data/ dir).

### Examples:

```Bash
% @gemini "Explain the root cause of this error." read error.log
% @gpt "Write a Python script for a ToDo app based on this spec." write app.py
```

### Advanced Commands
- @efficient [gemini/gpt/all] <filename>
  - Loads a text file from the `prompts/` directory and sets it as the system prompt (persona) for the specified AI. Note: This also resets the AI's memory.
  - Example: `% @efficient gemini architect.txt`
- @scrub [gemini/gpt/all]
  - Clears the conversation history (memory) of the specified AI. Defaults to all if no target is specified.
  - Example: `% @scrub gpt`
- `exit` or `quit`
  - Shuts down the CLI.

## 📖 The "Dual-Agent" Workflow Pattern
Here is a practical example of human-in-the-loop orchestration, utilizing the strengths of different models.

1. Set up personas:

```Bash
% @efficient gemini architect.txt
% @efficient gpt coder.txt
```

2. Make Gemini design the architecture:

```Bash
% @gemini "Propose a database schema for a SQLite ToDo app." write schema.txt
```

3. Pass the design to GPT for implementation:

```Bash
% @gpt "Implement the Python code strictly following this schema. No markdown explanations." read schema.txt write app.py
```

4. Hit a bug? Scrub GPT's memory and make it retry from scratch:

```Bash
% @scrub gpt
% @gpt "Forget the previous code. Rewrite app.py simpler." read schema.txt write app.py
```

Created as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.
