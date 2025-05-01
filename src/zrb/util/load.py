import importlib
import importlib.util
import os
import re
import sys
from functools import lru_cache
from typing import Any

pattern = re.compile("[^a-zA-Z0-9]")


@lru_cache
def load_file(script_path: str, sys_path_index: int = 0) -> Any | None:
    """
    Load a Python module from a file path.

    Args:
        script_path (str): The path to the Python script.
        sys_path_index (int): The index to insert the script directory into sys.path.

    Returns:
        Any | None: The loaded module object, or None if the file does not
            exist or cannot be loaded.
    """
    if not os.path.isfile(script_path):
        return None
    module_name = pattern.sub("", script_path)
    # Append script dir path
    script_dir_path = os.path.dirname(script_path)
    if script_dir_path not in sys.path:
        if sys_path_index == -1:
            sys_path_index = len(sys.path)
        sys.path.insert(sys_path_index, script_dir_path)
    # Add script dir path to Python path
    os.environ["PYTHONPATH"] = _get_new_python_path(script_dir_path)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_new_python_path(dir_path: str) -> str:
    """
    Helper function to update the PYTHONPATH environment variable.

    Args:
        dir_path (str): The directory path to add to PYTHONPATH.

    Returns:
        str: The new value for the PYTHONPATH environment variable.
    """
    current_python_path = os.getenv("PYTHONPATH")
    if current_python_path is None or current_python_path == "":
        return dir_path
    if dir_path in current_python_path.split(":"):
        return current_python_path
    return ":".join([current_python_path, dir_path])


def load_module(module_name: str) -> Any:
    """
    Load a Python module by its name.

    Args:
        module_name (str): The name of the module to load.

    Returns:
        Any: The loaded module object.
    """
    module = importlib.import_module(module_name)
    return module
