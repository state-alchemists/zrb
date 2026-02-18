import os
import sys
from unittest.mock import patch

from zrb.util.load import _get_new_python_path, load_file, load_module_from_path


def test_get_new_python_path_already_exists():
    with patch.dict(os.environ, {"PYTHONPATH": "/some/path"}):
        assert _get_new_python_path("/some/path") == "/some/path"


def test_load_file_nonexistent():
    assert load_file("nonexistent.py") is None


def test_load_file_exception():
    # Trigger exception by passing a directory instead of a file to spec_from_file_location
    with patch("os.path.exists", return_value=True):
        assert load_file("/") is None


def test_load_module_from_path_success():
    # Create a temp python file
    with open("temp_mod.py", "w") as f:
        f.write("x = 10")
    try:
        mod = load_module_from_path("temp_mod", os.path.abspath("temp_mod.py"))
        assert mod.x == 10
    finally:
        if os.path.exists("temp_mod.py"):
            os.remove("temp_mod.py")


def test_load_module_from_path_nonexistent():
    assert load_module_from_path("name", "nonexistent.py") is None


def test_load_module_from_path_exception():
    with patch("os.path.exists", return_value=True):
        assert load_module_from_path("name", "/") is None
