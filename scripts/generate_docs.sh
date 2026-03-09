#!/bin/bash

# 1. GPT Prompt (Coder)
PROMPT="You are a strict Python code formatter. Your ONLY job is to output Python code. 
Rewrite the docstrings in the provided code following the Google Python Style Guide. 
Rules: 
1. Silently analyze the logic to write accurate docstrings, but DO NOT output your analysis. 
2. Use triple double-quotes and Google Style sections (Args:, Returns:, etc.). 
3. Use third-person present tense for the summary (e.g., 'Fetches'). 
4. DO NOT add new inline comments. 
5. Delete existing inline comments that explain 'What'. 
6. All text must be in English. Remove all Japanese. 
CRITICAL: Return ONLY the raw, updated Python code. Do NOT output any explanations, overviews, or markdown formatting blocks like \`\`\`python."

# 2. Gemini Prompt (Reviewer) - Gemini is used in a clean state without @efficient
REVIEW_PROMPT="Compare the original code with the version updated by GPT and review it strictly based on these criteria: "
REVIEW_PROMPT+="1. Accuracy: Does the Docstring content perfectly match the code's logic, arguments, and return values? (No false information). "
REVIEW_PROMPT+="2. Style: Does it strictly adhere to the Google Python Style Guide? "
REVIEW_PROMPT+="3. Redundancy: Are all unnecessary inline comments removed? "
REVIEW_PROMPT+="If there are points for improvement, point them out specifically and create a readable report in Markdown format in Japanese."

# 3. Claude Prompt (Fixer)
CLAUDE_PROMPT="You are an expert Python engineer. You will receive code formatted by GPT and a strict code review from Gemini. 
Apply all the improvements suggested in the review to create the final, perfect Python code. 
CRITICAL: Output ONLY the raw Python code. Do NOT provide explanations, introductions, or markdown formatting blocks (e.g., \`\`\`python)."

FILES=("config.py" "engines.py" "handlers.py" "main.py" "parsers.py" "utils.py" "version.py")

# Directory preparation (Clarify save locations)
mkdir -p work_data/commented
mkdir -p work_data/reviews
mkdir -p work_data/final
mkdir -p prompts

# Save prompts to files
echo "$PROMPT" > prompts/formatter.txt
echo "$CLAUDE_PROMPT" > prompts/fixer.txt

# Execute Pipeline
uv run multi-ai << EOF
@efficient gpt formatter.txt
@efficient claude fixer.txt
$(for f in "${FILES[@]}"; do
    BASENAME="${f%.py}"
    
    # Step 1: Load original code
    CMD="@sh cat src/multi_ai_cli/$f -w work_data/r.txt"
    
    # Step 2: GPT adds Docstrings
    CMD="$CMD -> @gpt -r r.txt -w:code commented/commented_$f"
    
    # Step 3: Gemini performs strict review
    CMD="$CMD -> @gemini -m \"$REVIEW_PROMPT\" -r r.txt -r commented/commented_$f -w reviews/review_${BASENAME}.md"
    
    # Step 4: Claude performs final fix based on review
    CMD="$CMD -> @claude -r commented/commented_$f -r reviews/review_${BASENAME}.md -w:code final/final_$f"
    
    echo "$CMD"
done)
exit
EOF

echo "Pipeline complete!"
echo "- GPT's draft: work_data/commented/"
echo "- Gemini's review: work_data/reviews/"
echo "- Claude's final code: work_data/final/"
