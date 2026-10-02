import pytest

from portable_agent_chat.files import ensure_new_file, read_file, write_new_file


def test_read_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, AI!", encoding="utf-8")

    assert read_file(str(test_file)) == "Hello, AI!"


def test_read_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="file not found"):
        read_file(str(tmp_path / "missing.txt"))


def test_read_file_is_directory(tmp_path):
    with pytest.raises(ValueError, match="not a file"):
        read_file(str(tmp_path))


def test_write_new_file(tmp_path):
    out_file = tmp_path / "nested" / "output.txt"

    size = write_new_file(str(out_file), "test output")

    assert size == 11
    assert out_file.read_text(encoding="utf-8") == "test output"


def test_write_new_file_exists(tmp_path):
    out_file = tmp_path / "exists.txt"
    out_file.write_text("some content")

    with pytest.raises(FileExistsError, match="file already exists"):
        write_new_file(str(out_file), "new content")


def test_ensure_new_file(tmp_path):
    target_file = tmp_path / "new.txt"
    ensure_new_file(str(target_file))  # 例外が発生しないこと

    target_file.write_text("exists")
    with pytest.raises(FileExistsError, match="file already exists"):
        ensure_new_file(str(target_file))
