"""Ratchet `Any` annotations downward.

Some `Any` values are honest, but others disable pyright; lower the baseline
when replacing one with a real type, never raise it to admit new code.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# Baseline history: -2 queue types, -1 dead `_admits`, -4 daemon-thread hooks,
# -1 steering context (`submit_user_message_via_queue` no longer takes one),
# -10 (1087->1077): the history splitter's message lists are typed
# `list[ModelMessage]` now that the split is planned over real messages rather
# than counted indices, and the archive's role label takes `object` (it only
# asks the message what it is).
# -18 (1077->1059): the RAG tool and its config mixin were removed.
# -1 (1059->1058): `_retry_prompt_to_text(part: Any)` merged into
# `_tool_return_to_text`, which already takes an `Any` part.
# -2 (1058->1056): `_drop_summary_parts` became `_drop_synthetic_parts`, typed
# over `ModelMessage` in and out, and the two synthetic-part predicates take
# `object` (they only ask the part what it is).
# -1 (1056->1055): `_search_with_python` became `_python_matches` and returns
# `list[tuple[str, int, str]]` — the rows it matched — now that the ranking and
# the result dict live in `_format_results`, instead of building `dict[str, Any]`
# itself.
# -1 (1055->1054): the shared `*_float` frame builder is gone — the panels dock
# into the layout, so each builds its own `Frame` from typed state.
# -2 (1054->1052): `subtree_model`'s `to_dict` returns `dict[str, object]` — it
# only passes values through to `json.dumps`.
# -3 (1052->1049): the two echo emitters take an `AnyUI` target and
# `_restore_snapshot` takes a `SnapshotManager`.
# -1 (1049->1048): the ffmpeg camera backend's device cache is typed fields
# rather than a `dict[str, Any]`.
# -4 (1048->1044): `TerminalApprovalChannel` hands an edit to the handler's
# response handlers through `run_response_handlers`, typed over `ToolCallHandler`
# and `ToolCallPart` instead of `Any`.
ANY_ANNOTATIONS = 1044


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
