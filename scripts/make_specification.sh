#!/bin/bash

set -euo pipefail

UPDATE_FILE="update_specification.txt"
REVIEW_UPDATE_FILE="review_update_specification.txt"
CHECK_REVIEW_UPDATE_FILE="check_update_specification.txt"

CMD="@claude -m \"specification.txt に従ってどこをどう修正すべきか詳細設計書を書いて下さい\" -r specification.txt -r config.py -r parsers.py -r utils.py -r main.py -r handlers.py -r engines.py -r version.py -w $UPDATE_FILE"
CMD="$CMD -> @gemini -m \"update_specification.txt が 正しく specification.txt の要件が組み込まれているかレビューし懸念事項があれば記載して下さい。\" -r specification.txt -r $UPDATE_FILE -r config.py -r parsers.py -r utils.py -r main.py -r handlers.py -r engines.py -r version.py -w $REVIEW_UPDATE_FILE"
CMD="$CMD -> @gpt -m \"update_specification.txt を変更する余地があれば check_update_specification.txt に従って書き直して下さい\" -r specification.txt -r $UPDATE_FILE -r $REVIEW_UPDATE_FILE -r config.py -r parsers.py -r utils.py -r main.py -r handlers.py -r engines.py -r version.py -w $CHECK_REVIEW_UPDATE_FILE"

echo "Running specification update pipeline..."
echo $CMD
uv run multi-ai $CMD

echo "update_specification"

