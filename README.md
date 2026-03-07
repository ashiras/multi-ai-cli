## multi-ai-cli

### Transform Your Terminal into a Multi-AI Strategic Hub: The Ultimate Command-Line Tool

Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room.

**Multi-AI CLI** is a lightweight, zero-friction command-line tool designed to seamlessly orchestrate the world's leading AI engines: **Google Gemini**, **OpenAI GPT**, **Anthropic Claude**, **xAI Grok**, and now **Local AI models** (e.g., Ollama).

Built on the philosophy of **"Command & Monitor"**, it allows you to iterate, design, and code at the speed of thought. With the introduction of **powerful multi-step workflow orchestration** in v0.9.0, you can now automate complex interactions across AIs. Furthermore, v0.9.1 brought a fundamental shift in I/O behavior towards "UNIX-like predictability," refining how AI responses are saved. By using local files as a "shared blackboard," agents can collaborate, cross-check, and implement complex architectures while you monitor the entire conversation flow in real-time through a dedicated HUD.

Now, with **v0.11.0**, Multi-AI CLI introduces **native shell orchestration (`@sh`)** for direct interaction with your local environment, the ability to integrate **local AI models (Ollama)** for enhanced privacy and customization, and **automatic response continuation** to seamlessly handle lengthy AI outputs. This is a sophisticated AI collaboration environment for developers, designed as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.

### 🐉 Multi-AI CLI (v0.11.0: Local AI, Shell Orchestration, Auto-Continue Edition)

### ✨ Features

-   **🎼 Multi-Engine Symphony (5+ AI Engines)**: Instantly switch between `@gemini`, `@gpt`, `@claude`, `@grok`, and the new **`@local`** for self-hosted models, all within the same session.
-   **📺 HUD Monitoring (Live Log)**: Monitor the "AI conversation" in a separate terminal window using `tail -f`. Keep your workspace clean and professional.
-   **📂 Smart File I/O (v0.9.1: Raw-by-Default Write)**: Use `-r` (`--read`) and `-w` (`--write`) flags to interact with local files.
    *   Supports **multiple `-r` inputs**, allowing you to attach several files to your prompt.
    *   Features a **fixed prompt construction priority** (`A1 > Message > Editor > Files`) for consistent and predictable AI context delivery.
    *   The `-w` flag **saves the FULL AI response without modification by default**. The `:code` modifier must be explicitly used to extract code blocks. Includes built-in protection against directory traversal.
-   **🔄 Automatic Response Continuation**: Never miss a word from your AI. If an AI's response hits its maximum token limit, the CLI will automatically detect it and instruct the AI to `continue exactly from where you stopped`, providing seamless, uninterrupted output for lengthy tasks.
-   **🚀 Workflow Orchestration (@sequence)**: Define and execute sophisticated multi-step AI pipelines right from your editor using **HAN Syntax**. Supports **sequential chaining (`->`)** and **parallel execution (`[ ... || ... ]`)** of AI commands, complete with artifact relay and human gates.
-   **⚙️ Shell Orchestration (@sh)**: Integrate directly with your local shell to execute commands and scripts.
    *   Run arbitrary shell commands with `@sh "command"`.
    *   Execute local scripts (Python, Bash, Ruby, Node, etc.) directly from your `data` directory using `@sh -r script.py`.
    *   Capture command output as structured JSON or human-readable text using `-w output.json` or `-w output.md`.
    *   Use `--shell` for complex commands involving pipes, environment variable expansion, or shell-specific features.
-   **🎭 Persona Injection (@efficient)**: Inject system prompts (e.g., "Senior Architect", "Security Auditor") from local text files, effectively defining the AI's role and behavior.
-   **🧹 Memory Control (@scrub)**: Exercise precise control over conversation history. Flush specific AI memories or all at once.
-   **🔒 Security First**: Built-in protection against directory traversal and secure API key management via environment variables.
-   **🕶️ Stealth Mode**: Use the `--no-log` flag to suppress file output for sensitive sessions.

