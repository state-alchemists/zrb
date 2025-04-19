import os
import shutil
import tempfile

import pytest

from zrb.builtin.llm.tool.file import _is_hidden


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


def test_is_hidden():
    assert _is_hidden(".hidden_file") is True
    assert _is_hidden("visible_file") is False
    assert _is_hidden("path/to/.hidden_in_dir") is True  # Basename starts with .
    assert _is_hidden("path/to/visible_in_dir") is False
    assert _is_hidden(".") is False  # Special case '.'
    assert _is_hidden("..") is False  # Special case '..'
