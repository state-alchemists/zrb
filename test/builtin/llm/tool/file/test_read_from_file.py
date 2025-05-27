import json
import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import read_from_file


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing file operations."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for reading tests."""
    path = os.path.join(temp_dir, "sample.txt")
    content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    create_file(path, content)
    return path


def create_file(path, content=""):
    """Helper to create a file with optional content."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_read_from_file_full(sample_file):
    result = read_from_file(path=sample_file)
    data = json.loads(result)
    assert data["path"] == sample_file
    assert (
        data["content"] == "1 | Line 1\n2 | Line 2\n3 | Line 3\n4 | Line 4\n5 | Line 5"
    )
    assert data["start_line"] == 1
    assert data["end_line"] == 5
    assert data["total_lines"] == 5


def test_read_from_file_partial(sample_file):
    result = read_from_file(path=sample_file, start_line=2, end_line=4)
    data = json.loads(result)
    assert data["path"] == sample_file
    assert data["content"] == "2 | Line 2\n3 | Line 3\n4 | Line 4"
    assert data["start_line"] == 2
    assert data["end_line"] == 4
    assert data["total_lines"] == 5


def test_read_from_file_start_only(sample_file):
    result = read_from_file(path=sample_file, start_line=4)
    data = json.loads(result)
    assert data["content"] == "4 | Line 4\n5 | Line 5"
    assert data["start_line"] == 4
    assert data["end_line"] == 5
    assert data["total_lines"] == 5


def test_read_from_file_end_only(sample_file):
    result = read_from_file(path=sample_file, end_line=2)
    data = json.loads(result)
    assert data["content"] == "1 | Line 1\n2 | Line 2"
    assert data["start_line"] == 1
    assert data["end_line"] == 2
    assert data["total_lines"] == 5


def test_read_from_file_single_line(sample_file):
    result = read_from_file(path=sample_file, start_line=3, end_line=3)
    data = json.loads(result)
    assert data["content"] == "3 | Line 3"
    assert data["start_line"] == 3
    assert data["end_line"] == 3
    assert data["total_lines"] == 5


def test_read_from_file_invalid_range(sample_file):
    # Start > End
    result = read_from_file(path=sample_file, start_line=4, end_line=2)
    data = json.loads(result)
    assert data["content"] == ""  # Empty content for invalid range
    assert data["start_line"] == 3
    assert data["end_line"] == 2
    assert data["total_lines"] == 5

    # Start < 1
    result = read_from_file(path=sample_file, start_line=0, end_line=2)
    data = json.loads(result)
    assert data["content"] == "1 | Line 1\n2 | Line 2"  # Corrected to 1
    assert data["start_line"] == 1  # Corrected to 1
    assert data["end_line"] == 2
    assert data["total_lines"] == 5

    # End > total_lines
    result = read_from_file(path=sample_file, start_line=4, end_line=10)
    data = json.loads(result)
    assert data["content"] == "4 | Line 4\n5 | Line 5"
    assert data["start_line"] == 4  # Corrected to total_lines
    assert data["end_line"] == 5  # Corrected to total_lines
    assert data["total_lines"] == 5


def test_read_from_file_not_exist(temp_dir):
    non_existent_path = os.path.join(temp_dir, "not_a_file.txt")
    with pytest.raises(FileNotFoundError, match="File not found:"):
        read_from_file(path=non_existent_path)


def test_read_from_file_empty(temp_dir):
    empty_path = os.path.join(temp_dir, "empty.txt")
    create_file(empty_path, "")
    result = read_from_file(path=empty_path)
    data = json.loads(result)
    assert data["path"] == empty_path  # Empty file content is empty string
    assert data["content"] == ""  # Empty file content is empty string
    assert data["start_line"] == 1  # end_idx is 0 for empty file
    assert data["end_line"] == 0  # end_idx is 0 for empty file
    assert data["total_lines"] == 0


def test_read_from_file_os_error(sample_file, monkeypatch):
    """Test handling of OSError during file reading."""

    def mock_read_file_with_line_numbers(*args, **kwargs):
        raise OSError("Simulated OS error")

    monkeypatch.setattr(
        "zrb.builtin.llm.tool.file.read_file_with_line_numbers",
        mock_read_file_with_line_numbers,
    )

    with pytest.raises(OSError, match="Error reading file"):
        read_from_file(path=sample_file)


def test_read_from_file_io_error(sample_file, monkeypatch):
    """Test handling of IOError during file reading."""

    def mock_read_file_with_line_numbers(*args, **kwargs):
        raise IOError("Simulated IO error")

    monkeypatch.setattr(
        "zrb.builtin.llm.tool.file.read_file_with_line_numbers",
        mock_read_file_with_line_numbers,
    )

    with pytest.raises(
        OSError, match="Error reading file"
    ):  # IOError is a subclass of OSError
        read_from_file(path=sample_file)


def test_read_from_file_generic_exception(sample_file, monkeypatch):
    """Test handling of unexpected generic exceptions during file reading."""

    def mock_read_file_with_line_numbers(*args, **kwargs):
        raise Exception("Simulated unexpected error")

    monkeypatch.setattr(
        "zrb.builtin.llm.tool.file.read_file_with_line_numbers",
        mock_read_file_with_line_numbers,
    )

    with pytest.raises(RuntimeError, match="Unexpected error reading file"):
        read_from_file(path=sample_file)
