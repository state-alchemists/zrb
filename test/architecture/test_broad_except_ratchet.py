"""Ratchet swallowed broad exceptions downward.

Some broad handlers are justified for UI continuity or cleanup; lower the
baseline when narrowing one, and never raise it to admit new code.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

_BROAD = {"Exception", "BaseException"}

SWALLOWED_BROAD_EXCEPTS = 313


def _is_broad(handler: ast.ExceptHandler) -> bool:
    caught = handler.type
    if caught is None:
        return True
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    return any(isinstance(name, ast.Name) and name.id in _BROAD for name in names)


def _is_reraised(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ExceptHandler)
                and _is_broad(node)
                and not _is_reraised(node)
            ):
                found.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return found


def test_swallowed_broad_excepts_do_not_grow():
    offenders = _offenders()
    assert len(offenders) <= SWALLOWED_BROAD_EXCEPTS, (
        f"{len(offenders)} broad `except` handlers swallow the error, up from "
        f"{SWALLOWED_BROAD_EXCEPTS}. Catch what the code can recover from, or "
        "re-raise."
    )


def test_the_ratchet_is_tight():
    offenders = _offenders()
    assert len(offenders) == SWALLOWED_BROAD_EXCEPTS, (
        f"{SWALLOWED_BROAD_EXCEPTS - len(offenders)} broad handler(s) were "
        f"narrowed without lowering the ratchet. Set SWALLOWED_BROAD_EXCEPTS "
        f"to {len(offenders)}."
    )
