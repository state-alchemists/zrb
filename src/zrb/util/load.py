import importlib
import importlib.util
import os
import sys
import threading
import traceback
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from importlib.abc import Loader
from types import ModuleType
from typing import cast

from zrb.context.any_context import zrb_print

# A loaded file's declarations need a stable `__module__` for pickle, typing and
# `inspect`, but its bare stem must not answer later imports. The identity below
# is the name those declarations carry instead: unique, and kept in `sys.modules`
# so resolving an object's module still works after the load.
_IDENTITY_PREFIX = "_zrb_loaded_"
_IDENTITY_LOCK = threading.RLock()
_MISSING = object()

# Not the user's code: zrb itself, and the interpreter's stdlib and
# installed packages.
_NOT_USER_DIRS = tuple(
    os.path.join(os.path.realpath(path), "")
    for path in {
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
    }
)


def get_user_frames(
    error: BaseException,
) -> tuple[traceback.FrameSummary, traceback.FrameSummary]:
    """The deepest frame of *error* in the user's code, and the frame that
    raised it.

    A mistake in a `zrb_init.py` (a misspelled keyword, a bad `json.loads`) is
    usually raised inside zrb, the stdlib or a package, but the line to fix is
    the user's call site. Both are the raising frame when no frame is the
    user's.
    """
    frames = traceback.extract_tb(error.__traceback__)
    outside = [
        frame
        for frame in frames
        if not frame.filename.startswith("<")
        and not os.path.realpath(frame.filename).startswith(_NOT_USER_DIRS)
    ]
    raising = frames[-1]
    return (outside[-1] if outside else raising), raising


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

    The module's declarations are given a private `__module__` identity so
    `pickle`, `typing.get_type_hints` and `inspect.getmodule` keep working after
    the file's body has run. The file's bare stem is not left in `sys.modules`;
    a later `import <stem>` is a fresh import from disk, exactly as any other
    temporary import would be.
    """
    if not os.path.exists(path):
        return None

    try:
        abs_path, module_name = _prepare_file(path)
        return _exec_module_file(module_name, abs_path, adopt_identity=True)
    except Exception as e:
        if raise_on_error:
            raise
        zrb_print(f"Error loading file {path}: {e}", plain=True)
        return None


def load_file_with_result(path: str) -> tuple[ModuleType | None, Exception | None]:
    """Exec *path* and return `(module, error)`.

    The module is returned even when exec raised: declarations that ran
    before the failure are already live in the CLI tree. Its declarations get
    the same private `__module__` identity as `load_file`, so a partial load is
    still introspectable without the file's stem shadowing a real module.
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
        _exec_module(module, loader, module_name, adopt_identity=True)

    error = _execute(run)
    return (loaded[0] if loaded else None), error


def load_module_from_path(name: str, path: str) -> ModuleType | None:
    """Load a Python module from a file path without touching `sys.path`
    (imports inside the module may still need it).

    Unlike `load_file`, the caller supplies a unique *name* and that name is
    kept in `sys.modules` after the body runs: the hook, skill and agent loaders
    use a UUID-suffixed name that cannot shadow a real module, and their
    definitions need a module object they can be resolved through later.
    """
    if not os.path.exists(path):
        return None
    try:
        return _exec_module_file(name, path, keep_name=True)
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
    """Build module *name* from *path* and leave it unexec'd.

    Returns `(None, None)` when the path yields no loader.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None, None
    return importlib.util.module_from_spec(spec), spec.loader


@contextmanager
def _registered(name: str, module: ModuleType) -> Iterator[None]:
    """Hold *module* under *name* while the body runs, then give the name back.

    A file loaded from disk is not the process's module for its bare name. A
    hook file called `openai.py` used to answer every later `import openai`,
    and every `zrb_init.py` leaves the name of the next one waiting behind it.
    The entry exists only while the body runs, which is what lets a file import
    itself during its own body; whatever held the name before is restored
    afterwards, and a name that held nothing is dropped again.
    """
    previous = sys.modules.get(name, _MISSING)
    sys.modules[name] = module
    try:
        yield
    finally:
        if previous is _MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = cast("ModuleType", previous)


def _exec_module_file(
    name: str,
    path: str,
    *,
    adopt_identity: bool = False,
    keep_name: bool = False,
) -> ModuleType | None:
    """Exec *path* as module *name*, holding the name while the body runs."""
    module, loader = _create_module(name, path)
    if module is None or loader is None:
        return None
    _exec_module(
        module,
        loader,
        name,
        adopt_identity=adopt_identity,
        keep_name=keep_name,
    )
    return module


def _exec_module(
    module: ModuleType,
    loader: Loader,
    name: str,
    *,
    adopt_identity: bool = False,
    keep_name: bool = False,
) -> None:
    """Exec *module* under *name* and settle what happens to the name after.

    The load lock is held across the body: two same-stem files loaded at once
    would otherwise share the temporary `sys.modules` entry, and one body could
    import the other's module or lose its own entry to the other's cleanup.
    """
    with _IDENTITY_LOCK:
        kept = False
        try:
            with _registered(name, module):
                loader.exec_module(module)
            kept = True
        finally:
            if adopt_identity:
                _adopt_identity(module, name)
            elif keep_name and kept:
                sys.modules[name] = module


def _adopt_identity(module: ModuleType, original_name: str) -> str:
    """Give *module*'s declarations a stable name in `sys.modules`.

    A loaded file is not the process's module for its bare stem, so the entry
    under that stem is removed after the body. `pickle`, typing and `inspect`
    still resolve an object through `obj.__module__`, however, so each
    declaration defined in the file is moved onto a unique identity and that
    identity is kept. The module's own `__name__` remains the file's stem: user
    code that reads `__name__` sees what it saw before this identity exists.
    """
    identity = f"{_IDENTITY_PREFIX}{uuid.uuid4().hex}"
    sys.modules[identity] = module
    for value in tuple(vars(module).values()):
        if getattr(value, "__module__", None) != original_name:
            continue
        try:
            value.__module__ = identity
        except (AttributeError, TypeError):
            # An object whose module is fixed, such as a C extension, is still
            # usable; it just keeps the name it was born with.
            pass
    return identity
