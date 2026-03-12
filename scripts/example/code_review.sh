#!/bin/bash

PROMPT="Please evaluate this Python code. Focus on:
1. Potential bugs or edge case issues.
2. Security vulnerabilities.
3. Performance optimization opportunities.
4. Readability and adherence to Pythonic idioms.
5. Provide a concise summary of your findings."

FILES=("config.py" "engines.py" "handlers.py" "main.py" "parsers.py" "utils.py" "version.py")

uv run multi-ai << EOF
@efficient all "$PROMPT"
$(for f in "${FILES[@]}"; do
echo "@sh "cat src/multi_ai_cli/$f" -w r.txt -> @claude -r r.txt -w review_$f.md"
done)
exit
EOF

echo "All code reviews completed. Check 'work_data/review_*.md' for results."