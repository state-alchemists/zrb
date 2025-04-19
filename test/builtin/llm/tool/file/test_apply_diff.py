import json
import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import apply_diff


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


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for apply_diff tests."""
    path = os.path.join(temp_dir, "sample_for_diff.txt")
    content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    create_file(path, content)
    return path


def test_apply_diff_success(sample_file):
    """Test successful application of a diff."""
    search_content = "Line 2\nLine 3"
    replace_content = "Inserted Line 2.5\nNew Line 3"
    start_line = 2
    end_line = 3

    result = apply_diff(
        path=sample_file,
        start_line=start_line,
        end_line=end_line,
        search_content=search_content,
        replace_content=replace_content,
    )
    data = json.loads(result)

    assert data["success"] is True
    assert data["path"] == sample_file

    with open(sample_file, "r") as f:
        content = f.read()
    expected_content = "Line 1\nInserted Line 2.5\nNew Line 3\nLine 4\nLine 5"
    assert content == expected_content


def test_apply_diff_file_not_found(temp_dir):
    """Test applying diff to a non-existent file."""
    non_existent_path = os.path.join(temp_dir, "non_existent_file.txt")
    search_content = "Line 1"
    replace_content = "New Line 1"
    start_line = 1
    end_line = 1

    result = apply_diff(
        path=non_existent_path,
        start_line=start_line,
        end_line=end_line,
        search_content=search_content,
        replace_content=replace_content,
    )
    data = json.loads(result)

    assert data["success"] is False
    assert data["path"] == non_existent_path
    assert "error" in data
    assert "File not found" in data["error"]


def test_apply_diff_invalid_line_range(sample_file):
    """Test applying diff with invalid line ranges."""
    search_content = "Line 1"
    replace_content = "New Line 1"

    # Start line < 1
    result = apply_diff(
        path=sample_file,
        start_line=0,
        end_line=1,
        search_content=search_content,
        replace_content=replace_content,
    )
    data = json.loads(result)
    assert data["success"] is False
    assert "error" in data
    assert "Invalid line range" in data["error"]

    # End line > total lines
    result = apply_diff(
        path=sample_file,
        start_line=1,
        end_line=10,
        search_content=search_content,
        replace_content=replace_content,
    )
    data = json.loads(result)
    assert data["success"] is False
    assert "error" in data
    assert "Invalid line range" in data["error"]

    # Start line > End line
    result = apply_diff(
        path=sample_file,
        start_line=3,
        end_line=1,
        search_content="Line 3",
        replace_content="New Line 3",
    )
    data = json.loads(result)
    assert data["success"] is False
    assert "error" in data
    assert "Invalid line range" in data["error"]


def test_apply_diff_search_content_mismatch(sample_file):
    """Test applying diff when search content does not match."""
    search_content = "Incorrect content"
    replace_content = "New content"
    start_line = 2
    end_line = 2

    result = apply_diff(
        path=sample_file,
        start_line=start_line,
        end_line=end_line,
        search_content=search_content,
        replace_content=replace_content,
    )
    data = json.loads(result)

    assert data["success"] is False
    assert "error" in data
    assert "Search content does not match file content" in data["error"]


def test_apply_diff_os_error_read(sample_file, monkeypatch):
    """Test handling of OSError during file reading in apply_diff."""

    def mock_read_file(*args, **kwargs):
        raise OSError("Simulated OS error during read")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.read_file", mock_read_file)

    search_content = "Line 1"
    replace_content = "New Line 1"
    start_line = 1
    end_line = 1

    with pytest.raises(OSError, match="Error applying diff to"):
        apply_diff(
            path=sample_file,
            start_line=start_line,
            end_line=end_line,
            search_content=search_content,
            replace_content=replace_content,
        )


def test_apply_diff_io_error_read(sample_file, monkeypatch):
    """Test handling of IOError during file reading in apply_diff."""

    def mock_read_file(*args, **kwargs):
        raise IOError("Simulated IO error during read")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.read_file", mock_read_file)

    with pytest.raises(
        OSError, match="Error applying diff to"
    ):  # IOError is a subclass of OSError
        apply_diff(
            path=sample_file,
            start_line=1,
            end_line=1,
            search_content="Line 1",
            replace_content="New Line 1",
        )


def test_apply_diff_os_error_write(sample_file, monkeypatch):
    """Test handling of OSError during file writing in apply_diff."""

    def mock_write_file(*args, **kwargs):
        raise OSError("Simulated OS error during write")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.write_file", mock_write_file)

    search_content = "Line 1"
    replace_content = "New Line 1"
    start_line = 1
    end_line = 1

    with pytest.raises(OSError, match="Error applying diff to"):
        apply_diff(
            path=sample_file,
            start_line=start_line,
            end_line=end_line,
            search_content=search_content,
            replace_content=replace_content,
        )


def test_apply_diff_io_error_write(sample_file, monkeypatch):
    """Test handling of IOError during file writing in apply_diff."""

    def mock_write_file(*args, **kwargs):
        raise IOError("Simulated IO error during write")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.write_file", mock_write_file)

    with pytest.raises(
        OSError, match="Error applying diff to"
    ):  # IOError is a subclass of OSError
        apply_diff(
            path=sample_file,
            start_line=1,
            end_line=1,
            search_content="Line 1",
            replace_content="New Line 1",
        )


def test_apply_diff_generic_exception(sample_file, monkeypatch):
    """Test handling of unexpected generic exceptions in apply_diff."""

    # Mock read_file to raise a generic exception
    def mock_read_file(*args, **kwargs):
        raise Exception("Simulated unexpected error during read")

    monkeypatch.setattr("zrb.builtin.llm.tool.file.read_file", mock_read_file)

    search_content = "Line 1"
    replace_content = "New Line 1"
    start_line = 1
    end_line = 1

    with pytest.raises(RuntimeError, match="Unexpected error applying diff to"):
        apply_diff(
            path=sample_file,
            start_line=start_line,
            end_line=end_line,
            search_content=search_content,
            replace_content=replace_content,
        )

    # You could also add a test mocking write_file to raise a generic exception
    # if you want to be extra thorough, but the structure is similar.
