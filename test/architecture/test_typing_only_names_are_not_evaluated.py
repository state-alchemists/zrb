"""A name imported only for the type checker must not be evaluated at import.

`if TYPE_CHECKING:` keeps the type checker happy and the runtime graph small,
but Python evaluates an annotation when the module executes — a class body or a
module-level `def` runs right there — unless `from __future__ import annotations`
turns every annotation into a string. A module that names a typing-only import
in one of those signatures therefore raises `NameError` on the first import,
on 3.13 and older; 3.14 defers annotations by default (PEP 649) and hides it.

Only annotations evaluated while the module executes are checked: a `def`
nested inside another function is annotated when its enclosing function runs,
which is a different moment and often has a local import in scope.
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).parents[2] / "src" / "zrb"


def _is_type_checking(test: ast.expr) -> bool:
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _type_checking_only_names(tree: ast.Module) -> set[str]:
    """Names the module binds solely under `if TYPE_CHECKING:`.

    An `else:` branch binds them at runtime too — `ModelRequest = Any` is the
    common shape — and that name is never missing.
    """
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.If) or not _is_type_checking(node.test):
            continue
        bound_anyway = {
            target.id
            for statement in node.orelse
            for target in _assigned_names(statement)
        }
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in child.names)
            elif isinstance(child, ast.Import):
                names.update(
                    alias.asname or alias.name.split(".")[0] for alias in child.names
                )
        names -= bound_anyway
    return names


def _assigned_names(statement: ast.stmt) -> list[ast.Name]:
    if isinstance(statement, ast.Assign):
        return [n for n in statement.targets if isinstance(n, ast.Name)]
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return [statement.target]
    return []


def _signature_annotations(node: ast.AST) -> list[ast.expr]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    arguments = node.args
    every = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    every += [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
    found = [a.annotation for a in every if a.annotation is not None]
    return found + ([node.returns] if node.returns is not None else [])


def _annotations_evaluated_at_import(tree: ast.Module) -> list[ast.expr]:
    found: list[ast.expr] = []
    for node in tree.body:
        found += _signature_annotations(node)
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                found += _signature_annotations(member)
                if isinstance(member, ast.AnnAssign):
                    found.append(member.annotation)
    return found


def _has_postponed_annotations(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    )


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_a_typing_only_name_is_never_evaluated_when_the_module_loads(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    typing_only = _type_checking_only_names(tree)
    if not typing_only or _has_postponed_annotations(tree):
        return
    offenders = sorted(
        {
            node.id
            for annotation in _annotations_evaluated_at_import(tree)
            for node in ast.walk(annotation)
            if isinstance(node, ast.Name) and node.id in typing_only
        }
    )
    assert not offenders, (
        f"{path.relative_to(SRC.parent.parent.parent)} annotates a signature with "
        f"{offenders}, imported only under `if TYPE_CHECKING:`. Postpone the "
        "annotations with `from __future__ import annotations`, or the import "
        "raises NameError on Python 3.13 and older."
    )
