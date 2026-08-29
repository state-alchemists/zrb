"""Guards the one mechanical half of builtin/__init__.py's registration contract.

A new builtin task must be BOTH imported here AND added to `__all__`, or it
silently never appears in the CLI (see AGENTS.md's "Gotchas" note). This test
only catches the half that's checkable without guessing at intent elsewhere in
the tree: an import and `__all__` that have drifted apart within this one file
(imported but not exported, or exported but not actually imported). It cannot
catch "forgot to import a new module at all" — some `builtin/` functions are
intentionally internal (e.g. an `upstream=` dependency of another task), so a
scan of the whole tree would false-positive on those; the AGENTS.md comment is
the guard for that half.
"""

import ast
from pathlib import Path

INIT_PATH = Path(__file__).parents[2] / "src" / "zrb" / "builtin" / "__init__.py"


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
