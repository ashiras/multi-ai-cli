[
    @sh "cp -r src/multi_ai_cli/ work_data/multi_ai_cli/"
    ||
    @github.issue --repo ashiras/multi-ai-cli --number 49 -w issue_49.md
]
->
@gpt -m "issue_49.md のような機能追加をします。どう実装すれば機能が満たされるか調べ要約を書いてまとめて下さい。" -r issue_49.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_49_specification.txt
->
@pause
->
@gpt -m "次に github の issue に書けるフォーマットで、英文でまとめて下さい" -w issue_49_specification.2.txt
->
@pause
->
@claude -m "issue_49_specification.2.txt に従って対象ファイルのコードを修正して下さい。コード中のコメントは英文とする。" -r issue_49_specification.2.txt -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_49_code.py
->
@pause
->
@claude -m "issue_49_specification.3.txt に従って修正したコードをもう一度見直してください。コード中のコメントは英文とする。" -r issue_49_specification.3.txt -r issue_49_code.py -w issue_49_code.2.py
