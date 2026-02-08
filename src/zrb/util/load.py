import importlib
import importlib.util
import os
import sys
from types import ModuleType

from zrb.context.any_context import zrb_print


def _get_new_python_path(path_to_add: str) -> str:
    current_python_path = os.environ.get("PYTHONPATH", "")
    paths = current_python_path.split(os.pathsep) if current_python_path else []
    if path_to_add not in paths:
        # Append to the end
        return os.pathsep.join(paths + [path_to_add]) if paths else path_to_add
    return current_python_path


def load_module(name: str) -> ModuleType:
    return importlib.import_module(name)


def load_file(path: str, max_depth: int = -1) -> ModuleType | None:
    # max_depth is kept for signature compatibility but ignored in this simple implementation
    if not os.path.exists(path):
        return None

    try:
        abs_path = os.path.abspath(path)
        directory = os.path.dirname(abs_path)

        # Add to sys.path if not present
        if directory not in sys.path:
            sys.path.append(directory)

        # Update PYTHONPATH
        new_python_path = _get_new_python_path(directory)
        if new_python_path != os.environ.get("PYTHONPATH", ""):
            os.environ["PYTHONPATH"] = new_python_path

        module_name = os.path.splitext(os.path.basename(path))[0]

        # Use load_module_from_path logic but we also wanted sys.path side effects above
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    except Exception as e:
        zrb_print(f"Error loading file {path}: {e}", plain=True)
        return None


def load_module_from_path(name: str, path: str) -> ModuleType | None:
    """
    Dynamically load a Python module from a file path without necessarily modifying sys.path permanently,
    though imports within the module might require it.
    """
    if not os.path.exists(path):
        return None

    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        zrb_print(f"Error loading module {name} from {path}: {e}", plain=True)
        return None
