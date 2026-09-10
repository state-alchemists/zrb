"""Guards both halves of builtin/__init__.py's registration contract.

A new builtin task must be BOTH imported here AND added to `__all__`, or it
silently never appears in the CLI (see AGENTS.md's "Gotchas" note).

- *Within the file* — an import and `__all__` that have drifted apart
  (imported but not exported, or exported but not actually imported).
- *Across the tree* — a task module on disk that `__init__.py` never imports
  at all, which the within-file check cannot see.

A builtin task can be intentionally internal — an `upstream=` dependency of
another task, never a CLI entry point of its own — which the tree scan cannot
tell from an oversight. `INTERNAL_TASKS` names those with their reason, so the
distinction is recorded rather than guessed. It is empty: every task under
`builtin/` is a CLI entry point.
"""

import ast
import importlib
import pkgutil
from pathlib import Path

import zrb.builtin
from zrb.task.any_task import AnyTask

INIT_PATH = Path(__file__).parents[2] / "src" / "zrb" / "builtin" / "__init__.py"

# "<module>:<name>" -> why this task is deliberately not a CLI entry point.
# Add an entry only for a task that exists purely as another task's
# dependency; anything else missing from `__all__` is the silent-failure bug.
INTERNAL_TASKS: dict[str, str] = {}


def _imported_names() -> set[str]:
    tree = ast.parse(INIT_PATH.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _all_names() -> set[str]:
    tree = ast.parse(INIT_PATH.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(
            node.value, (ast.List, ast.Tuple)
        ):
            continue
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            return {
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    raise AssertionError("builtin/__init__.py has no `__all__` list")


def test_every_imported_name_is_exported():
    imported, exported = _imported_names(), _all_names()
    missing = imported - exported
    assert (
        not missing
    ), f"Imported in builtin/__init__.py but missing from __all__: {sorted(missing)}"


def test_every_exported_name_is_imported():
    imported, exported = _imported_names(), _all_names()
    stale = exported - imported
    assert (
        not stale
    ), f"Listed in builtin/__init__.py's __all__ but not actually imported: {sorted(stale)}"


def test_every_task_module_on_disk_is_wired_into_the_cli():
    """The half the two checks above are blind to: a task nobody imported.

    The checks above compare `__init__.py` against itself, so a module never
    referenced there passes both while its tasks never reach the CLI.
    `pkgutil.walk_packages` walks the package path instead, which is what
    makes an unimported module visible.
    """
    exported = _all_names()
    unwired = {}
    for module_info in pkgutil.walk_packages(
        zrb.builtin.__path__, f"{zrb.builtin.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        missing = [
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and isinstance(value, AnyTask)
            and name not in exported
            and f"{module_info.name}:{name}" not in INTERNAL_TASKS
        ]
        if missing:
            unwired[module_info.name] = sorted(missing)
    assert not unwired, (
        "Task(s) under `builtin/` never reach the CLI: they are missing from "
        "`builtin/__init__.py`'s imports and `__all__`. Wire them up, or — if "
        "one exists only as another task's dependency — record it in "
        f"INTERNAL_TASKS with the reason: {unwired}"
    )
