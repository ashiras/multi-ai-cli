from unittest.mock import patch

import pytest

from multi_ai_cli.main import main


class TestMainVersionFlag:
    @patch("sys.argv", ["multi-ai", "--version"])
    def test_version_flag(self):
        with patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        assert "multi-ai version" in mock_print.call_args[0][0]

    @patch("sys.argv", ["multi-ai", "-v"])
    def test_version_short_flag(self):
        with patch("builtins.print"):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestMainIniNotFound:
    @patch("sys.argv", ["multi-ai"])
    @patch("os.path.exists", return_value=False)
    def test_ini_not_found_exits(self, mock_exists):
        with patch("builtins.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        mock_print.assert_called_once_with(
            "[!] Error: 'multi_ai_cli.ini' not found in the current directory."
        )


class TestMainLoop:
    """Test for the interactive loop of main()"""

    def _patch_startup(self):
        """Patch startup processes (config/logger/engines/banner) together"""
        return [
            patch("sys.argv", ["multi-ai"]),
            patch("os.path.exists", return_value=True),
            patch("multi_ai_cli.main.setup_config"),
            patch("multi_ai_cli.main.setup_logger"),
            patch("multi_ai_cli.engines.initialize_engines"),
            patch("multi_ai_cli.main.print_welcome_banner"),
        ]

    def test_exit_command(self):
        """正常終了 with 'exit'"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch("builtins.input", side_effect=["exit"]):
            with patch("multi_ai_cli.main.dispatch_command") as mock_dispatch:
                main()
        assert mock_dispatch.call_count == 0

        for p in patches:
            p.stop()

    def test_quit_command(self):
        """正常終了 with 'quit'"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch("builtins.input", side_effect=["quit"]):
            with patch("multi_ai_cli.main.dispatch_command") as mock_dispatch:
                main()
        assert mock_dispatch.call_count == 0

        for p in patches:
            p.stop()

    def test_empty_input_skipped(self):
        """Empty input is skipped"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch("builtins.input", side_effect=["", "  ", "exit"]):
            with patch("multi_ai_cli.main.dispatch_command") as mock_dispatch:
                main()
        assert mock_dispatch.call_count == 0

        for p in patches:
            p.stop()

    def test_single_command_dispatched(self):
        """A single command is passed to dispatch_command"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch("builtins.input", side_effect=["@gpt hello world", "exit"]):
            with patch(
                "multi_ai_cli.main.dispatch_command", return_value=True
            ) as mock_dispatch:
                main()

        mock_dispatch.assert_called_once_with(["@gpt", "hello", "world"])

        for p in patches:
            p.stop()

    def test_pipeline_two_steps(self):
        """A pipeline with '->' runs in 2 steps"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch(
            "builtins.input", side_effect=["@gpt step1 -> @claude step2", "exit"]
        ):
            with patch(
                "multi_ai_cli.main.dispatch_command", return_value=True
            ) as mock_dispatch:
                with patch("builtins.print"):
                    main()

        assert mock_dispatch.call_count == 2
        mock_dispatch.assert_any_call(["@gpt", "step1"])
        mock_dispatch.assert_any_call(["@claude", "step2"])

        for p in patches:
            p.stop()

    def test_pipeline_stops_on_failure(self):
        """The pipeline stops if a command fails"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch(
            "builtins.input",
            side_effect=["@gpt step1 -> @claude step2 -> @grok step3", "exit"],
        ):
            with patch(
                "multi_ai_cli.main.dispatch_command", return_value=False
            ) as mock_dispatch:
                with patch("builtins.print") as mock_print:
                    main()

        # If the first step fails, it stops there
        assert mock_dispatch.call_count == 1
        # Pipeline stop message
        mock_print.assert_any_call(
            "[!] Pipeline stopped due to an error in the current step."
        )

        for p in patches:
            p.stop()

    def test_shlex_parse_error_continues(self):
        """Loop continues even with shlex parse errors"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        # An unclosed quote raises ValueError with shlex.split
        with patch("builtins.input", side_effect=['@gpt "unclosed quote', "exit"]):
            with patch("multi_ai_cli.main.dispatch_command") as mock_dispatch:
                with patch("builtins.print") as mock_print:
                    main()

        assert mock_dispatch.call_count == 0
        # Output a parse error message
        print_calls = [str(c) for c in mock_print.call_args_list]
        assert any("Parse error" in c for c in print_calls)

        for p in patches:
            p.stop()

    def test_keyboard_interrupt_handled(self):
        """Loop continues with KeyboardInterrupt, and exits on 'exit'"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch(
            "builtins.input",
            side_effect=[KeyboardInterrupt, "exit"],
        ):
            with patch("builtins.print") as mock_print:
                main()

        print_calls = [str(c) for c in mock_print.call_args_list]
        assert any("interrupted" in c for c in print_calls)

        for p in patches:
            p.stop()

    def test_unexpected_exception_handled(self):
        """Loop continues even with unexpected exceptions in dispatch_command"""
        patches = self._patch_startup()
        for p in patches:
            p.start()

        with patch("builtins.input", side_effect=["@gpt hello", "exit"]):
            with patch(
                "multi_ai_cli.main.dispatch_command",
                side_effect=RuntimeError("boom"),
            ):
                with patch("builtins.print") as mock_print:
                    main()

        print_calls = [str(c) for c in mock_print.call_args_list]
        assert any("unexpected error" in c.lower() for c in print_calls)

        for p in patches:
            p.stop()


if __name__ == "__main__":
    pytest.main()
