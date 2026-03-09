#!/bin/bash
set -euo pipefail

TEST_PROMPT="コード中の日本語を英語にして下さい。pythonコードは変更してはいけません"

FILES=("config.py" "parsers.py" "utils.py" "main.py" "handlers.py" "engines.py" "version.py")

mkdir -p prompts
mkdir -p work_data/src
mkdir -p work_data/tests_unit

echo "$TEST_PROMPT" > prompts/test_prompt.txt

uv run multi-ai << EOF
$(for f in "${FILES[@]}"; do
    TEST_FILE="tests_unit/test_$f"
    TEST_FILE_OUT="tests_unit/test_out_$f"

    CMD="@gpt -m $TEST_PROMPT -r $TEST_FILE -w:code $TEST_FILE_OUT"

    echo "$CMD"
done)
exit
EOF

echo "Test generation complete! Check 'work_data/tests_unit/'."