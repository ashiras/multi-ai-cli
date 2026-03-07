#!/bin/bash

PROMPT="Please add Google style English docstrings and inline comments to this Python code. Return only the updated code."
FILES=("config.py" "engines.py" "handlers.py" "main.py" "parsers.py" "utils.py" "version.py")

uv run multi-ai << EOF
@efficient all "$PROMPT"
$(for f in "${FILES[@]}"; do
echo "@sh "cat src/multi_ai_cli/$f" -w r.txt -> @gpt -r r.txt -w:code commented_$f"
done)
exit
EOF
SKIP

echo "Scenario test complete!"