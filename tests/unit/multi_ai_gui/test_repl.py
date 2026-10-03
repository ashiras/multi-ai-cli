import sys

from multi_ai_gui.repl import get_multi_ai_repl_command


def test_get_multi_ai_repl_command_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "multi-ai-gui.exe"
    exe.touch()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    prog, args, cwd = get_multi_ai_repl_command()

    assert prog == str(tmp_path / "multi-ai")
    assert args == ["--mode", "repl"]
    assert cwd == str(tmp_path)
