"""`Any` in annotations, as a number that only goes down.

An `Any` switches pyright off for everything that flows through it, so a
wrong attribute or a wrong argument type there is found by a user, not by
`./zrb-test.sh`. Some are honest (a value from `json.loads`, a user callback
whose return zrb never reads); many stand in for a type nobody wrote down.

This counts `Any` used in a parameter, return or variable annotation, the
shape of `test_bool_naming_ratchet.py`. Lower `ANY_ANNOTATIONS` in the same
diff that replaces one with a real type (a protocol, a `TypeVar`, `object`
for a value only passed along); never raise it to make new code pass.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# -2: message-queue provenance forwarding now uses object/Awaitable types.
# -1: the slop sweep dropped `_admits` in live_context, whose `model: "Any"`
# was never read (it always returned True).
ANY_ANNOTATIONS = 1093


def _count_any(annotation: ast.expr | None) -> int:
    if annotation is None:
        return 0
    return sum(
        1
        for node in ast.walk(annotation)
        if (isinstance(node, ast.Name) and node.id == "Any")
        or (isinstance(node, ast.Attribute) and node.attr == "Any")
        or (isinstance(node, ast.Constant) and node.value == "Any")
    )


def _annotations(tree: ast.AST) -> list[ast.expr | None]:
    found: list[ast.expr | None] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = args.posonlyargs + args.args + args.kwonlyargs
            every += [arg for arg in (args.vararg, args.kwarg) if arg is not None]
            found += [arg.annotation for arg in every]
            found.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            found.append(node.annotation)
    return found


def _count() -> int:
    return sum(
        _count_any(annotation)
        for path in sorted(SRC.rglob("*.py"))
        for annotation in _annotations(ast.parse(path.read_text(encoding="utf-8")))
    )


def test_any_annotations_do_not_grow():
    count = _count()
    assert count <= ANY_ANNOTATIONS, (
        f"{count} `Any` annotations, up from {ANY_ANNOTATIONS}. Name the real "
        "type: a protocol, a TypeVar, or `object` for a value only passed along."
    )


def test_the_ratchet_is_tight():
    count = _count()
    assert count == ANY_ANNOTATIONS, (
        f"{ANY_ANNOTATIONS - count} `Any` annotation(s) were replaced without "
        f"lowering the ratchet. Set ANY_ANNOTATIONS to {count}."
    )
