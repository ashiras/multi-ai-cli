#!/bin/bash

set -e

echo "[*] Starting Pipeline..."

echo "[*] Formatting code with ruff..."
uv run ruff format .

echo "[*] Linting code with ruff..."
uv run ruff check . --fix

echo "[*] Type checking with mypy..."
uv run mypy src

# echo "[*] Running tests with pytest..."
# uv run pytest

if [ -f "./scripts/test_scenario.sh" ]; then
    echo "[*] Executing test scenario..."
    bash ./scripts/test_scenario.sh
else
    echo "[!] Error: test_scenario.sh not found."
    exit 1
fi

echo "[✓] Pipeline completed successfully!"