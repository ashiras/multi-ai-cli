import configparser
from pathlib import Path
from unittest.mock import patch

from multi_ai_gui.utils import get_dir_state, get_logging_file_path, strip_ansi


def test_get_dir_state(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / ".subdir").mkdir()
    (tmp_path / ".subdir" / "b.txt").write_text("y")

    result = get_dir_state(str(tmp_path))
    paths = {Path(p).name for p in result}

    assert "a.txt" in paths
    assert "b.txt" not in paths


def test_strip_ansi():
    assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"
    assert strip_ansi("plain text") == "plain text"
    assert strip_ansi("\x1b[1;32mbold green\x1b[0m") == "bold green"


def test_get_logging_file_path_missing_ini():
    with patch("multi_ai_gui.utils.os.path.exists", return_value=False):
        assert get_logging_file_path() is None


def test_get_logging_file_path_invalid_config():
    with (
        patch("multi_ai_gui.utils.os.path.exists", return_value=True),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.read",
            side_effect=configparser.Error,
        ),
    ):
        assert get_logging_file_path() is None


def test_get_logging_file_path_no_section():
    with (
        patch("multi_ai_gui.utils.os.path.exists", return_value=True),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.has_section",
            return_value=False,
        ),
    ):
        assert get_logging_file_path() is None


def test_get_logging_file_path_disabled():
    with (
        patch("multi_ai_gui.utils.os.path.exists", return_value=True),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.has_section",
            return_value=True,
        ),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.getboolean",
            return_value=False,
        ),
    ):
        assert get_logging_file_path() is None


def test_get_logging_file_path_success():
    with (
        patch("multi_ai_gui.utils.os.path.exists", return_value=True),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.has_section",
            return_value=True,
        ),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.getboolean", return_value=True
        ),
        patch(
            "multi_ai_gui.utils.configparser.ConfigParser.get",
            side_effect=["logs", "app.log"],
        ),
    ):
        path = get_logging_file_path()
        assert path is not None
        assert path.endswith("logs/app.log")
