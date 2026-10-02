# portable-agent-chat

A minimal interactive chat CLI for AI agents provided through `multi-ai-cli`.

This tool starts a chat session with a specified agent, lets you enter multi-line prompts, and supports simple file-related commands for reading prompt context from files and writing assistant responses to files.

## Features

- Start an interactive chat session with a selected agent
- Multi-line prompt input powered by `prompt_toolkit`
- Include file contents in the next prompt
- Write the last response to a new file
- Write the next response directly to a new file

## Requirements

This project depends on:

- Python
- `multi-ai-cli`
- `prompt_toolkit`

It also expects your agent configuration and API keys to be set up through `multi-ai-cli`.

## Installation

Install dependencies with your preferred environment manager.

If you use `uv`, a typical setup is:

```bash
uv sync
```

## Usage

Start the chat CLI by specifying an agent name:

```bash
portable-chat --agent <agent-name>
```

Example:

```bash
portable-chat --agent gpt4
```

When the program starts, it shows:

```text
portable-chat
agent: <agent-name>
```

Then you can begin entering prompts at the `% ` prompt.

## Input behavior

Input is handled by `prompt_toolkit` in multiline mode.

Key bindings:

- `Enter` = insert a newline
- `Alt-Enter` = send the current prompt
- `Esc` → `Enter` = send the current prompt
- `Ctrl-C` = discard the current input
- `Ctrl-D` = exit if the current input is empty

## Commands

In addition to normal prompts, the CLI supports a few colon-prefixed commands.

### `:r <path>`

Queue a file to be read and included in the **next** prompt.

Example:

```text
:r notes.txt
```

When you send your next prompt, the file content is prepended in this form:

```text
--- file: notes.txt ---
<file content>
--- end file: notes.txt ---
```

Notes:

- The file must exist
- The path must point to a regular file
- Queued files are cleared after the next send attempt, even if the model call fails

### `:w <path>`

Write the **last assistant response** to a new file.

Example:

```text
:w answer.md
```

Notes:

- This only works after at least one assistant response has been received
- The destination file must not already exist

### `:o <path>`

Queue an output path for the **next assistant response**.

Example:

```text
:o next-answer.md
```

After the next successful prompt, the response is written to that file automatically.

Notes:

- The destination file must not already exist
- The file is reserved in advance by checking that it does not already exist

## Typical workflow

Example session:

```text
% :r draft.md
queued draft.md

% Please review this text and suggest improvements.
[*] @gpt4 is thinking...

<assistant response>
```

Write the last response later:

```text
% :w review.md
wrote review.md (1234 bytes)
```

Or queue the next response to be written automatically:

```text
% :o output.txt
queued output output.txt

% Summarize the previous feedback in bullet points.
[*] @gpt4 is thinking...

<assistant response>

wrote output.txt (567 bytes)
```

## Error behavior

The CLI prints errors in a simple form such as:

```text
error: <message>
```

Examples include:

- unknown agent name
- missing command path
- file not found
- path already exists
- no assistant response to write

## Exit

You can exit by:

- pressing `Ctrl-D` on empty input
- sending EOF from the terminal

On exit, the program prints:

```text
bye
```

## Development

Run Ruff checks:

```bash
uv run ruff check src/portable_agent_chat --fix
```

If you want formatting as well, run:

```bash
uv run ruff format .
```