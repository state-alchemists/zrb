"""Tests asserting POSIX permission bits must say they are POSIX-only.

`os.chmod` on Windows toggles only the read-only flag, and a directory there
reports 0o777 whatever mode it was created with. A test that *asserts* a mode
therefore checks a guarantee the platform does not offer and fails on Windows
alone -- a slow way to find out, since it needs a full CI run on another OS.

Calling `chmod` for setup is fine and is not flagged: making a stub
executable behaves sensibly everywhere. It is reading the bits back and
asserting them that does not travel.

The marker is any `skipif` naming `os.name`/`sys.platform` on the test or its
class. `test_journal_backlinks.py::needs_fcntl` is the shape to copy.
"""

import ast
from pathlib import Path

TEST_ROOT = Path(__file__).parents[1]

_MODE_READS = frozenset({"S_IMODE", "st_mode"})
_GUARDS = ("skipif", "os.name", "sys.platform", "needs_posix")


def _reads_a_mode(func: ast.AST) -> bool:
    """Whether the body reads permission bits.

    Matched on the AST, not on the unparsed text: `st_mode` is a substring of
    every `test_model_*` name, which made a text search flag eighteen tests
    that have nothing to do with permissions.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Attribute) and node.attr in _MODE_READS:
            return True
        if isinstance(node, ast.Name) and node.id in _MODE_READS:
            return True
    return False


def _guarded(node: ast.AST, module_guards: set[str]) -> bool:
    decorators = getattr(node, "decorator_list", [])
    text = " ".join(ast.unparse(d) for d in decorators)
    return any(g in text for g in _GUARDS) or any(n in text for n in module_guards)


def test_mode_assertions_are_marked_posix_only():
    offenders = []
    for path in TEST_ROOT.rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # Module-level markers, e.g. `needs_posix_modes = pytest.mark.skipif(...)`.
        module_guards = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(g in ast.unparse(node.value) for g in _GUARDS)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not func.name.startswith("test") or not _reads_a_mode(func):
                continue
            if not _guarded(func, module_guards):
                offenders.append(f"{path.relative_to(TEST_ROOT)}::{func.name}")
    assert not offenders, (
        "test(s) assert POSIX permission bits with no platform guard, so they "
        "fail on Windows only: " + ", ".join(sorted(offenders))
    )
