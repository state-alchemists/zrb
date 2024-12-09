import importlib
import importlib.util
import os
import re
import sys
from functools import lru_cache
from typing import Any

pattern = re.compile("[^a-zA-Z0-9]")


def load_zrb_init(dir_path: str | None = None) -> Any | None:
    if dir_path is None:
        dir_path = os.getcwd()
    script_path = os.path.join(dir_path, "zrb_init.py")
    if os.path.isfile(script_path):
        return load_file(script_path, -1)
    new_dir_path = os.path.dirname(dir_path)
    if new_dir_path == dir_path:
        return
    return load_zrb_init(new_dir_path)


@lru_cache
def load_file(script_path: str, sys_path_index: int = 0) -> Any | None:
    if not os.path.isfile(script_path):
        return None
    module_name = pattern.sub("", script_path)
    # Append script dir path
    script_dir_path = os.path.dirname(script_path)
    if script_dir_path not in sys.path:
        sys.path.insert(sys_path_index, script_dir_path)
    # Add script dir path to Python path
    os.environ["PYTHONPATH"] = _get_new_python_path(script_dir_path)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_new_python_path(dir_path: str) -> str:
    current_python_path = os.getenv("PYTHONPATH")
    if current_python_path is None or current_python_path == "":
        return dir_path
    if dir_path in current_python_path.split(":"):
        return current_python_path
    return ":".join([current_python_path, dir_path])


def load_module(module_name: str) -> Any:
    module = importlib.import_module(module_name)
    return module
