import os
import pickle
import sys
import tempfile
import types
import typing
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from zrb.task.cmd_task import CmdTask
from zrb.util.load import (
    get_user_frames,
    load_file,
    load_file_with_result,
    load_module,
    load_module_from_path,
    load_module_with_result,
)


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


def test_load_file_leaves_the_name_its_stem_would_take_free():
    """A loaded file is not the process's module for its bare name.

    A `zrb_init.py`, or a hook file called `openai.py`, answered every later
    `import openai` because the loader registered the file under its stem and
    never put the name back.
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("value = 1")
        path = f.name
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        assert load_file(path) is not None
        assert stem not in sys.modules
    finally:
        os.remove(path)


def test_load_file_restores_the_module_its_stem_would_have_shadowed():
    """The name it borrowed is handed back, not replaced."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("value = 1")
        path = f.name
    stem = os.path.splitext(os.path.basename(path))[0]
    existing = types.ModuleType(stem)
    sys.modules[stem] = existing
    try:
        assert load_file(path) is not None
        assert sys.modules[stem] is existing
    finally:
        sys.modules.pop(stem, None)
        os.remove(path)


def test_load_file_with_result_leaves_the_name_its_stem_would_take_free():
    """The `zrb_init.py` path execs the file itself, and leaks the same entry."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("value = 1")
        path = f.name
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        module, error = load_file_with_result(path)
        assert module is not None
        assert error is None
        assert stem not in sys.modules
    finally:
        os.remove(path)


def test_load_file_lets_the_file_import_itself_during_its_own_body():
    """The name is held while the body runs — that is what a self-import needs,
    and only the entry left behind once the body ends is the defect."""
    with tempfile.NamedTemporaryFile(
        prefix="zrb_load_self_import_", suffix=".py", mode="w", delete=False
    ) as f:
        stem = os.path.splitext(os.path.basename(f.name))[0]
        f.write(f"import {stem}\nvalue = {stem}\n")
        path = f.name
    try:
        module = load_file(path)
        assert module is not None
        assert module.value is module
    finally:
        os.remove(path)


def test_load_file_pickles_without_running_the_body_again():
    """The declarations need a module name, but the file's stem must not keep one.

    `pickle` re-imports the name it reads from `obj.__module__`; when that was
    the stem, the file ran a second time and produced a different class. The
    private identity keeps both promises: the body runs once, and pickle finds
    the object it was given.
    """
    with tempfile.TemporaryDirectory() as directory:
        marker = os.path.join(directory, "runs")
        path = os.path.join(directory, "pickle_mod.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"with open({marker!r}, 'a', encoding='utf-8') as runs:\n"
                f"    runs.write('run\\n')\n"
                f"class Thing:\n"
                f"    pass\n"
                f"def make():\n"
                f"    return Thing()\n"
            )
        module = load_file(path, raise_on_error=True)
        assert module is not None
        assert module.__name__ == "pickle_mod"
        assert sys.modules[module.Thing.__module__] is module
        with open(marker, encoding="utf-8") as f:
            assert f.read().count("run") == 1

        assert pickle.loads(pickle.dumps(module.Thing)) is module.Thing
        assert pickle.loads(pickle.dumps(module.make)) is module.make
        assert isinstance(pickle.loads(pickle.dumps(module.Thing())), module.Thing)
        with open(marker, encoding="utf-8") as f:
            assert f.read().count("run") == 1


def test_load_file_resolves_its_own_type_hints():
    """Typing reads a class's annotations through `sys.modules[__module__]`."""
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "hinted_mod.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "from __future__ import annotations\n"
                "class Child:\n"
                '    parent: "Child | None" = None\n'
            )
        module = load_file(path, raise_on_error=True)
        assert module is not None
        assert typing.get_type_hints(module.Child)["parent"] == module.Child | None


def test_load_module_from_path_keeps_its_unique_name():
    """The hook/skill/agent loaders supply a UUID name that cannot shadow."""
    name = f"zrb_hook_{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "hook_mod.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("class Thing:\n    pass\n")
        module = load_module_from_path(name, path)
        try:
            assert module is not None
            assert sys.modules[name] is module
            assert pickle.loads(pickle.dumps(module.Thing)) is module.Thing
        finally:
            sys.modules.pop(name, None)


def test_load_file_restores_a_none_blocker_in_sys_modules():
    """`sys.modules[name] = None` is a deliberate import blocker, not absence."""
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "blocked_mod.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("value = 1")
        sys.modules["blocked_mod"] = None
        try:
            assert load_file(path, raise_on_error=True) is not None
            assert "blocked_mod" in sys.modules
            assert sys.modules["blocked_mod"] is None
        finally:
            sys.modules.pop("blocked_mod", None)


