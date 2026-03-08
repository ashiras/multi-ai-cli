#!/bin/bash

PROMPT="Analyze this Python code and write comprehensive unit tests using 'pytest'. Strictly follow these rules:
1. Analyze the actual code logic, branches, and return values to determine necessary test cases. DO NOT write superficial tests.
2. Test both 'happy paths' and 'edge cases' (e.g., exceptions, invalid inputs, missing files).
3. Strictly isolate tests. You MUST mock all external dependencies (e.g., file system, 'os', 'sys.argv', 'input()', network calls) using 'unittest.mock' or 'pytest' fixtures.
4. Structure every test strictly using the Arrange-Act-Assert (AAA) pattern. You MUST include exactly these three inline comments in every single test function: '# Arrange', '# Act', and '# Assert'.
5. Use highly descriptive test names following the pattern: 'test_<function_name>_<condition>_<expected_result>'.
6. Write all tests strictly in English. DO NOT add any other inline comments explaining 'What' the code does. Only add comments to explain 'Why' a specific complex mock or test data is used.
Return only the valid, runnable test Python code without any markdown formatting blocks."

FILES=("config.py" "engines.py" "handlers.py" "main.py" "parsers.py" "utils.py" "version.py")

mkdir -p tests

uv run multi-ai << EOF
@efficient all "$PROMPT"
$(for f in "${FILES[@]}"; do
echo "@sh cat src/multi_ai_cli/$f -w r.txt -> @gpt -r r.txt -w:code tests/test_$f"
done)
exit
EOF
SKIP

echo "Test generation complete! Check the 'tests/' directory."