import pytest

from portable_agent_chat.files import (
    ensure_new_file,
    read_file,
    resolve_read_paths,
    write_file,
    write_new_file,
)


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


def test_resolve_read_paths(tmp_path):
    file1 = tmp_path / "a.txt"
    file1.write_text("1")
    file2 = tmp_path / "sub" / "b.txt"
    file2.parent.mkdir()
    file2.write_text("2")

    results = resolve_read_paths(str(tmp_path / "**/*.txt"))
    assert len(results) == 2
    assert file1 in results
    assert file2 in results


def test_resolve_read_paths_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="no files matched"):
        resolve_read_paths(str(tmp_path / "*.txt"))


def test_write_file_new_and_overwrite(tmp_path):
    out_file = tmp_path / "test.txt"

    # New
    size = write_file(str(out_file), "first")
    assert size == 5
    assert out_file.read_text() == "first"

    # Overwrite
    size = write_file(str(out_file), "second")
    assert size == 6
    assert out_file.read_text() == "second"


def test_write_file_is_directory(tmp_path):
    with pytest.raises(ValueError, match="not a file"):
        write_file(str(tmp_path), "content")
