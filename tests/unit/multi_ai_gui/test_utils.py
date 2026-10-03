from pathlib import Path

from multi_ai_gui.utils import get_dir_state


def test_get_dir_state(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / ".subdir").mkdir()
    (tmp_path / ".subdir" / "b.txt").write_text("y")

    result = get_dir_state(str(tmp_path))
    paths = {Path(p).name for p in result}

    assert "a.txt" in paths
    assert "b.txt" not in paths
