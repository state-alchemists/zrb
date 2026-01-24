import os
import shutil

import pytest

from zrb.llm.tool.file import (
    glob_files,
    list_files,
    read_file,
    replace_in_file,
    search_files,
    write_file,
)


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_file_tool"
    d.mkdir()
    return str(d)


def test_write_and_read_file(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    content = "hello world"

    # Test write_file
    res = write_file(file_path, content)
    assert "Successfully wrote to" in res
    assert os.path.exists(file_path)

    # Test read_file
    read_res = read_file(file_path)
    assert content in read_res


def test_list_files(temp_dir):
    os.makedirs(os.path.join(temp_dir, "subdir"))
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("1")
    with open(os.path.join(temp_dir, "subdir", "file2.txt"), "w") as f:
        f.write("2")

    res = list_files(temp_dir)
    files = res.get("files", [])
    assert "file1.txt" in files
    assert "subdir/file2.txt" in files


def test_glob_files(temp_dir):
    with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
        f.write("1")
    with open(os.path.join(temp_dir, "file2.log"), "w") as f:
        f.write("2")

    res = glob_files("*.txt", path=temp_dir)
    assert len(res) == 1
    assert "file1.txt" in res


def test_replace_in_file(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("hello world")

    res = replace_in_file(file_path, "world", "zrb")
    assert "Successfully updated" in res
    with open(file_path, "r") as f:
        assert f.read() == "hello zrb"


def test_search_files(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("hello world\nzrb is cool")

    res = search_files(temp_dir, "zrb")
    assert "Found 1 matches" in res.get("summary", "")
    assert len(res.get("results", [])) == 1
    assert res["results"][0]["file"] == os.path.relpath(file_path, os.getcwd())
