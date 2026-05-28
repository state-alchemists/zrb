import os
from unittest.mock import patch

import pytest

from zrb.llm.tool.file_rm import remove_file


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_rm"
    d.mkdir()
    return str(d)


def test_remove_existing_file(temp_dir):
    path = os.path.join(temp_dir, "target.txt")
    open(path, "w").close()
    result = remove_file(path)
    assert "Removed" in result
    assert not os.path.exists(path)


def test_remove_nonexistent_path(temp_dir):
    path = os.path.join(temp_dir, "ghost.txt")
    result = remove_file(path)
    assert "Error" in result
    assert "not found" in result


def test_remove_empty_directory(temp_dir):
    d = os.path.join(temp_dir, "emptydir")
    os.mkdir(d)
    result = remove_file(d)
    assert "Removed empty directory" in result
    assert not os.path.exists(d)


def test_remove_nonempty_directory_without_recursive(temp_dir):
    d = os.path.join(temp_dir, "nonempty")
    os.mkdir(d)
    open(os.path.join(d, "file.txt"), "w").close()
    result = remove_file(d)
    assert "Error" in result
    assert "non-empty" in result
    assert os.path.exists(d)


def test_remove_nonempty_directory_with_recursive(temp_dir):
    d = os.path.join(temp_dir, "nonempty")
    os.mkdir(d)
    open(os.path.join(d, "file.txt"), "w").close()
    result = remove_file(d, recursive=True)
    assert "Removed directory recursively" in result
    assert not os.path.exists(d)


def test_remove_file_default_not_recursive(temp_dir):
    """recursive defaults to False — file removal still works normally."""
    path = os.path.join(temp_dir, "plain.txt")
    open(path, "w").close()
    result = remove_file(path)
    assert "Removed" in result
    assert not os.path.exists(path)


def test_remove_file_propagates_os_remove_error(temp_dir):
    """os.remove raising returns a clear error string rather than crashing."""
    path = os.path.join(temp_dir, "plain.txt")
    open(path, "w").close()
    with patch("zrb.llm.tool.file_rm.os.remove", side_effect=PermissionError("denied")):
        result = remove_file(path)
    assert "Error removing" in result
    assert "denied" in result


def test_remove_directory_recursive_propagates_rmtree_error(temp_dir):
    """shutil.rmtree raising returns a clear error string rather than crashing."""
    d = os.path.join(temp_dir, "boom")
    os.mkdir(d)
    open(os.path.join(d, "file.txt"), "w").close()
    with patch(
        "zrb.llm.tool.file_rm.shutil.rmtree",
        side_effect=PermissionError("denied"),
    ):
        result = remove_file(d, recursive=True)
    assert "Error removing directory" in result
    assert "denied" in result
