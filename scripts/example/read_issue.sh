@sh "cp -r src/multi_ai_cli/ work_data/multi_ai_cli/"
->
@github.issue --repo ashiras/multi-ai-cli --number 47 -w issue_47.md
->
@gpt -m "issue 47 のような機能追加をします。どこに機能追加すれば解消されるか詳細を調べ要約を書いてまとめて下さい" -r issue_47.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_47_specification.txt
->
@gpt -m "github の issue に書けるようなフォーマットで、英文でまとめて下さい" -w issue_47_specification.2.txt
->
@claude -m "issue_47_specification.2.txt に従って対象ファイルのコードを修正して下さい。コード中のコメントは英文とする。" -r issue_47_specification.2.txt -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_47_code.py
