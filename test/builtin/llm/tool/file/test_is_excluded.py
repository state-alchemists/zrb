import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import _is_excluded


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


def test_is_excluded():
    patterns = ["*.log", "__pycache__", "node_modules"]
    assert _is_excluded("app.log", patterns) is True
    assert _is_excluded("subdir/data.log", patterns) is True  # Checks parts
    assert _is_excluded("__pycache__", patterns) is True
    assert _is_excluded("src/__pycache__/some.pyc", patterns) is True  # Checks parts
    assert _is_excluded("node_modules", patterns) is True
    assert (
        _is_excluded("project/node_modules/lib/index.js", patterns) is True
    )  # Checks parts
    assert _is_excluded("main.py", patterns) is False
    assert _is_excluded("data.txt", patterns) is False
    assert _is_excluded("important_cache", patterns) is False
