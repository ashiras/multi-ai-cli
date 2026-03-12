#!/bin/bash

uv run multi-ai << 'EOF'
  @gemini -m "今回のシステム改修で、README修正要件書(update_README.md)に従い、実装に合わせて英文で README.md を修正して下さい。" -r README.md -r update_README.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py -r multi_ai_cli/registry.py -r multi_ai_cli/utils.py -r multi_ai_cli/version.py  -r multi_ai_cli/adapters/github/backends/rest_backend.py -r multi_ai_cli/adapters/github/adapter.py -r multi_ai_cli/adapters/github/facade.py -r multi_ai_cli/adapters/github/models.py -w new_README.md
exit
EOF

echo "update_README.md"

