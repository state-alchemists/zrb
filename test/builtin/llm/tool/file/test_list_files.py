import json
import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import _is_hidden, list_files


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


def test_list_files_non_recursive(temp_dir):
    create_file(os.path.join(temp_dir, "file1.txt"))
    create_file(os.path.join(temp_dir, ".hiddenfile"))
    os.makedirs(os.path.join(temp_dir, "subdir"))
    create_file(os.path.join(temp_dir, "subdir", "file2.txt"))
    os.makedirs(os.path.join(temp_dir, ".hiddendir"))

    # Default: non-recursive, exclude hidden
    data = list_files(path=temp_dir, recursive=False, include_hidden=False)
    assert sorted(data["files"]) == ["file1.txt", "subdir"]

    # Non-recursive, include hidden
    data = list_files(path=temp_dir, recursive=False, include_hidden=True)
    assert sorted(data["files"]) == [".hiddendir", ".hiddenfile", "file1.txt", "subdir"]


def test_list_files_recursive(temp_dir):
    create_file(os.path.join(temp_dir, "file1.txt"))
    create_file(os.path.join(temp_dir, ".hiddenfile"))
    os.makedirs(os.path.join(temp_dir, "subdir"))
    create_file(os.path.join(temp_dir, "subdir", "file2.txt"))
    create_file(os.path.join(temp_dir, "subdir", ".hiddenfile2"))
    os.makedirs(os.path.join(temp_dir, ".hiddendir"))
    create_file(os.path.join(temp_dir, ".hiddendir", "file3.txt"))

    # Recursive, exclude hidden
    data = list_files(path=temp_dir, recursive=True, include_hidden=False)
    # Note: os.path.join creates OS-specific paths
    expected = sorted(
        [
            "file1.txt",
            os.path.join("subdir", "file2.txt"),
        ]
    )
    assert sorted(data["files"]) == expected

    # Recursive, include hidden
    data = list_files(path=temp_dir, recursive=True, include_hidden=True)
    expected = sorted(
        [
            ".hiddenfile",
            os.path.join(".hiddendir", "file3.txt"),
            "file1.txt",
            os.path.join("subdir", ".hiddenfile2"),
            os.path.join("subdir", "file2.txt"),
        ]
    )
    assert sorted(data["files"]) == expected


def test_list_files_exclusions(temp_dir):
    create_file(os.path.join(temp_dir, "file1.txt"))
    create_file(os.path.join(temp_dir, "file.log"))
    os.makedirs(os.path.join(temp_dir, "node_modules"))
    create_file(os.path.join(temp_dir, "node_modules", "lib.js"))
    os.makedirs(os.path.join(temp_dir, "subdir"))
    create_file(os.path.join(temp_dir, "subdir", "data.txt"))
    create_file(os.path.join(temp_dir, "subdir", "another.log"))

    # Default exclusions (recursive) - node_modules should be excluded, .log should NOT
    data = list_files(path=temp_dir, recursive=True, include_hidden=False)
    expected = sorted(
        [
            "file1.txt",
            "file.log",  # .log is not in DEFAULT_EXCLUDED_PATTERNS
            os.path.join("subdir", "data.txt"),
            os.path.join(
                "subdir", "another.log"
            ),  # .log is not in DEFAULT_EXCLUDED_PATTERNS
        ]
    )
    # Filter out potential OS-specific hidden files if any created in temp
    actual = sorted([f for f in data["files"] if not _is_hidden(f)])  # Use the helper
    assert actual == expected

    # Custom exclusions (recursive)
    data = list_files(path=temp_dir, recursive=True, excluded_patterns=["*.txt"])
    expected = sorted(
        [
            "file.log",  # Default exclusions not applied here
            os.path.join(
                "node_modules", "lib.js"
            ),  # Default exclusions not applied here
            os.path.join(
                "subdir", "another.log"
            ),  # Default exclusions not applied here
        ]
    )
    # Filter out potential OS-specific hidden files if any created in temp
    actual = sorted([f for f in data["files"] if not f.startswith(".")])
    assert actual == expected

    # Exclude specific dir (non-recursive)
    data = list_files(path=temp_dir, recursive=False, excluded_patterns=["subdir"])
    expected = sorted(
        [
            "file.log",  # Default exclusions not applied here
            "file1.txt",
            "node_modules",  # Default exclusions not applied here
        ]
    )
    # Filter out potential OS-specific hidden files if any created in temp
    actual = sorted([f for f in data["files"] if not f.startswith(".")])
    assert actual == expected


def test_list_files_path_not_exist():
    # This should raise an OSError because the path doesn't exist
    with pytest.raises(OSError):
        list_files(path="/non/existent/path/hopefully")


def test_list_files_generic_exception(temp_dir, monkeypatch):
    """Test handling of unexpected generic exceptions during listing."""

    def mock_walk(*args, **kwargs):
        raise Exception("Simulated unexpected error")

    monkeypatch.setattr(os, "walk", mock_walk)

    with pytest.raises(RuntimeError, match="Unexpected error listing files in"):
        list_files(path=temp_dir)
