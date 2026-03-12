## multi-ai-cli

### Transform Your Terminal into a Multi-AI Strategic Hub: The Ultimate Command-Line Tool

Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room or a powerful Unix shell filter.

**Multi-AI CLI** is a lightweight command-line hub for orchestrating multiple AI agents and external adapters. It now supports **two execution styles**:
- **Interactive REPL Mode**: A rich, stateful environment for complex, multi-step workflows.
- **Filter Mode**: A stateless, Unix-style `stdin -> AI -> stdout` pipeline mode.

It supports:
- multiple AI namespaces (`gpt`, `claude`, `gemini`, `grok`, `local`)
- adapter-style integrations such as **Figma** and **GitHub**
- artifact-based workflows using local files as a shared blackboard

With the **Agent/Engine separation**, you can bind logical agents such as `@gpt.code` or `@claude.review` to reusable engine definitions and compose them in sequential or parallel workflows.

Built on the philosophy of **"Command & Monitor"**, it allows you to iterate, design, and code at the speed of thought. By using local files as a "shared blackboard," agents can collaborate, cross-check, and implement complex architectures while you monitor the entire conversation flow in real-time through a dedicated HUD.

Now, with **v0.14.0**, Multi-AI CLI introduces a massive upgrade:
- **Dual-Mode CLI Architecture (New in v0.14.0)**: Multi-AI CLI natively supports both an Interactive REPL and a Unix-style Filter mode. Filter mode is completely stateless and shell-friendly, guaranteeing `stdout` purity for flawless pipe (`|`) integration.

*(Building on the recent v0.13.0 features)*:
- **Agent/Engine Separation Architecture**: We completely revamped how AIs are invoked. You can now define physical execution backends (`[ENGINE.*]`) and map them to logical agents with specific roles (`[AGENT.*]`). This means you can instantly switch between `@gpt`, `@gpt.code`, or `@claude.review`, each with distinct configurations but sharing the same API keys.
- **GitHub Adapter (`@github.*`)**: Native REST API integration brings your repositories, file trees, source code, and issues directly into your terminal. Seamlessly fetch GitHub data and feed it into your AI workflows without ever leaving the CLI.

This is a sophisticated AI collaboration environment for developers, designed as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.

### 🐉 Multi-AI CLI (v0.14.0: Dual-Mode Architecture Edition)

### ✨ Features

-   **☯️ Dual-Mode CLI (New in v0.14.0)**: Run as an Interactive REPL for complex workflows or as a Unix-style Filter for shell pipelines. In Filter mode, `stdin` becomes the primary input, `-m` acts as an optional instruction, `-r` provides supplemental file references, and `stdout` contains only the final AI result (with diagnostics sent to `stderr`).
-   **🧠 Agent/Engine Separation**: Decouple physical AI providers from logical roles. Define engines like `openai_main` or `claude_fast`, and map them to namespace+role combinations like `@gpt.code`, `@claude.review`, or `@gemini.plan`.
-   **🐙 GitHub Adapter (@github)**: Instantly pull repository metadata, directory trees, file contents, and issue tracking data from GitHub directly into your local workspace.
-   **🎼 Multi-Engine Symphony**: Seamlessly interact with multiple namespaces (`gpt`, `claude`, `gemini`, `grok`, `local`) in the same session.
-   **🎨 Figma Adapter (@figma)**: Bridge AI and design. Pull raw design data (`@figma.pull`) or push generated content back to Figma via a local plugin bridge (`@figma.push`).
-   **🚀 Workflow Orchestration (@sequence)**: Define and execute sophisticated multi-step AI pipelines right from your editor using **HAN Syntax**. Supports **sequential chaining (`->`)** and **parallel execution (`[ ... || ... ]`)** of AI commands, complete with artifact relay and human gates.
-   **⚙️ Shell Orchestration (@sh)**: Integrate directly with your local shell to execute commands and scripts. Capture output as JSON or markdown artifacts.
-   **📂 Smart File I/O**: Use `-r` (`--read`) to attach files as context (supported in both modes). In Interactive mode, use `-w` (`--write`) to save the raw AI response or extract pure code blocks (`-w:code`), and `-e` (`--edit`) for multi-line prompts. In Filter mode, output redirection should be handled natively by the shell (`>`).
-   **🔄 Automatic Response Continuation**: Never miss a word from your AI. Auto-detects token limits and seamlessly instructs the AI to continue exactly where it stopped.
-   **📺 HUD Monitoring (Live Log)**: Monitor the "AI conversation" in a separate terminal window using `tail -f logs/chat.log`.
-   **🎭 Persona Injection (@efficient)**: Inject system prompts (e.g., "Senior Architect") from local files to define agent behavior.
-   **🧹 Memory Control (@scrub)**: Exercise precise control over conversation history. Flush specific AI memories or all at once.

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

