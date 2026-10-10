"""Guard circular imports with an allowlist and isolated module imports.

The allowlist records each `# lazy: circular` count; isolated imports expose
cycles hidden by package initialization; the package allowlist keeps two
packages from importing each other at runtime.
"""

import ast
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Relative path -> expected `# lazy: circular` count; additions need reasons.
CIRCULAR_IMPORT_ALLOWLIST: dict[str, int] = {
    # Pipecat and its re-exporting backend package form a genuine cycle; defer the
    # backend half where the pipeline is built.
    "llm/speech/backend/pipecat.py": 1,
}


def _circular_import_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in SRC.rglob("*.py"):
        n = len(re.findall(r"# lazy: circular", path.read_text(encoding="utf-8")))
        if n:
            counts[path.relative_to(SRC).as_posix()] = n
    return counts


def test_circular_import_workarounds_match_the_allowlist():
    actual = _circular_import_counts()
    assert actual == CIRCULAR_IMPORT_ALLOWLIST, (
        "`# lazy: circular` workarounds drifted from the allowlist — a file "
        "missing here, an extra file, or a changed count means a cycle was "
        "added, fixed, or moved. Update CIRCULAR_IMPORT_ALLOWLIST in this "
        f"file to match, in the same diff, with a reason.\nactual={actual}\n"
        f"expected={CIRCULAR_IMPORT_ALLOWLIST}"
    )


# Package pairs allowed to import each other at runtime (imports under
# `TYPE_CHECKING` or inside a function excluded); additions need reasons.
PACKAGE_CYCLE_ALLOWLIST: set[frozenset[str]] = {
    # `util/load.py` reports a failed user-code load through `zrb_print`, which
    # routes to the running task's context; that context state is owned by
    # `zrb.context`, not by a helper package.
    frozenset({"zrb.context", "zrb.util"}),
}


def _package_of(module: str) -> str:
    parts = module.split(".")
    depth = 3 if len(parts) > 2 and parts[1] == "llm" else 2
    return ".".join(parts[:depth])


def _runtime_imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    pending: list[ast.stmt] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
            pending.extend(node.orelse)
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
        for field in ("body", "orelse", "finalbody", "handlers"):
            pending.extend(getattr(node, field, None) or [])
    return [module for module in found if module.startswith("zrb.")]


def _package_cycles() -> set[frozenset[str]]:
    edges: set[tuple[str, str]] = set()
    for path in SRC.rglob("*.py"):
        module = ".".join(("zrb", *path.relative_to(SRC).with_suffix("").parts))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for target in _runtime_imports(tree):
            edges.add((_package_of(module), _package_of(target)))
    return {frozenset({a, b}) for a, b in edges if a != b and (b, a) in edges}


def test_packages_do_not_import_each_other():
    actual = _package_cycles()
    assert actual == PACKAGE_CYCLE_ALLOWLIST, (
        "Two packages import each other at runtime. Move the shared piece to "
        "the lower package, or under `TYPE_CHECKING` when it is only an "
        "annotation; a fixed cycle is removed from PACKAGE_CYCLE_ALLOWLIST in "
        f"the same diff.\nactual={sorted(map(sorted, actual))}"
    )


# Isolated imports catch cycles hidden by parent-package preloading.


_ISOLATED_IMPORT = textwrap.dedent("""
    import importlib
    import pathlib
    import sys
    import types

    root = pathlib.Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))
    target = sys.argv[1]
    parts = target.split(".")
    # Stub every parent package so its __init__ can't pre-warm sys.modules,
    # keeping __path__ intact so submodule resolution still works.
    for i in range(1, len(parts)):
        name = ".".join(parts[:i])
        module = types.ModuleType(name)
        module.__path__ = [str(root.joinpath(*parts[:i]))]
        sys.modules[name] = module
    importlib.import_module(target)
    """)


def _all_modules() -> list[str]:
    """Return importable package and module targets under `zrb`."""
    targets = set()
    for path in SRC.rglob("*.py"):
        relative = path.parent if path.name == "__init__.py" else path.with_suffix("")
        parts = relative.relative_to(SRC).parts
        if all(part.isidentifier() for part in parts):
            targets.add(".".join(("zrb", *parts)))
    targets.discard("zrb")
    return sorted(targets)


@pytest.mark.parametrize("module", _all_modules())
def test_every_module_imports_with_its_parents_stubbed(module: str):
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATED_IMPORT, module, str(REPO_ROOT / "src")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`{module}` cannot be imported on its own — its import closure "
        "contains a cycle that is currently masked by whatever else loads "
        "first. Fix it at the source: trim the package __init__ re-export "
        "that drags a heavy sibling in, move a dependency-free leaf module out "
        "of the package it doesn't belong to, or — only when both directions "
        "are genuine — defer one import with a `# lazy: circular` tag and add "
        f"it to CIRCULAR_IMPORT_ALLOWLIST above.\n{result.stderr[-1500:]}"
    )
