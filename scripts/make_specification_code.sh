#!/bin/bash

uv run multi-ai << 'EOF'
  @claude -m "agent_github_detailed_design.md に従って Python コードを修正して下さい。コードの中に書くコメントは全て英語で書いて下さい。尚 review_agent_github_detailed_design.md も参考に。" -r agent_github_detailed_design.md -r review_agent_github_detailed_design.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py -r multi_ai_cli/registry.py -r multi_ai_cli/utils.py -r multi_ai_cli/version.py -w new_code.md
exit
EOF

echo "update_specification"

