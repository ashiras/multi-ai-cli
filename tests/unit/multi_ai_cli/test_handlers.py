"""Tests for multi_ai_cli.handlers module."""

from unittest.mock import MagicMock, patch

from multi_ai_cli.handlers import (
    dispatch_command,
    handle_pause,
    handle_scrub,
)


class TestHandlePause:
    def test_extra_args_rejected(self, capsys):
        result = handle_pause(["@pause", "extra"])
        assert result is False
        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_continue(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = handle_pause(["@pause"])
        assert result is True

    def test_abort(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "q")
        result = handle_pause(["@pause"])
        assert result is False

    def test_invalid_then_continue(self, monkeypatch):
        responses = iter(["invalid", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = handle_pause(["@pause"])
        assert result is True

    def test_eof(self, monkeypatch):
        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        result = handle_pause(["@pause"])
        assert result is False


class TestDispatchCommand:
    def setup_method(self):
        self.session = MagicMock()
        self.session.is_valid_agent.return_value = False
        self.session.agent_keys.return_value = ["gpt", "claude"]

    def test_empty_parts(self):
        result = dispatch_command([], self.session)
        assert result is False

    def test_unknown_command(self, capsys):
        result = dispatch_command(["@unknown"], self.session)
        assert result is False
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    def test_scrub_command(self):
        with patch("multi_ai_cli.handlers.handle_scrub") as mock_scrub:
            result = dispatch_command(["@scrub"], self.session)
            assert result is True
            mock_scrub.assert_called_once()

    def test_flush_command(self):
        with patch("multi_ai_cli.handlers.handle_scrub"):
            result = dispatch_command(["@flush"], self.session)
            assert result is True

    def test_pause_command(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = dispatch_command(["@pause"], self.session)
        assert result is True

    def test_sh_command(self):
        with patch("multi_ai_cli.handlers.handle_sh") as mock_sh:
            mock_sh.return_value = True
            result = dispatch_command(["@sh", "echo", "hi"], self.session)
            assert result is True

    def test_agent_command(self):
        self.session.is_valid_agent.return_value = True
        with patch("multi_ai_cli.handlers.handle_ai_interaction") as mock_ai:
            mock_ai.return_value = True
            result = dispatch_command(["@gpt", "hello"], self.session)
            assert result is True

    def test_figma_pull(self):
        with patch("multi_ai_cli.adapters.figma.facade.handle_figma_pull") as mock_fp:
            mock_fp.return_value = True
            result = dispatch_command(["@figma.pull", "--file", "abc"], self.session)
            assert result is True

    def test_figma_push(self):
        with patch("multi_ai_cli.adapters.figma.facade.handle_figma_push") as mock_fp:
            mock_fp.return_value = True
            result = dispatch_command(["@figma.push", "-r", "f.md"], self.session)
            assert result is True

    def test_github_repo(self):
        with patch("multi_ai_cli.adapters.github.facade.handle_github_repo") as mock_gh:
            mock_gh.return_value = True
            result = dispatch_command(["@github.repo", "--repo", "o/r"], self.session)
            assert result is True

    def test_github_tree(self):
        with patch("multi_ai_cli.adapters.github.facade.handle_github_tree") as mock_gh:
            mock_gh.return_value = True
            result = dispatch_command(["@github.tree", "--repo", "o/r"], self.session)
            assert result is True

    def test_github_file(self):
        with patch("multi_ai_cli.adapters.github.facade.handle_github_file") as mock_gh:
            mock_gh.return_value = True
            result = dispatch_command(
                ["@github.file", "--repo", "o/r", "--path", "f"], self.session
            )
            assert result is True

    def test_github_issue(self):
        with patch(
            "multi_ai_cli.adapters.github.facade.handle_github_issue"
        ) as mock_gh:
            mock_gh.return_value = True
            result = dispatch_command(
                ["@github.issue", "--repo", "o/r", "--number", "1"], self.session
            )
            assert result is True

    def test_github_issues(self):
        with patch(
            "multi_ai_cli.adapters.github.facade.handle_github_issues"
        ) as mock_gh:
            mock_gh.return_value = True
            result = dispatch_command(["@github.issues", "--repo", "o/r"], self.session)
            assert result is True

    def test_efficient_command(self):
        with patch("multi_ai_cli.handlers.handle_efficient") as mock_eff:
            result = dispatch_command(["@efficient", "persona.txt"], self.session)
            assert result is True
            mock_eff.assert_called_once()

    def test_sequence_command(self):
        with patch(
            "multi_ai_cli.handlers.handle_sequence",
            return_value=True,
        ) as mock_seq:
            result = dispatch_command(
                ["@sequence", "-e"],
                self.session,
            )

            assert result is True

            mock_seq.assert_called_once_with(
                ["@sequence", "-e"],
                self.session,
            )


class TestHandleScrub:
    def test_scrub_all(self, capsys):
        session = MagicMock()
        engine_a = MagicMock()
        engine_a.name = "AgentA"
        engine_b = MagicMock()
        engine_b.name = "AgentB"

        session.agent_keys.return_value = ["a", "b"]
        session.scrub.return_value = ["a", "b"]
        session.get_agent.side_effect = lambda k: {"a": engine_a, "b": engine_b}[k]

        handle_scrub(["@scrub"], session)
        session.scrub.assert_called_once_with()

        captured = capsys.readouterr()
        assert "AgentA" in captured.out
        assert "AgentB" in captured.out

    def test_scrub_specific(self, capsys):
        session = MagicMock()
        engine = MagicMock()
        engine.name = "MyAgent"

        session.agent_keys.return_value = ["myagent"]
        session.has_agent.return_value = True
        session.get_agent.return_value = engine

        handle_scrub(["@scrub", "myagent"], session)
        session.scrub.assert_called_once_with("myagent")

    def test_scrub_invalid_target(self, capsys):
        session = MagicMock()
        session.agent_keys.return_value = ["gpt"]

        handle_scrub(["@scrub", "nonexistent"], session)
        captured = capsys.readouterr()
        assert "Invalid target" in captured.out

    def test_scrub_not_loaded(self, capsys):
        session = MagicMock()
        session.agent_keys.return_value = ["gpt"]
        session.has_agent.return_value = False

        handle_scrub(["@scrub", "gpt"], session)
        captured = capsys.readouterr()
        assert "not been used" in captured.out
