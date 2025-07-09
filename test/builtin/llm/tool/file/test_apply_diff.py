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
    file_name = os.path.basename(sample_file)
    diff_content = f"""--- a/{file_name}
+++ b/{file_name}
@@ -2,3 +2,3 @@
 Line 2
-Line 3
+New Line 3
 Line 4
"""
    result = apply_diff(path=sample_file, diff_content=diff_content)
    data = json.loads(result)

    assert data["success"] is True
    assert data["path"] == sample_file

    with open(sample_file, "r") as f:
        content = f.read()
    expected_content = "Line 1\nLine 2\nNew Line 3\nLine 4\nLine 5"
    assert content == expected_content


def test_apply_diff_file_not_found(temp_dir):
    """Test applying diff to a non-existent file."""
    non_existent_path = os.path.join(temp_dir, "non_existent_file.txt")
    diff_content = "irrelevant"

    with pytest.raises(FileNotFoundError, match="File not found:"):
        apply_diff(path=non_existent_path, diff_content=diff_content)


def test_apply_diff_invalid_diff_content(sample_file):
    """Test applying a diff with invalid content."""
    # This diff is invalid because the context "Incorrect Line" does not match "Line 2"
    diff_content = """--- a/sample_for_diff.txt
+++ b/sample_for_diff.txt
@@ -2,3 +2,3 @@
 Incorrect Line
-Line 3
+New Line 3
 Line 4
"""
    result = apply_diff(path=sample_file, diff_content=diff_content)
    data = json.loads(result)

    assert data["success"] is False
    assert "error" in data
    assert "Could not apply hunk" in data["error"]
    # Check that the file was not modified
    with open(sample_file, "r") as f:
        content = f.read()
    assert content == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"


def test_apply_diff_preserves_trailing_newline(temp_dir):
    """Test that apply_diff preserves a trailing newline if one existed."""
    path = os.path.join(temp_dir, "trailing_newline.txt")
    file_name = os.path.basename(path)
    content = "Line 1\nLine 2\nLine 3\n"
    create_file(path, content)

    diff_content = f"""--- a/{file_name}
+++ b/{file_name}
@@ -1,3 +1,3 @@
 Line 1
-Line 2
+Line Two
 Line 3
"""

    result = apply_diff(path=path, diff_content=diff_content)
    data = json.loads(result)
    assert data["success"] is True

    with open(path, "r") as f:
        final_content = f.read()

    expected_content = "Line 1\nLine Two\nLine 3\n"
    assert final_content == expected_content


def test_apply_diff_adds_trailing_newline_if_missing(temp_dir):
    """Test that apply_diff does not add a trailing newline if one was not present."""
    path = os.path.join(temp_dir, "no_trailing_newline.txt")
    file_name = os.path.basename(path)
    content = "Line 1\nLine 2\nLine 3"
    create_file(path, content)

    diff_content = f"""--- a/{file_name}
+++ b/{file_name}
@@ -1,3 +1,3 @@
 Line 1
-Line 2
+Line Two
 Line 3
"""
    result = apply_diff(path=path, diff_content=diff_content)
    data = json.loads(result)
    assert data["success"] is True

    with open(path, "r") as f:
        final_content = f.read()

    expected_content = "Line 1\nLine Two\nLine 3"
    assert final_content == expected_content
