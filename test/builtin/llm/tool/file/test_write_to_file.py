import json
import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import write_to_file


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing file operations."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def create_file(path, content=""):
    """Helper to create a file with optional content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_write_to_file_create_new(temp_dir):
    """Test writing content to a new file."""
    file_path = os.path.join(temp_dir, "new_file.txt")
    content = "Hello\nWorld"

    result = write_to_file(path=file_path, content=content)
    data = result

    assert data["success"] is True
    assert data["path"] == file_path
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        assert f.read() == content


def test_write_to_file_overwrite_existing(temp_dir):
    """Test overwriting an existing file."""
    file_path = os.path.join(temp_dir, "existing_file.txt")
    create_file(file_path, "Initial content")

    new_content = "Overwritten\nContent"

    result = write_to_file(path=file_path, content=new_content)
    data = result

    assert data["success"] is True
    assert data["path"] == file_path
    with open(file_path, "r") as f:
        assert f.read() == new_content


def test_write_to_file_create_subdir(temp_dir):
    """Test writing to a file where the subdirectory needs to be created."""
    file_path = os.path.join(temp_dir, "subdir", "another_file.txt")
    content = "Content in subdir"

    result = write_to_file(path=file_path, content=content)
    data = result

    assert data["success"] is True
    assert data["path"] == file_path
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        assert f.read() == content


def test_write_to_file_empty_content(temp_dir):
    """Test writing empty content to a file."""
    file_path = os.path.join(temp_dir, "empty_file.txt")
    content = ""

    result = write_to_file(path=file_path, content=content)
    data = result

    assert data["success"] is True
    assert data["path"] == file_path
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        assert f.read() == ""


def test_write_to_file_invalid_path(temp_dir):
    """Test writing to an invalid path (e.g., permission denied - harder to simulate reliably).
    Instead, test writing to a path that looks like a directory."""
    parent_file = os.path.join(temp_dir, "parent_is_file.txt")
    create_file(parent_file, "I am a file")
    invalid_path = os.path.join(parent_file, "child.txt")
    content = "This should fail"

    with pytest.raises(OSError):
        write_to_file(path=invalid_path, content=content)


def test_write_to_file_generic_exception(temp_dir, monkeypatch):
    """Test handling of unexpected generic exceptions during writing."""

    def mock_write_file(*args, **kwargs):
        raise Exception("Simulated unexpected error")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.write_file", mock_write_file)

    file_path = os.path.join(temp_dir, "error_file.txt")
    content = "Some content"

    with pytest.raises(RuntimeError, match="Unexpected error writing file"):
        write_to_file(path=file_path, content=content)


def test_write_to_file_os_error(temp_dir, monkeypatch):
    """Test handling of OSError during writing."""

    def mock_write_file(*args, **kwargs):
        raise OSError("Simulated OS error")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.write_file", mock_write_file)

    file_path = os.path.join(temp_dir, "os_error_file.txt")
    content = "Some content"

    with pytest.raises(OSError, match="Error writing file"):
        write_to_file(path=file_path, content=content)
