import os
import shutil
import tempfile
from typing import Any

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
        f.write("Hello world\nThis is a test\nHello world again\n")

    result = replace_in_file(
        file={"path": file_path, "old_text": "Hello world", "new_text": "Hello ZRB"}
    )

    assert result == f"Successfully applied replacement(s) to {file_path}"

    with open(file_path, "r") as f:
        content = f.read()
    # Default behavior: replace ALL occurrences
    assert content == "Hello ZRB\nThis is a test\nHello ZRB again\n"


def test_replace_in_file_with_count(temp_dir):
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Hello world\nThis is a test\nHello world again\n")

    result = replace_in_file(
        file={
            "path": file_path,
            "old_text": "Hello world",
            "new_text": "Hello ZRB",
            "count": 1,
        }
    )

    assert result == f"Successfully applied replacement(s) to {file_path}"

    with open(file_path, "r") as f:
        content = f.read()
    # Count=1 behavior: replace ONLY FIRST occurrence
    assert content == "Hello ZRB\nThis is a test\nHello world again\n"


def test_replace_in_file_multiple_replacements(temp_dir):
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Hello world\nThis is a test\n")

    result = replace_in_file(
        file=[
            {"path": file_path, "old_text": "Hello world", "new_text": "Hello ZRB"},
            {
                "path": file_path,
                "old_text": "This is a test",
                "new_text": "This is a success",
            },
        ]
    )

    assert isinstance(result, dict)
    assert file_path in result["success"]

    with open(file_path, "r") as f:
        content = f.read()
    assert content == "Hello ZRB\nThis is a success\n"


def test_replace_in_file_not_found(temp_dir):
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Hello world\nThis is a test\n")

    with pytest.raises(RuntimeError) as excinfo:
        replace_in_file(
            file={"path": file_path, "old_text": "Not found", "new_text": "Hello ZRB"}
        )
    assert "old_text not found in file" in str(excinfo.value)


def test_replace_in_file_file_not_found(temp_dir):
    file_path = os.path.join(temp_dir, "non_existent_file.txt")
    with pytest.raises(RuntimeError) as excinfo:
        replace_in_file(
            file={"path": file_path, "old_text": "Hello world", "new_text": "Hello ZRB"}
        )
    assert "File not found" in str(excinfo.value)
