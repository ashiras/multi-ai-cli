import warnings

# requests の文字コード判定警告だけをピンポイントで握りつぶす（サイレント・キル！）
warnings.filterwarnings("ignore", message=".*Unable to find acceptable character detection dependency.*")

from multi_ai_cli.main import main

if __name__ == "__main__":
    main()