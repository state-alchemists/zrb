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
        return os.pathsep.join(paths + [path_to_add]) if paths else path_to_add
    return current_python_path


def load_module(name: str) -> ModuleType:
    return importlib.import_module(name)


def load_file(path: str, raise_on_error: bool = False) -> ModuleType | None:
    """Exec `path` as a module and return it.

    A broken file is reported and yields `None` by default — the lenient
    contract most callers (discovery of optional plugin/skill files) want.
    Pass `raise_on_error=True` for a call site that needs the real exception
    rather than a printed line and a `None` it may not even check — e.g.
    `zrb_init.py`'s loader (`_load_or_warn`), which reports the file, line,
    and exception type precisely rather than this function's own generic
    "Error loading file X: e" fallback.
    """
    if not os.path.exists(path):
        return None

    try:
        abs_path = os.path.abspath(path)
        directory = os.path.dirname(abs_path)

        if directory not in sys.path:
            sys.path.append(directory)

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
        if raise_on_error:
            raise
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
