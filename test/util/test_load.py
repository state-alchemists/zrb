import os
import sys
import tempfile

import pytest

from zrb.util.load import load_file, load_module


@pytest.fixture
def temp_script():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def hello(): return 'world'")
        path = f.name
    yield path
    os.remove(path)


def test_load_file_success(temp_script):
    # Capture original PYTHONPATH
    original_pythonpath = os.environ.get("PYTHONPATH")
    
    try:
        module = load_file(temp_script)
        assert module is not None
        assert module.hello() == "world"

        # Check path manipulation
        script_dir = os.path.dirname(temp_script)
        assert script_dir in sys.path
        
        # Check PYTHONPATH update
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        assert script_dir in current_pythonpath.split(os.pathsep)
    finally:
        # Restore PYTHONPATH
        if original_pythonpath is not None:
            os.environ["PYTHONPATH"] = original_pythonpath
        elif "PYTHONPATH" in os.environ:
            del os.environ["PYTHONPATH"]


def test_load_file_not_found():
    assert load_file("/non/existent/path.py") is None


def test_load_module_success():
    module = load_module("os")
    assert module is os


def test_load_module_fail():
    with pytest.raises(ImportError):
        load_module("non_existent_module_xyz")