### 🛠 Setup

#### 1. API Keys & Environment Variables

You can set your API keys as environment variables (recommended) or inside the `.ini` file. Environment variables always take priority.

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GEMINI_API_KEY="..."
export GROK_API_KEY="..."
export FIGMA_ACCESS_TOKEN="..."
export GITHUB_TOKEN="..." # Required for @github commands
```

#### 2. Configuration File (`multi_ai_cli.ini`) - *Agent/Engine Syntax*

Place `multi_ai_cli.ini` in your working directory. The modern architecture separates physical `[ENGINE]` definitions from logical `[AGENT]` endpoints. 

*(Note: The legacy `[MODELS]` format is still supported for backward compatibility, but upgrading is highly recommended).*

```ini
[API_KEYS]
# Leave empty if using environment variables
openai_api_key = ...
anthropic_api_key = ...

[MODELS]
# Define reusable model aliases
gpt4o = gpt-4o
gpt_mini = gpt-4o-mini
claude_sonnet = claude-3-5-sonnet-20241022

[RUNTIME]
max_history_turns = 30
auto_continue_max_rounds = 5
auto_continue_tail_chars = 1200

# ==========================================
# PHYSICAL ENGINES
# ==========================================
[ENGINE.openai_main]
type = openai
api_key_ref = openai_api_key
model_ref = gpt4o
max_output_tokens = 4096

[ENGINE.claude_main]
type = anthropic
api_key_ref = anthropic_api_key
model_ref = claude_sonnet
max_output_tokens = 8192

[ENGINE.local_coder]
type = local_openai
base_url = http://localhost:11434/v1
model = qwen2.5-coder:14b
api_key = ollama

# ==========================================
# LOGICAL AGENTS (@namespace.role)
# Valid namespaces: gpt, claude, gemini, grok, local
# Valid roles: code, review, plan, doc, chat, test, image
# ==========================================
[AGENT.gpt]
engine = openai_main

[AGENT.gpt.code]
engine = openai_main

[AGENT.claude.review]
engine = claude_main

[AGENT.local.chat]
engine = local_coder

# ==========================================
# ADAPTERS
# ==========================================
[GITHUB]
# Optional: if GITHUB_TOKEN is set via env var, leave this blank
token = 
api_base_url = https://api.github.com

[FIGMA]
handoff_dir = work_data/figma_handoff

[logging]
enabled = true
log_dir = logs
log_level = INFO

[Paths]
work_efficient = prompts
work_data = data
```

#### 3. HUD Workflow (Recommended)

Open a second terminal window and run:
```bash
tail -f logs/chat.log
```

### ☯️ Dual-Mode CLI (Quick Start)

You can launch Multi-AI CLI in two different ways depending on your use case:

**1. Interactive REPL Mode**
Launch the tool without piped input to enter a stateful, rich environment:
```bash
multi-ai
```

**2. Filter Mode (Unix-style)**
Pipe data directly into the CLI to run a single-shot, stateless AI execution:
```bash
# Basic string processing
echo "apple" | multi-ai @gpt -m "Translate this to Japanese only."

