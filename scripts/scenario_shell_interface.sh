#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TMP_DIR="work_data/_sh_smoke"
LOG_FILE="$TMP_DIR/session.log"

mkdir -p "$TMP_DIR"
rm -f "$TMP_DIR/artifact.txt" "$TMP_DIR/artifact.json" "$LOG_FILE"

cat > "$TMP_DIR/runner.py" <<'PY'
print("runner-ok")
PY

echo "[*] Running @sh smoke test via uv run multi-ai ..."

uv run multi-ai <<'EOF' >"$LOG_FILE" 2>&1
@sh "printf direct-ok"
@sh --shell "printf shell-ok | tr a-z A-Z"
@sh -r _sh_smoke/runner.py
@sh "printf text-artifact" -w _sh_smoke/artifact.txt
@sh "printf json-artifact" -w _sh_smoke/artifact.json
@sh --shell "exit 7"
@sh -r _sh_smoke/missing.py
exit
EOF

assert_log_contains() {
  local needle="$1"
  local label="$2"
  if grep -Fq -- "$needle" "$LOG_FILE"; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    echo "----- session log -----"
    cat "$LOG_FILE"
    echo "----- end log -----"
    exit 1
  fi
}

assert_file_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if grep -Fq -- "$needle" "$file"; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    echo "----- file: $file -----"
    cat "$file"
    echo "----- end file -----"
    exit 1
  fi
}

# --- log checks ---
assert_log_contains "[*] @sh: Executing: printf direct-ok" "direct command shows Executing"
assert_log_contains "direct-ok" "direct command stdout appears"

assert_log_contains "[*] @sh: --shell mode enabled (shell=True)" "--shell banner appears"
assert_log_contains "SHELL-OK" "--shell pipeline output appears"

assert_log_contains "runner-ok" "-r script execution works"

assert_log_contains "Artifact saved to '_sh_smoke/artifact.txt'" "text artifact save message appears"
assert_log_contains "Artifact saved to '_sh_smoke/artifact.json'" "json artifact save message appears"

assert_log_contains "[✗] @sh: FAILURE (exit code: 7" "failing command is reported"
assert_log_contains "File not found: '_sh_smoke/missing.py'" "missing file is reported"

# --- artifact checks ---
test -f "$TMP_DIR/artifact.txt"
echo "[PASS] text artifact file exists"
assert_file_contains "$TMP_DIR/artifact.txt" "# Shell Execution Artifact" "text artifact header is present"
assert_file_contains "$TMP_DIR/artifact.txt" "text-artifact" "text artifact stdout is present"

test -f "$TMP_DIR/artifact.json"
echo "[PASS] json artifact file exists"

python3 - <<'PY'
import json
from pathlib import Path

path = Path("work_data/_sh_smoke/artifact.json")
data = json.loads(path.read_text(encoding="utf-8"))

assert data["status"] == "success", data
assert data["stdout"] == "json-artifact", data
assert data["exit_code"] == 0, data

print("[PASS] json artifact content is valid")
PY

echo
echo "[✓] @sh smoke test completed successfully."