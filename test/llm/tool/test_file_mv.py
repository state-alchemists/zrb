import os

import pytest

from zrb.llm.tool.file_mv import move_file


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_mv"
    d.mkdir()
    return str(d)


def test_move_file(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    open(src, "w").close()
    result = move_file(src, dst)
    assert "Moved" in result
    assert not os.path.exists(src)
    assert os.path.exists(dst)


def test_rename_file(temp_dir):
    src = os.path.join(temp_dir, "old.txt")
    dst = os.path.join(temp_dir, "new.txt")
    with open(src, "w") as f:
        f.write("content")
    result = move_file(src, dst)
    assert "Moved" in result
    with open(dst) as f:
        assert f.read() == "content"


def test_move_file_creates_parent_dirs(temp_dir):
    src = os.path.join(temp_dir, "src.txt")
    dst = os.path.join(temp_dir, "nested", "deep", "dst.txt")
    open(src, "w").close()
    result = move_file(src, dst)
    assert "Moved" in result
    assert os.path.exists(dst)


def test_move_directory(temp_dir):
    src = os.path.join(temp_dir, "srcdir")
    os.mkdir(src)
    open(os.path.join(src, "file.txt"), "w").close()
    dst = os.path.join(temp_dir, "dstdir")
    result = move_file(src, dst)
    assert "Moved" in result
    assert not os.path.exists(src)
    assert os.path.exists(os.path.join(dst, "file.txt"))


def test_move_nonexistent_source(temp_dir):
    src = os.path.join(temp_dir, "ghost.txt")
    dst = os.path.join(temp_dir, "dst.txt")
    result = move_file(src, dst)
    assert "Error" in result
    assert "not found" in result
