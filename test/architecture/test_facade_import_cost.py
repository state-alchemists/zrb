"""Two halves of one contract: the facade stays lazy, the CLI stays whole.

`zrb/__init__.py` resolves every export through PEP 562, so `import zrb` loads
no `zrb.*` submodule. That is what keeps a library import off the agent stack:
the eager facade spent ~0.53s of its ~0.56s inside the `zrb.builtin` tree,
because `llm_chat` pulls pydantic and pydantic-ai before anything runs.

The same deferral moves one side effect out of the package body: importing
`zrb.builtin` registers the built-in tasks on `cli`, and `zrb.__main__` is now
what does it. Both halves are pinned here, in a clean interpreter, because each
one fails silently on its own — an eager export costs every caller half a
second nobody attributes to zrb, and a lazy facade without the entry-point
import drops every built-in task from `zrb --help`, with exit code 0 and no
warning ("Invalid subcommand" only when the user tries one).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src"

# What a bare interpreter needs from the parent: PATH to start at all, plus the
# variables Windows requires to load its own runtime. zrb's import chain reaches
# `asyncio`, which imports `_overlapped` there and dies with `WinError 10106`
# without `SYSTEMROOT`. Names absent on this platform are skipped.
_INHERITED = (
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "COMSPEC",
    "PATHEXT",
    "PATH",
    "TEMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
)


def _run_in_clean_interpreter(code: str) -> str:
    """Run *code* in a fresh interpreter that imports this tree, not an install.

    `PYTHONPATH` points at `src/` rather than relying on the editable install,
    so the interpreter under test is always the checkout this file is in.
    """
    env = {"PYTHONPATH": str(SRC), "HOME": str(Path.home())}
    env.update({name: os.environ[name] for name in _INHERITED if name in os.environ})
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, f"the probe failed: {result.stderr[-2000:]}"
    return result.stdout


def _builtin_task_names() -> set[str]:
    """The task names `zrb.builtin` contributes, read in this process.

    Enumerated from `__all__` rather than from `cli.get_all_subtasks()`, so a
    task another test registered on the process-wide tree cannot widen it.
    """
    import zrb.builtin as builtin

    return {getattr(builtin, name).name for name in builtin.__all__}


def test_importing_zrb_loads_no_zrb_submodule():
    loaded = json.loads(
        _run_in_clean_interpreter(
            "import json, sys, zrb; "
            "print(json.dumps(sorted("
            "m for m in sys.modules if m == 'zrb' or m.startswith('zrb.'))))"
        )
    )
    assert loaded == ["zrb"], (
        "`import zrb` now loads zrb submodule(s) "
        f"{[name for name in loaded if name != 'zrb']}. Every caller pays for "
        "them, including one that wanted only `Task` and `make_task`. Keep the "
        "export lazy (a `_LAZY_EXPORTS` entry in `zrb/__init__.py`) or defer "
        "the import to the code that uses it."
    )


def test_the_entry_point_registers_every_builtin_task():
    expected = _builtin_task_names()
    registered = set(
        json.loads(
            _run_in_clean_interpreter(
                "import json; import zrb.__main__; "
                "from zrb.runner.cli import cli; "
                "print(json.dumps(sorted(task.name for task in cli.get_all_subtasks())))"
            )
        )
    )
    assert not expected - registered, (
        "The `zrb` entry point no longer registers every built-in task on "
        f"`cli`; missing: {sorted(expected - registered)}. `import zrb` is lazy "
        "and does not import `zrb.builtin` — `zrb/__main__.py` must, before "
        "`serve_cli` loads any init source."
    )
