#!/bin/bash
set -euo pipefail

TEST_PROMPT="Role: Role:
You are an expert Python QA Engineer specializing in pytest and refactoring unit tests for CLI applications.
Task:
Review the existing unit test errors and refactor the test suite to be compatible with pytest.
Context & Setup:
- Target Module: Assume the source code is imported as from multi_ai_cli import (config) as app_config.
- Primary Goal: Regression prevention.
- Testing Strategy: Black-box testing only.
Testing Depth & Coverage Constraints:
- C0 (Statement Coverage): Ensure \"Happy Paths\" (main execution flows) are functional. This is the priority.
- C1 (Branch Coverage): It is sufficient to cover only one direction of a branch.
- C2 / MC/DC (Condition/Multiple Condition): Do NOT perform these.
- Coverage Metrics: Do not worry about specific percentage targets or high-coverage benchmarks. The focus is on basic operational stability.
Technical Stack:
- The environment uses the following libraries:
- Production: anthropic, google-genai, openai, python-dotenv
- Development/Testing: pytest, pytest-mock (for mocking API calls), mypy, ruff
Output Requirement:
Provide the corrected pytest code that satisfies the \"minimalist coverage\" criteria mentioned above, ensuring all external AI SDK calls are appropriately mocked using pytest-mock.
"

FILES=("config.py" "parsers.py" "utils.py" "main.py" "handlers.py" "engines.py" "version.py")

mkdir -p prompts
mkdir -p work_data/src
mkdir -p work_data/tests_unit

echo "$TEST_PROMPT" > prompts/test_prompt.txt

uv run multi-ai << EOF
@efficient gemini test_prompt.txt
$(for f in "${FILES[@]}"; do
    BASENAME="${f%.py}"
    SRC_FILE="src/${BASENAME}.txt"
    TEST_FILE="tests_unit/test_$f"
    TEST_FILE_OUT="tests_unit/test_out_$f"

    CMD="@sh cat src/multi_ai_cli/$f -w $SRC_FILE"
    CMD="$CMD -> @gemini -r $SRC_FILE -r error.txt -r $TEST_FILE -w:code $TEST_FILE_OUT"

    echo "$CMD"
done)
exit
EOF

echo "Test generation complete! Check 'work_data/tests_unit/'."