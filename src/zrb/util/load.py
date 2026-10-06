import importlib
import importlib.util
import os
import sys
from collections.abc import Callable
from importlib.abc import Loader
from types import ModuleType

from zrb.context.any_context import zrb_print


def _get_new_python_path(path_to_add: str) -> str:
    current_python_path = os.environ.get("PYTHONPATH", "")
    paths = current_python_path.split(os.pathsep) if current_python_path else []
    if path_to_add not in paths:
        return os.pathsep.join(paths + [path_to_add]) if paths else path_to_add
    return current_python_path


def _execute(run: Callable[[], object]) -> Exception | None:
    """Run *run* and hand back whatever it raised, or None when it succeeded."""
    try:
        run()
    except Exception as error:
        return error
    return None


def load_module(name: str) -> ModuleType:
    return importlib.import_module(name)


def load_module_with_result(
    name: str,
) -> tuple[ModuleType | None, Exception | None]:
    """Import *name* and return `(module, error)`.

    The error is returned rather than raised. A partially initialized module
    is included when `sys.modules` kept it.
    """
    error = _execute(lambda: load_module(name))
    return sys.modules.get(name), error


def load_file(path: str, raise_on_error: bool = False) -> ModuleType | None:
    """Exec `path` as a module and return it.

    A broken file is reported and yields `None`, unless `raise_on_error=True`.
    """
    if not os.path.exists(path):
        return None

    try:
        abs_path, module_name = _prepare_file(path)
        return _exec_module_file(module_name, abs_path)
    except Exception as e:
        if raise_on_error:
            raise
        zrb_print(f"Error loading file {path}: {e}", plain=True)
        return None


def load_file_with_result(path: str) -> tuple[ModuleType | None, Exception | None]:
    """Exec *path* and return `(module, error)`.

    The module is returned even when exec raised: declarations that ran
    before the failure are already live in the CLI tree.
    """
    if not os.path.exists(path):
        return None, None
    loaded: list[ModuleType] = []

    def run() -> None:
        abs_path, module_name = _prepare_file(path)
        module, loader = _create_module(module_name, abs_path)
        if module is None or loader is None:
            return
        loaded.append(module)
        loader.exec_module(module)

    error = _execute(run)
    return (loaded[0] if loaded else None), error


def load_module_from_path(name: str, path: str) -> ModuleType | None:
    """Load a Python module from a file path without touching `sys.path`
    (imports inside the module may still need it)."""
    if not os.path.exists(path):
        return None
    try:
        return _exec_module_file(name, path)
    except Exception as e:
        zrb_print(f"Error loading module {name} from {path}: {e}", plain=True)
        return None


def _prepare_file(path: str) -> tuple[str, str]:
    """Make `path`'s directory importable and return `(abs_path, module_name)`."""
    abs_path = os.path.abspath(path)
    directory = os.path.dirname(abs_path)

    if directory not in sys.path:
        sys.path.append(directory)

    new_python_path = _get_new_python_path(directory)
    if new_python_path != os.environ.get("PYTHONPATH", ""):
        os.environ["PYTHONPATH"] = new_python_path

    return abs_path, os.path.splitext(os.path.basename(path))[0]


def _create_module(name: str, path: str) -> tuple[ModuleType | None, Loader | None]:
    """Build module *name* from *path*, registered in `sys.modules` but unexec'd.

    Registering before exec lets a module that imports itself during its own
    body resolve. Returns `(None, None)` when the path yields no loader.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None, None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    return module, spec.loader


def _exec_module_file(name: str, path: str) -> ModuleType | None:
    """Exec *path* as module *name*, registered in `sys.modules`."""
    module, loader = _create_module(name, path)
    if module is None or loader is None:
        return None
    loader.exec_module(module)
    return module
