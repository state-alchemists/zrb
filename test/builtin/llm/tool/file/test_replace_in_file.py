import json
import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import replace_in_file


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing file operations."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_replace_in_file_success(temp_dir):
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Hello world\nThis is a test\n")

    result = replace_in_file(
        path=file_path, old_string="Hello world", new_string="Hello ZRB"
    )

    assert result == {"success": True, "path": file_path}

    with open(file_path, "r") as f:
        content = f.read()
    assert content == "Hello ZRB\nThis is a test\n"


def test_replace_in_file_not_found(temp_dir):
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Hello world\nThis is a test\n")

    with pytest.raises(ValueError) as excinfo:
        replace_in_file(path=file_path, old_string="Not found", new_string="Hello ZRB")
    assert str(excinfo.value) == f"old_string not found in file: {file_path}"


def test_replace_in_file_file_not_found(temp_dir):
    file_path = os.path.join(temp_dir, "non_existent_file.txt")
    with pytest.raises(FileNotFoundError) as excinfo:
        replace_in_file(
            path=file_path, old_string="Hello world", new_string="Hello ZRB"
        )
    assert str(excinfo.value) == f"File not found: {file_path}"