# File-oriented filter
cat specification.md | multi-ai @gpt -m "Write a detailed design document based on this specification" -r existing_code.py > detailed_design.md
```

### 💻 Command Reference

#### 1. Interactive REPL Mode (AI Interaction & I/O)

The interactive mode is the rich, stateful environment where you can use all features, adapters, and file I/O flags. The basic command structure to interact with your defined agents is:

`@<namespace>[.<role>] <A1_context> [-m "message"] [-r file1...] [-w[:mode] output.txt] [-e]`

-   `@<namespace>[.<role>]`: The agent you defined in your INI file (e.g., `@gpt`, `@claude.review`, `@gpt.code`).
-   `<A1_context_words>`: Space-separated text immediately following the agent name. Acts as the primary context/title.
-   `-m "<message>"`, `--message`: Specific instruction to send to the AI.
-   `-r <file>`, `--read`: Attaches a local file from the `data` directory to the prompt (supported in both modes).
-   `-w[:mode] <file>`, `--write`: Saves the AI's response (Interactive Mode only).
    *   **`-w <file>` or `-w:raw <file>`**: Saves the ENTIRE AI response exactly as received (default).
    *   **`-w:code <file>`**: Extracts only the fenced code blocks (e.g.,) and saves them.
-   `-e`, `--edit`: Opens your default `$EDITOR` to compose a multi-line prompt (Interactive Mode only).

**Examples:**
```bash
# General query using the default GPT agent
% @gpt "Explain how asyncio works in Python." \
    -w asyncio_guide.md

# Code generation using a specific role agent, extracting only code
% @gpt.code "Write a fast fibonacci function using memoization." \
 -w:code fibo.py

# Reviewing code with Claude
% @claude.review "Check this script for security vulnerabilities." \
  -r server.py \
  -w security_report.md
```

#### 2. Filter Mode (Unix-style stdin -> AI -> stdout)

Filter mode starts automatically when `stdin` is piped or redirected. It is designed specifically for single-shot, shell-oriented AI execution.

**Syntax:**
```bash
<stdin> | multi-ai @agent [-m "instruction"] [-r file ...]
```

-   **Supported Arguments**:
    -   Exactly one `@agent` (e.g., `@gpt`, `@claude.review`)
    -   `-m "<instruction>"`: Optional instruction/prompt for the AI.
    -   `-r <file>`: Supplemental file references (attaches local files as context).
-   **Unsupported Features** (These are REPL-only):
    -   `-w`, `-e`, `@sequence`, `->`, `||`, `@sh`, `@figma.*`, `@github.*`, and other command-style interfaces.
-   **Output Contract**:
    -   **`stdout`**: Contains *only* the final AI result. Safe for piping to other shell commands or files.
    -   **`stderr`**: Contains validation errors, runtime errors, or diagnostic messages.
-   **Stateless**: Filter mode does not preserve session history across invocations.

**Examples:**

*Example 1: Primary input*
```bash
echo "This is the PRIMARY input." | multi-ai @gpt -m "Reply with exactly the primary input text."
```

*Example 2: Translation*
```bash
echo "apple" | multi-ai @gpt -m "Translate this to Japanese only."
```

*Example 3: Summarization to file (Use shell redirection instead of `-w`)*
```bash
echo "hello world" | multi-ai @gpt -m "Summarize this" > out.txt
```

*Example 4: Validation failure*
```bash
# This will fail and output an error to stderr because -w is not supported
echo "hello" | multi-ai @gpt -w out.txt
```

---

*(Note: The following adapters and orchestration features (`@github.*`, `@sh`, `@figma.*`, `@sequence`) are **Interactive-mode features** in the current implementation. Filter mode is intentionally limited to direct AI agent execution only.)*

#### GitHub Adapter (`@github.*`) - REPL Only

Integrate GitHub repositories directly into your terminal workflow.

All commands support `-w`, so fetched outputs can be saved locally and reused as inputs (`-r`) for downstream AI agents.

**Note:** In the current implementation, `@github.*` commands require a GitHub token even for public repositories.

Supported commands:

- `@github.repo` — repository metadata
- `@github.tree` — directory listing for the root or a specific path
- `@github.file` — file content read
- `@github.issue` — single issue detail (**issue-only; PRs are not supported in v1**)
- `@github.issues` — issue list (PR entries are filtered out)

Examples:

```bash
% @github.repo --repo "ashiras/multi-ai-cli"
% @github.tree --repo "ashiras/multi-ai-cli" --path "src/"
% @github.file --repo "ashiras/multi-ai-cli" --path "README.md" -w remote_readme.md
% @github.issue --repo "ashiras/multi-ai-cli" --number 40 -w issue_40.md
% @github.issues --repo "ashiras/multi-ai-cli" --state open --limit 20
```

Requires the `GITHUB_TOKEN` environment variable or INI configuration.

#### Shell Orchestration (`@sh`) - REPL Only

Execute shell commands and scripts directly from the CLI.

`@sh "<command_string>" [-r <script>] [-w <output>] [--shell]`

-   **Direct Command**: `@sh "ls -la"`
-   **Run Local Script**: `@sh -r analyze_logs.py -w report.md` (Auto-detects runner: `python3`, `bash`, `node`, etc.)
-   **Capture Artifacts**: Use `-w <file.json>` to capture exit code, stdout, and stderr as structured JSON, or `.md` for a human-readable text artifact.
-   **Shell Mode**: Use `--shell` for complex commands involving pipes (`|`) or env variables. *(Warning: Allows shell injection, use with caution).*

#### Figma Adapter (`@figma.*`) - REPL Only

-   **`@figma.pull`**: Fetch design data.
    `@figma.pull --file <key> [--node <id> | --page <name>] -w design.json`
-   **`@figma.push`**: Send local content to a Figma plugin bridge.
    `@figma.push -r spec.md --file <key> --page "Designs" --frame "Button"`

#### Context Management - REPL Only

-   `@efficient [target/all] <filename>`: Loads a persona (system prompt) from the `prompts/` dir and resets the memory for the target agent.
-   `@scrub [target/all]`: Clears conversation history while keeping the current persona intact.
-   `exit` / `quit`: Shuts down all engines and exits the CLI.

### 🚀 Workflow Orchestration with @sequence (HAN Syntax)

Build sophisticated, multi-agent pipelines using the `@sequence -e` command. It opens your editor, allowing you to define complex interactions using **HAN (Human-Agent-Network) Syntax**. *(Interactive Mode Only)*.

-   **`->`**: Sequential execution (downstream consumes upstream output).
-   **`[ ... || ... ]`**: Parallel execution (run multiple agents simultaneously).
-   **Artifact Relay**: Files written (`-w`) by one step can be read (`-r`) by the next step instantly.

**Example Pipeline (Editor View):**
```text
# Step 1: GPT plans the architecture based on a GitHub issue
@github.issue --repo "owner/repo" --number 12 -w issue.md
-> @gpt.plan "Create a technical specification based on this issue." -r issue.md -w spec.md

