#!/bin/bash

uv run multi-ai << 'EOF'
  @claude -m "エージェント命名規約変更に伴うエージェント/エンジンの分離をします。要件に従ってどこをどう修正すればいいのか詳細設計を書いて下さい" -r specification.txt -r multi_ai_cli/config.py -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py -r multi_ai_cli/utils.py -r multi_ai_cli/version.py -w agent_engine_detailed_design.md -> @gemini -m "specification.txt と agent_engine_detailed_design.md 比較して agent_engine_detailed_design.md の実装方針が正しいか評価して下さい" -r specification.txt -r agent_engine_detailed_design.md -r multi_ai_cli/config.py -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py -r multi_ai_cli/utils.py -r multi_ai_cli/version.py -w review_agent_engine_detailed_design.md
exit
EOF

echo "update_specification"

