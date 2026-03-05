## multi-ai-cli

### Transform Your Terminal into a Multi-AI Strategic Hub: The Ultimate Command-Line Tool

Break free from the browser copy-paste hell. Turn your terminal into a multi-agent AI war room.

**Multi-AI CLI** is a lightweight, zero-friction command-line tool designed to seamlessly orchestrate the world's leading AI engines: **Google Gemini**, **OpenAI GPT**, **Anthropic Claude**, and **xAI Grok**.

Built on the philosophy of **"Command & Monitor"**, it allows you to iterate, design, and code at the speed of thought. With the introduction of **powerful multi-step workflow orchestration** in v0.9.0, you can now automate complex interactions across AIs. Furthermore, v0.9.1 brings a fundamental shift in I/O behavior towards "UNIX-like predictability," refining how AI responses are saved. By using local files as a "shared blackboard," agents can collaborate, cross-check, and implement complex architectures while you monitor the entire conversation flow in real-time through a dedicated HUD.

This is a sophisticated AI collaboration environment for developers, designed as a lightweight, hacker-friendly alternative to heavyweight Multi-Agent frameworks.

### 🐉 Multi-AI CLI (v0.9.1 Raw-by-Default Write Mode Edition)

### ✨ Features

-   **🎼 Quad-Engine Symphony**: Instantly switch between `@gemini`, `@gpt`, `@claude`, and `@grok` within the same session.
-   **📺 HUD Monitoring (Live Log)**: Monitor the "AI conversation" in a separate terminal window using `tail -f`. Keep your workspace clean and professional.
-   **📂 Smart File I/O (v0.9.1: Raw-by-Default Write)**: Use `-r` (`--read`) and `-w` (`--write`) flags to interact with local files.
    *   Supports **multiple `-r` inputs**, allowing you to attach several files to your prompt.
    *   Features a **fixed prompt construction priority** (`A1 > Message > Editor > Files`) for consistent and predictable AI context delivery.
    *   The `-w` flag **saves the FULL AI response without modification by default**. The `:code` modifier must be explicitly used to extract code blocks. Includes built-in protection against directory traversal.
-   **🚀 Workflow Orchestration (@sequence)**: Define and execute sophisticated multi-step AI pipelines right from your editor using **HAN Syntax**. Supports **sequential chaining (`->`)** and **parallel execution (`[ ... || ... ]`)** of AI commands, complete with artifact relay and human gates.
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
claude_model = claude-3-5-sonnet-20241022 # Updated default model example
grok_model = grok-4-latest
max_history_turns = 30
claude_max_tokens = 8192 # Added for Claude's max_tokens (if desired)

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

#### Interaction & I/O (v0.9.1 Update)

The basic command structure for interacting with an AI is as follows:

`@<ai_name> <A1_context_words> [-m "message"] [-r file1 -r file2 ...] [-w[:mode] output.txt] [-e]`

-   `@<ai_name>`: Specifies the AI engine you want to interact with (`@gemini`, `@gpt`, `@claude`, `@grok`).
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

#### Example:

```bash
# For updating entire documents (-w:raw behaves the same as -w)
% @claude "Update the installation steps in README.md, reflecting the v0.9.1 changes." -r README.md -w:raw README.md

# For generating a Python script and extracting only the code
% @gpt "Write a fast fibonacci function in Python using recursion with memoization." -w:code fibonacci.py

# Combining multiple files, messages, and A1 context to send to GPT
% @gpt "Refactor this function for better readability" -m "Consider performance implications too." -r utils.py -r tests/test_utils.py -w utils_new.py
```
This last command will assemble the prompt with: "Refactor this function for better readability" (A1) + "Consider performance implications too." (Message) + the content of `utils.py` and `tests/test_utils.py` (Files), send it to Claude, and save the refactored code to `utils_new.py`.

#### Context Management

-   `@efficient [target/all] <filename>`: Loads a persona (system prompt) from `prompts/` and resets the memory for the target AI.
    -   `% @efficient gpt architect.txt`
-   `@scrub [target/all]`: Clears conversation history while keeping the current persona intact.
    -   `% @scrub all`
-   `exit` or `quit`: Shuts down all AI engines and exits the CLI.

### 🚀 Workflow Orchestration with @sequence (HAN Syntax)

Move beyond single commands to build sophisticated, multi-agent pipelines. The `@sequence -e` command lets you define a series of AI interactions in your preferred editor, leveraging **HAN (Human-Agent-Network) Syntax** for powerful automation.

**Key Concepts:**

-   **Sequential Execution (`->`)**: Chain commands where the output of one step can become the input for the next. The sequence proceeds step-by-step.
-   **Parallel Execution (`[ ... || ... ]`)**: Run multiple AI tasks simultaneously within a single step. Their combined outputs (typically via `-w` files) can then be fed into a subsequent step for integration or synthesis.
-   **Artifact Relay**: Files generated by `-w` in one step are immediately available for reading by subsequent AIs via `-r`. This enables seamless collaboration across the pipeline.
-   **Cascade Stop**: If any step or parallel task within a sequence fails, the entire pipeline halts, preventing wasted resources or incorrect downstream processing.
-   **Human Gate (H)**: While not an explicit command in the CLI, the editor integration itself serves as the "Human Gate". You control when to run the sequence and can modify it between runs to introduce human judgment, approval, or editing.

**HAN Syntax Example (Editor View):**

This example demonstrates a complex workflow: Gemini designs, GPT and Grok review in parallel, Claude integrates the feedback, and finally GPT implements the code.

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
```

This powerful new capability allows you to orchestrate sophisticated AI workflows, managing complex interactions and artifact handoffs with simple, human-readable syntax.

### 📝 Appendix: Definition of HAN Syntax (Human-Agent-Network)

HAN is a domain-specific notation designed to describe the flow of information and decision-making between human users and AI agents. It prioritizes clarity and flexibility for multi-agent workflows.

```Plaintext
H        human gate (sets constraints / approves / decides)
A        agent step (LLM + tools)
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