# Step 2: Parallel Code Generation and Design Check
-> [
      @gpt.code "Write the Python implementation based on spec." -r spec.md -w:code app.py
   || @claude.review "Check the spec for security flaws." -r spec.md -w security_review.md
   ]

# Step 3: Local Linter Check
-> @sh "flake8 app.py" -w lint_report.md

# Step 4: Final Refinement
-> @gpt.code "Fix linting errors and apply security review suggestions." -r app.py -r security_review.md -r lint_report.md -w:code app_final.py
```

### Human-in-the-loop pause (v0.13.2)

Use `@pause` to stop a pipeline and manually review generated files before continuing.

```text
@gpt "Summarize issue.md into spec.md" -r issue.md -w spec.md
-> @pause
-> @claude "Create design.md from spec.md" -r spec.md -w design.md
```

### ⚠️ Notes and Limitations (Dual-Mode CLI)

- **Filter Mode Minimalism**: Filter mode is intentionally minimal. It supports only direct AI agents (`@gpt`, `@claude`, etc.). Orchestration, parallel execution (`||`), sequence chaining (`->`), and adapters (`@sh`, `@github.*`, `@figma.*`) are reserved for the Interactive REPL mode.
- **No Stateful History in Filter Mode**: Every execution via pipe/redirect is a clean slate. Session memory is not preserved across filter mode invocations.
- **Output Redirection**: Do not use the `-w` flag in Filter mode. All output formatting and file redirection is intended to be handled natively by your shell (e.g., `> file.txt`).
- **Mode Detection**: Mode switching is currently implicit, based on `sys.stdin.isatty()`. Explicit mode flags (e.g., `--interactive`, `--filter`) are not supported yet.
- **Testing Filter Mode**: For testing the robustness of Filter Mode integration, you can use the built-in checker script: `scripts/code_dual-mode_checker.sh`.

### 📝 Appendix: Definition of HAN Syntax (Human-Agent-Network)

HAN is a domain-specific notation designed to describe the flow of information and decision-making between human users and AI agents.

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
## ...   block label line (semantic; attaches to the following "[ ... ]" block)

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