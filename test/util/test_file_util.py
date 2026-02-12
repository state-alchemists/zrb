import os

import pytest

from zrb.util.file import is_path_excluded, list_files, read_file, write_file


def test_is_path_excluded():
    patterns = ["*.pyc", "__pycache__", "node_modules"]
    assert is_path_excluded("test.pyc", patterns) is True
    assert is_path_excluded("src/test.py", patterns) is False
    assert is_path_excluded("node_modules/abc", patterns) is True
    assert is_path_excluded("__pycache__", patterns) is True


def test_read_file_with_replace(tmp_path):
    d = tmp_path / "test_read"
    d.mkdir()
    f = d / "test.txt"
    f.write_text("hello world", encoding="utf-8")

    content = read_file(str(f), replace_map={"world": "zrb"})
    assert content == "hello zrb"


def test_read_binary_file_as_base64(tmp_path):
    d = tmp_path / "test_binary"
    d.mkdir()
    f = d / "test.bin"
    # Use bytes that are definitely invalid UTF-8 (e.g. 0xff)
    invalid_utf8 = b"\xff\xfe\xfd"
    f.write_bytes(invalid_utf8)

    # read_file falls back to base64 if it fails to read as text
    content = read_file(str(f))
    import base64

    assert content == base64.b64encode(invalid_utf8).decode("ascii")


def test_write_file_list_content(tmp_path):
    d = tmp_path / "test_write"
    d.mkdir()
    f = d / "test.txt"
    write_file(str(f), ["line1", "line2", None, "line3"])

    with open(f, "r") as file:
        assert file.read() == "line1\nline2\nline3"


def test_write_file_mode(tmp_path):
    d = tmp_path / "test_mode"
    d.mkdir()
    f = d / "test.txt"
    write_file(str(f), "hello")
    write_file(str(f), " world", mode="a")

    with open(f, "r") as file:
        assert file.read() == "hello world"


def test_list_files_depth(tmp_path):
    # tmp_path/
    #   file1.txt
    #   subdir/
    #     file2.txt
    #     subsubdir/
    #       file3.txt
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    subsubdir = subdir / "subsubdir"
    subsubdir.mkdir()

    (tmp_path / "file1.txt").write_text("1")
    (subdir / "file2.txt").write_text("2")
    (subsubdir / "file3.txt").write_text("3")

    # depth 1: only file1.txt
    files1 = list_files(str(tmp_path), depth=1)
    assert "file1.txt" in files1
    assert "subdir/file2.txt" not in files1

    # depth 2: file1.txt and subdir/file2.txt
    files2 = list_files(str(tmp_path), depth=2)
    assert "file1.txt" in files2
    assert "subdir/file2.txt" in files2
    assert "subdir/subsubdir/file3.txt" not in files2
