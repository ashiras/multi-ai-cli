@sh "cp -r src/multi_ai_cli/ work_data/multi_ai_cli/"
->
@gpt -m "issue_24.md のような機能追加をします。どう実装すれば機能が満たされるか詳細を調べ要約を書いてまとめて下さい。" -r issue_24.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_24_specification.txt
->
@pause
->
@gpt -m "github の issue に書けるようなフォーマットで、英文でまとめて下さい" -w issue_24_specification.2.txt
->
@claude -m "issue_24_specification.2.txt に従って対象ファイルのコードを修正して下さい。コード中のコメントは英文とする。" -r issue_24_specification.2.txt -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_24_code.py
->
@claude -m "issue_24_specification.3.txt に従って修正したコードをもう一度見直してください。コード中のコメントは英文とする。" -r issue_24_specification.3.txt -r issue_24_code.py -w issue_24_code.2.py