def test_same_stem_loads_are_serialized():
    """Two files named the same must not take each other's self-import."""
    with (
        tempfile.TemporaryDirectory() as first,
        tempfile.TemporaryDirectory() as second,
    ):
        paths = [
            os.path.join(first, "same_mod.py"),
            os.path.join(second, "same_mod.py"),
        ]
        for path in paths:
            with open(path, "w", encoding="utf-8") as f:
                f.write("import same_mod\nvalue = same_mod\n")

        with ThreadPoolExecutor(max_workers=2) as pool:
            modules = list(pool.map(lambda path: load_file(path, True), paths))

    assert modules[0] is not None and modules[1] is not None
    assert modules[0].value is modules[0]
    assert modules[1].value is modules[1]
    assert modules[0] is not modules[1]
    assert modules[0].value.__name__ == "same_mod"
    assert modules[1].value.__name__ == "same_mod"
    assert "same_mod" not in sys.modules


def test_load_file_not_found():
    assert load_file("/non/existent/path.py") is None


def test_load_module_success():
    module = load_module("os")
    assert module is os


def test_load_module_fail():
    with pytest.raises(ImportError):
        load_module("non_existent_module_xyz")


def test_load_file_broken_script_returns_none():
    """A file that raises on exec is reported and yields None, not an exception."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("raise RuntimeError('boom')")
        path = f.name
    try:
        assert load_file(path) is None
    finally:
        os.remove(path)


def test_load_file_broken_script_raises_when_raise_on_error():
    """The fatal-load call site (zrb_init.py) opts into the real exception."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("raise RuntimeError('boom')")
        path = f.name
    try:
        with pytest.raises(RuntimeError, match="boom"):
            load_file(path, raise_on_error=True)
    finally:
        os.remove(path)


def test_load_file_with_result_returns_declarations_with_the_error():
    """A source that fails after declaring a name still yields that name with
    the error: the declaration is already live in the CLI tree."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("value = 'declared'\nraise RuntimeError('boom')")
        path = f.name
    try:
        module, error = load_file_with_result(path)
        assert isinstance(error, RuntimeError)
        assert module is not None
        assert module.value == "declared"
    finally:
        os.remove(path)


def test_load_file_with_result_success_has_no_error():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def hello(): return 'world'")
        path = f.name
    try:
        module, error = load_file_with_result(path)
        assert error is None
        assert module is not None
        assert module.hello() == "world"
    finally:
        os.remove(path)


def test_load_file_with_result_missing_file_has_no_error():
    module, error = load_file_with_result("/non/existent/path.py")
    assert module is None
    assert error is None


def test_load_module_with_result_returns_the_import_error():
    module, error = load_module_with_result("non_existent_module_xyz")
    assert isinstance(error, ImportError)
    assert module is None


def test_load_module_with_result_success_has_no_error():
    module, error = load_module_with_result("os")
    assert module is os
    assert error is None


def test_load_module_from_path_success(temp_script):
    module = load_module_from_path("my_loaded_mod", temp_script)
    assert module is not None
    assert module.hello() == "world"


def test_load_module_from_path_not_found():
    assert load_module_from_path("nope", "/non/existent/path.py") is None


def test_load_module_from_path_broken_script_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("1 / 0")
        path = f.name
    try:
        assert load_module_from_path("broken_mod", path) is None
    finally:
        os.remove(path)


def test_get_user_frames_points_at_the_user_line_not_the_zrb_one():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(
            "from zrb.task.cmd_task import CmdTask\n\nCmdTask(name='x', cmmd='a')\n"
        )
        path = f.name
    try:
        _, error = load_file_with_result(path)
        assert isinstance(error, TypeError)
        user_frame, raising_frame = get_user_frames(error)
        assert (user_frame.filename, user_frame.lineno) == (path, 3)
        assert raising_frame.filename == sys.modules[CmdTask.__module__].__file__
    finally:
        os.remove(path)


def test_get_user_frames_falls_back_to_the_raising_frame():
    try:
        raise ValueError("x")
    except ValueError as error:
        user_frame, raising_frame = get_user_frames(error)
    assert user_frame is raising_frame


def test_get_user_frames_skips_stdlib_frames():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("import json\n\njson.loads('{')\n")
        path = f.name
    try:
        _, error = load_file_with_result(path)
        user_frame, _ = get_user_frames(error)
        assert (user_frame.filename, user_frame.lineno) == (path, 3)
    finally:
        os.remove(path)
