#!/usr/bin/env bash
set -euo pipefail

run() {
  local title="$1"
  shift

  printf '\n==> %s\n' "$title"
  "$@"
}

expect_failure() {
  local title="$1"
  shift

  printf '\n==> %s\n' "$title"
  if "$@"; then
    echo "[!] Expected failure, but the command succeeded."
    exit 1
  else
    echo "[✓] Failed as expected."
  fi
}

TMP_OUT="$(mktemp)"
trap 'rm -f "$TMP_OUT"' EXIT

run "Primary input is preserved" \
  bash -c 'echo "This is the PRIMARY input." | uv run multi-ai @gpt -m "Reply with exactly the primary input text."'

run "Japanese translation" \
  bash -c 'echo "apple" | uv run multi-ai @gpt -m "Translate this to Japanese only."'

run "Summary output redirected to file" \
  bash -c 'echo "hello world" | uv run multi-ai @gpt -m "Summarize this" > "$1" && cat "$1"' _ "$TMP_OUT"

expect_failure "Rejected write flag in filter mode" \
  bash -c 'echo "hello" | uv run multi-ai @gpt -w out.txt'

run "Brief reply redirected to file" \
  bash -c 'echo "hello" | uv run multi-ai @gpt -m "Reply briefly." > "$1" && cat "$1"' _ "$TMP_OUT"

printf '\n[✓] Dual-mode checker completed successfully!\n'
