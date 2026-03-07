from unittest.mock import patch

import pytest


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
    mock_exists,
) -> None:
    """
    Test the full main loop by simulating user inputs and ensuring
    it breaks correctly on 'exit'.
    """
    mock_exists.return_value = True

    mock_input.side_effect = ["@gpt hello", "exit", SystemExit("Loop safeguard")]

    from multi_ai_cli.main import main

    try:
        main()
    except (SystemExit, EOFError):
        pass

    mock_setup_config.assert_called_once()
    mock_init_engines.assert_called_once()
    mock_dispatch.assert_called_once_with(["@gpt", "hello"])
    assert mock_input.call_count == 2


@patch("multi_ai_cli.main.os.path.exists")
def test_main_error_exit(mock_exists, capsys) -> None:
    """Test that main exits with status 1 if the config file is missing."""
    mock_exists.return_value = False

    from multi_ai_cli.main import main

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "[!] Error" in captured.out
