#!/bin/bash

uv run multi-ai << 'EOF'
  @claude -m "agent_engine_detailed_design.md に従って Python コードを修正して下さい" -r specification.txt -r agent_engine_detailed_design.md -r multi_ai_cli/config.py -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py -r multi_ai_cli/utils.py -r multi_ai_cli/version.py -w new_code.py
exit
EOF

echo "update_specification"

