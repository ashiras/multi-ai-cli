@sh "cp -r src/multi_ai_cli/ work_data/multi_ai_cli/"
->
@github.issue --repo ashiras/multi-ai-cli --number 46 -w issue_46.md
->
@gpt -m "issue 46 のような不具合があります。どこを修正すれば解消されるか詳細を調べ詳細設計書を書いて下さい" -r issue_46.md -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_46_specification.txt
->
@claude -m "issue_46_specification.2.txt に従って対象ファイルのコードを修正して下さい。コード中のコメントは英文とする。" -r issue_46_specification.2.txt -r multi_ai_cli/config.py -r multi_ai_cli/engines.py -r multi_ai_cli/handlers.py -r multi_ai_cli/main.py -r multi_ai_cli/parsers.py  -r multi_ai_cli/utils.py -w issue_46_code.py