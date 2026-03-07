import pytest
from unittest.mock import patch, MagicMock

# mainの中で行われているローカルインポートを事前にモック化するための準備
@patch("multi_ai_cli.main.os.path.exists")
@patch("multi_ai_cli.main.setup_config")
@patch("multi_ai_cli.main.setup_logger")
@patch("multi_ai_cli.engines.initialize_engines")
@patch("multi_ai_cli.main.print_welcome_banner")
@patch("multi_ai_cli.main.dispatch_command")
@patch("builtins.input")
def test_main_loop_execution(
    mock_input, 
    mock_dispatch, 
    mock_banner, 
    mock_init_engines, 
    mock_setup_logger, 
    mock_setup_config, 
    mock_exists
):
    """
    Test the full main loop by simulating user inputs and ensuring 
    it breaks correctly on 'exit'.
    """
    # 1. 準備: 設定ファイルが存在すると仮定
    mock_exists.return_value = True
    
    # 2. 準備: ユーザー入力をシミュレート
    # 最初はコマンドを入力し、次に 'exit' でループを抜ける。
    # 万が一 'exit' で抜けられなかった時のために SystemExit を置いておく。
    mock_input.side_effect = ["@gpt hello", "exit", SystemExit("Loop safeguard")]

    from multi_ai_cli.main import main
    
    # 3. 実行: main() を呼び出す
    try:
        main()
    except (SystemExit, EOFError):
        # ループガードや入力終了による脱出を許容
        pass

    # 4. 検証: 正しく各関数が呼ばれたか
    mock_setup_config.assert_called_once()
    mock_init_engines.assert_called_once()
    mock_dispatch.assert_called_once_with(["@gpt", "hello"])
    assert mock_input.call_count == 2


@patch("multi_ai_cli.main.os.path.exists")
def test_main_error_exit(mock_exists, capsys):
    """
    Test that main exits with status 1 if the config file is missing.
    """
    mock_exists.return_value = False
    
    from multi_ai_cli.main import main
    
    # sys.exitをモックするのではなく、実際に発生する SystemExit をキャッチする
    with pytest.raises(SystemExit) as excinfo:
        main()
    
    # sys.exit(1) の「1」が正しく渡されたか確認
    assert excinfo.value.code == 1
    
    captured = capsys.readouterr()
    assert "[!] Error" in captured.out