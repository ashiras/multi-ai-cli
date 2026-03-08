#!/bin/bash

PROMPT="Rewrite and standardize the docstrings in this Python code. Strictly follow these rules based on the Google Python Style Guide:
1. Analyze the actual code logic, arguments, and return values to write accurate docstrings. DO NOT simply translate or reformat existing comments.
2. Must write or update module, class, and function docstrings using \"\"\" and Google Style sections (Args:, Returns:, Raises:, etc.).
3. Must use descriptive third-person present tense for the first summary line (e.g., 'Fetches', not 'Fetch').
4. DO NOT add new inline comments (#) for code logic. Assume the code is self-explanatory.
5. Delete any existing inline comments that merely explain 'What' the code does.
6. Write all docstrings strictly in English. Completely remove any existing Japanese text.
Return only the updated Python code without any markdown formatting blocks."

REVIEW_PROMPT="元のコードと、GPTがDocstringを追加した後のコードを比較し、以下の観点で厳しくレビューしてください。
1. Docstringの内容が、元のコードの実際のロジック・引数・戻り値と完全に一致しているか（嘘をついていないか）
2. Google Python Style Guideに正確に準拠しているか
3. 不要なインラインコメントが残っていないか
改善点があれば具体的に指摘し、Markdown形式の読みやすいレポートを作成してください。"

FILES=("config.py" "engines.py" "handlers.py" "main.py" "parsers.py" "utils.py" "version.py")

mkdir -p reviews

uv run multi-ai << EOF
@efficient all "$PROMPT"
$(for f in "${FILES[@]}"; do
    BASENAME="${f%.py}"
    CMD="@sh cat src/multi_ai_cli/$f -w r.txt"
    CMD="$CMD -> @gpt -r r.txt -w:code commented_$f"
    CMD="$CMD -> @gemini -m '$REVIEW_PROMPT' -r r.txt -r commented_$f -w reviews/review_${BASENAME}.md"
    echo "$CMD"
done)
exit
EOF

echo "Docstring generation and Gemini review complete! Check the 'reviews/' directory."