### 🍎 Installation (macOS / Linux)
1.  Download the binary from the [Latest Release](https://github.com/ashiras/multi-ai-cli/releases/).
2.  Add execution permission:
    ```bash
    chmod +x multi-ai
    ```
3.  Move to your local bin directory:
    ```bash
    sudo mv multi-ai /usr/local/bin/
    ```
4.  Verify installation:
    ```bash
    multi-ai --version
    ```

Note: On macOS, if prompted with a security warning, go to System Settings > Privacy & Security and click "Allow Anyway".

### 🛠 For Developers (Source Installation)
If you prefer to run from source or want to contribute to the project, use [uv](https://github.com/astral-sh/uv) for a seamless setup:

1. Clone the repository:
   ```bash
   git clone git@github.com:ashiras/multi-ai-cli.git
   cd multi-ai-cli
   ```
2. Sync dependencies and create a virtual environment:
   ```Bash
   uv sync
   ```

3. Run the CLI directly:
   ```Bash
   uv run multi-ai --version
   ```

Note: Using `uv` ensures that all linter (Ruff) and type-check (mypy) settings are applied exactly as configured in `pyproject.toml`.

### 🛠 Setup

#### 1. API Keys & Environment Variables

You can set your API keys as environment variables (recommended) or in the `.ini` file. Environment variables take priority.

```ini
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GROK_API_KEY="..."
export LOCAL_API_KEY="ollama" # Usually 'ollama' for default Ollama setups, can be empty
```

#### 2. Configuration File (`multi_ai_cli.ini`)

Place this file in your working directory to define models, paths, and advanced settings.

```ini
[API_KEYS]
# Leave empty if using environment variables
gemini_api_key = ...
openai_api_key = ...
anthropic_api_key = ...
grok_api_key = ...
local_api_key = ollama # Usually 'ollama' or empty for local models

[MODELS]
gemini_model = gemini-2.5-flash
gpt_model = gpt-4o-mini
claude_model = claude-3-5-sonnet-20241022
grok_model = grok-4-latest
local_model = qwen2.5-coder:14b # Example for Ollama model
max_history_turns = 30

# Optional: Set max output tokens for each model to control response length
# If the AI hits this limit, auto-continuation will trigger.
gemini_max_output_tokens = 8192
openai_max_tokens = 4096
claude_max_tokens = 8192
grok_max_tokens = 4096
local_max_tokens = 4096

# Automatic Response Continuation Settings
# How many times the CLI should automatically ask the AI to continue
auto_continue_max_rounds = 5
# How many characters from the end of the previous output to send as context
# to help the AI continue accurately.
auto_continue_tail_chars = 1200

[LOCAL]
# Base URL for local AI models, e.g., Ollama or other OpenAI-compatible servers
base_url = http://localhost:11434/v1
# Default model name for the @local engine
model = qwen2.5-coder:14b

[logging]
enabled = true
log_dir = logs
base_filename = chat.log
log_level = INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
max_bytes = 10485760 # 10MB
backup_count = 5

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

#### Interaction & I/O (v0.9.1 Update)

The basic command structure for interacting with an AI is as follows:

`@<ai_name> <A1_context_words> [-m "message"] [-r file1 -r file2 ...] [-w[:mode] output.txt] [-e]`

-   `@<ai_name>`: Specifies the AI engine you want to interact with (`@gemini`, `@gpt`, `@claude`, `@grok`, `@local`).
-   `<A1_context_words>`: Any space-separated text immediately following the AI's name, up to the first flag (`-`). This serves as the "title" or primary context for your prompt.
-   `-m "<message>"`, `--message "<message>"`: Specifies a concrete message body to send to the AI. Use quotes for multi-word messages.
-   `-r <file>`, `--read <file>`: Attaches the content of a file from your configured `data` directory to the prompt. **Multiple `-r` flags are supported**, each adding a file's content to the prompt.
-   `-w[:mode] <file>`, `--write[:mode] <file>`: Saves the AI's response to the `data` directory. Only the *last* `-w` flag will take effect if specified multiple times. **As of v0.9.1, the behavior of the `-w` flag has been changed.**

    *   **`-w <file>` or `-w:raw <file>` (Raw by Default)**:
        *   This is the new default behavior. It **saves the ENTIRE AI response exactly as received, without any modification or extraction.**
        *   Ideal for updating `README.md` files, generating documentation, or when you want to preserve all the AI's output, including explanations and context alongside any code.
        *   The `:raw` modifier is an explicit alias to clarify this unmodified saving behavior.
    *   **`-w:code <file>` (Code Block Extraction)**:
        *   This mode **extracts only the content of fenced code blocks** (e.g., ```python ... ```) from the AI's response and saves it to the specified file.
        *   Extremely useful when you only need the pure code from an AI's output, stripping away any explanatory prose.
        *   If multiple code blocks are present, they will be concatenated.
        *   If the response contains no fenced code blocks, it will fall back to saving the original text entirely.
-   `-e`, `--edit`: Opens your default `$EDITOR` (or `vi`) to compose a multi-line prompt.

#### Prompt Construction Priority

When combining different input methods, the final prompt sent to the AI is constructed in a fixed order, regardless of their position on the command line:

1.  **A1 (Context/Title)**: Everything from the command start to the first switch (`-`). This sets the primary intent or theme of your prompt.
2.  **Message (`-m`)**: Content following the `-m` / `--message` flag. Useful for specific instructions or questions.
3.  **Editor (`-e`)**: Content captured via the `-e` / `--edit` flag. Ideal for longer, more complex instructions or requirements.
4.  **Files (`-r`)**: Content of all specified files. Each file's content is clearly delimited (e.g., `--- [File: filename] ---`), helping the AI understand which part originated from which file.

#### Example AI Interactions:

```bash
# For updating entire documents (-w:raw behaves the same as -w)
% @claude "Update the installation steps in README.md, reflecting the v0.11.0 changes, including @local and @sh." -r README.md -w:raw README_updated.md

# For generating a Python script and extracting only the code
% @gpt "Write a fast fibonacci function in Python using recursion with memoization." -w:code fibonacci.py

# Combining multiple files, messages, and A1 context to send to GPT
% @gpt "Refactor this function for better readability" -m "Consider performance implications too." -r utils.py -r tests/test_utils.py -w utils_new.py

# Using the local Ollama model to summarize a document
% @local "Summarize this long technical document for a non-technical audience." -r long_doc.txt -w summary.md
```

#### Shell Orchestration (`@sh`) - NEW in v0.11.0

The `@sh` command allows you to execute shell commands and scripts directly from the CLI, seamlessly integrating local tools and workflows with your AI interactions. This is invaluable for automating tasks, generating data for AI processing, or implementing AI-generated code.

**Basic Usage:**
`@sh "<command_string>"`
`@sh -r <script_file>`
`@sh "<command_string>" -w <output_file>`
`@sh --shell "<complex_command_with_pipes>"`

**Key Features & Flags:**

-   **Direct Command Execution**:
    *   `@sh "ls -la"`: Executes `ls -la`. Arguments are safely parsed via `shlex.split` by default, preventing shell injection unless `--shell` is used.
    *   If `--shell` is specified (`@sh --shell "echo $HOME | grep user"`), the command string is passed directly to the system shell (e.g., `bash -c "..."`), enabling pipes, environment variable expansion, and other shell-specific features. Use with caution.
-   **Run Local Script (`-r <file>`, `--read <file>`)**:
    *   `@sh -r my_script.py`: Executes a script located in your configured `data` directory.
    *   The CLI automatically detects the correct runner based on the file extension.
    *   **Supported Runners**:
        *   `.py`: `python3`
        *   `.sh`: `bash`
        *   `.rb`: `ruby`
        *   `.js`: `node`
        *   `.ts`: `npx ts-node`
        *   `.pl`: `perl`
        *   `.lua`: `lua`
        *   `.R`, `.r`: `Rscript`
-   **Capture Output Artifact (`-w <file>`, `--write <file>`)**:
    *   `@sh "git status" -w git_status.md`: Captures the `stdout` and `stderr`, exit code, and duration of the command.
    *   **Intelligent Output Formatting**:
        *   If the output file ends with `.json` (e.g., `result.json`), the artifact will be saved as structured JSON.
        *   Otherwise (e.g., `.txt`, `.md`), it will be saved as a human-readable Markdown-like text artifact, clearly showing command, status, output, and errors.
-   **Security**: By default, commands are executed safely via `shlex.split` without involving a shell. The `--shell` flag explicitly enables shell execution, which is powerful but requires careful use to prevent command injection. All file paths for `-r` and `-w` are securely resolved within designated `data` directories.

**Examples:**

```bash
# Execute a simple command and print output to console
% @sh "pwd"

# Run a Python script and capture its output to a Markdown file
% @sh -r analyze_logs.py -w log_analysis.md

# Run a Python script that takes an argument, and capture output as JSON
% @sh "python3 my_tool.py --config prod" -w tool_output.json

# Execute a complex shell command with pipes and environment variable expansion
# WARNING: Use --shell with caution, as it enables shell interpretation.
% @sh --shell "grep -r 'TODO' . | wc -l" -w todo_count.txt

# Integrate @sh into a sequence (see @sequence section below)
# This allows AI to generate code, then @sh to run it, and AI to review results.
```

#### Automatic Response Continuation - NEW in v0.11.0

This feature enhances your workflow by automatically managing cases where an AI's response is truncated due to `max_tokens` limits. Instead of receiving an incomplete answer, the CLI will:

1.  Detect that the AI's response was cut short (e.g., due to `length` stop reason or `MAX_TOKENS`).
2.  Send a follow-up prompt to the AI, instructing it to `continue EXACTLY from where you stopped`. This prompt includes a "tail" of the last part of the AI's output to help the AI maintain context and seamless flow.
3.  Concatenate the new segment with the previous output.
4.  Repeat this process for a configurable number of `auto_continue_max_rounds` until the AI indicates it has finished or the round limit is reached.

This means you can request very long code blocks, detailed explanations, or extensive documentation without manually prompting "continue" multiple times.

**Configuration**:
Adjust `auto_continue_max_rounds` and `auto_continue_tail_chars` in your `multi_ai_cli.ini` file to fine-tune this behavior.

#### Context Management

-   `@efficient [target/all] <filename>`: Loads a persona (system prompt) from `prompts/` and resets the memory for the target AI.
    -   `% @efficient gpt architect.txt`
    -   `% @efficient all security_expert.txt`
-   `@scrub [target/all]`: Clears conversation history while keeping the current persona intact.
    -   `% @scrub all`
    -   `% @scrub claude`
-   `exit` or `quit`: Shuts down all AI engines and exits the CLI.

### 🚀 Workflow Orchestration with @sequence (HAN Syntax)

Move beyond single commands to build sophisticated, multi-agent pipelines. The `@sequence -e` command lets you define a series of AI interactions and shell commands in your preferred editor, leveraging **HAN (Human-Agent-Network) Syntax** for powerful automation.

**Key Concepts:**

-   **Sequential Execution (`->`)**: Chain commands where the output of one step can become the input for the next. The sequence proceeds step-by-step.
-   **Parallel Execution (`[ ... || ... ]`)**: Run multiple AI tasks or shell commands simultaneously within a single step. Their combined outputs (typically via `-w` files) can then be fed into a subsequent step for integration or synthesis.
-   **Artifact Relay**: Files generated by `-w` in one step are immediately available for reading by subsequent AIs or `@sh` commands via `-r`. This enables seamless collaboration across the pipeline.
-   **Cascade Stop**: If any step or parallel task within a sequence fails, the entire pipeline halts, preventing wasted resources or incorrect downstream processing.
-   **Human Gate (H)**: While not an explicit command in the CLI, the editor integration itself serves as the "Human Gate". You control when to run the sequence and can modify it between runs to introduce human judgment, approval, or editing.

**HAN Syntax Example (Editor View):**

This example demonstrates a complex workflow: Gemini designs, GPT and Grok review in parallel, Claude integrates the feedback, `@sh` executes a linting check on the generated code, and finally GPT implements the code.

```Plaintext
# Step 1: Design Phase - Gemini proposes an architecture and writes it to a file.
@gemini "Propose a scalable architecture for a real-time chat app. Focus on microservices and cloud deployment." -w arch_design.md

-> # Step 2: Parallel Review - GPT and Grok review the design concurrently.
   [
       @gpt  "Review arch_design.md for security flaws and suggest improvements." -r arch_design.md -w gpt_security_review.md
    || @grok "Review arch_design.md for efficiency and scalability bottlenecks. Focus on cost optimization." -r arch_design.md -w grok_efficiency_review.md
   ]

-> # Step 3: Integration - Claude integrates reviews and provides a refined design.
   @claude "Integrate the security and efficiency reviews into the original architecture. Output a final, refined architecture."
          -r arch_design.md -r gpt_security_review.md -r grok_efficiency_review.md -w final_arch.md

-> # Step 4: Code Implementation - GPT starts implementing a core component based on the final design.
   @gpt "Implement the server-side logic in Python for a user authentication microservice based on final_arch.md."
        -r final_arch.md -w auth_service.py

-> # Step 5: Linting Check - Use @sh to run a linter on the generated code.
   @sh "pylint auth_service.py" -r auth_service.py -w lint_report.md

-> # Step 6: Code Refinement - GPT reviews the lint report and refines the code.
   @gpt "Review lint_report.md and refactor auth_service.py to address any issues. Provide the refined Python code."
        -r auth_service.py -r lint_report.md -w:code auth_service_refined.py
```

This powerful capability allows you to orchestrate sophisticated AI workflows, managing complex interactions, artifact handoffs, and local shell commands with simple, human-readable syntax.

### 📝 Appendix: Definition of HAN Syntax (Human-Agent-Network)

HAN is a domain-specific notation designed to describe the flow of information and decision-making between human users and AI agents. It prioritizes clarity and flexibility for multi-agent workflows.

```Plaintext
H        human gate (sets constraints / approves / decides)
A        agent step (LLM + tools, e.g., @gemini, @gpt, @sh)
N<...>   named node / label (use when you want labels other than H or A)

->       dependency / composition (downstream consumes upstream output)
||       independent parallelism (redundant interpretation paths)
[ ... ]  block (grouping; becomes parallel when it contains top-level "||")

::       NOTE annotation (non-semantic; parsed token)
{...}    role tag / label (annotation only; does not change semantics)
- ...    node spec line (semantic; attaches to a node declaration)
# ...    comment line (non-semantic; for humans only; may label a branch)
## ...   block label line (semantic; attaches to the following "[ ... ]" block

Normalization (layout):
- Newlines and indentation do not change semantics.
- Use "->" for sequential composition and "[ ... || ... ]" for parallel branches.

Blocks and branch labels:
- A "[ ... ]" always forms a single block (atomic grouping unit).
- If a block contains top-level "||", each "||"-separated branch is treated as one atomic unit/block
  (even if the branch contains internal "->" sequences).
- A "# ..." line labels a branch ONLY when it appears immediately before that branch block.
  Any other "# ..." is ignored (non-semantic).

Node Specs ("- ..."):
- A node spec block is one or more consecutive "- ..." lines that immediately follow
  a single node declaration line: H / A / N<...> (optionally with "::..." and/or "{...}").
- A "single node declaration line" MUST NOT contain any of: "->", "||", "[", "]".
  (If you want specs for a node inside a sequence, split the node onto its own line.)
- A "- ..." line not attached to a valid node declaration is a syntax error.

NOTE parsing ("::"):
- "::" introduces an inline NOTE token.
- The NOTE payload is captured by *minimal match* up to (but not including) the earliest of:
  "->", "||", "[", "]", or a newline.
- "::" does not change semantics (annotation only).
- If multiple "::" appear on the same line, each NOTE is parsed independently with the same rule.

Block Labels ("## ..."):
- A block label is a "## ..." line that immediately precedes a "[" block (ignoring blank lines/indentation).
- The label attaches to the entire "[" ... "]" block as a whole (not to the first node inside).
- A "## ..." line not followed by a "[" block is a syntax error (strict) or ignored (weak).
```
