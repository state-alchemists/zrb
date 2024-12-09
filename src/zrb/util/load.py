import importlib
import importlib.util
import os
import re
import sys
from typing import Any

pattern = re.compile("[^a-zA-Z0-9]")

_module_names: dict[str, Any] = {}
_script_paths: dict[str, Any] = {}


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


def load_file(
    script_path: str, sys_path_index: int = 0, reload: bool = False
) -> Any | None:
    if not os.path.isfile(script_path):
        return None
    if script_path in _script_paths and not reload:
        return _script_paths[script_path]
    module_name = pattern.sub("", script_path)
    if module_name not in sys.modules:
        # Append script dir path
        script_dir_path = os.path.dirname(script_path)
        if script_dir_path not in sys.path:
            sys.path.insert(sys_path_index, script_dir_path)
        # Add script dir path to Python path
        os.environ["PYTHONPATH"] = _get_new_python_path(script_dir_path)
    if reload and module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _script_paths[script_path] = module
    return module


def _get_new_python_path(dir_path: str) -> str:
    current_python_path = os.getenv("PYTHONPATH")
    if current_python_path is None or current_python_path == "":
        return dir_path
    if dir_path in current_python_path.split(":"):
        return current_python_path
    return ":".join([current_python_path, dir_path])


def load_module(module_name: str, reload: bool = False) -> Any:
    if module_name in _module_names and not reload:
        return _module_names[module_name]
    if reload and module_name in sys.modules:
        del sys.modules[module_name]
    module = importlib.import_module(module_name)
    _module_names[module_name] = module
    return module
