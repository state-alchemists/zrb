"""The collapse mechanics key off the `append_to_output` `kind` of a chunk.

`mark_thinking_block_start`/`mark_text_block_start` register the kind whose
chunks belong to the block, and `merge_into_block` absorbs only those — that
is what keeps a concurrent writer's line (default kind `"text"`) outside the
block. If `StreamEventHandler` ever prints block content under a different
kind, the block would absorb nothing and the collapse would silently no-op,
leaving the raw stream on screen. Nothing else would fail, so it is pinned
here.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

# kind printed by StreamEventHandler -> the streamer method that prints it
BLOCK_KINDS = {
    "thinking": "_stream_thinking_content",
    "streaming": "_stream_text_content",
}


def _print_kinds_in(method_name: str) -> set[str]:
    """The literal kinds `method_name` passes to its print callback."""
    tree = ast.parse((SRC / "llm" / "util" / "stream_response.py").read_text("utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == method_name):
            continue
        return {
            arg.value
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            for arg in call.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
    raise AssertionError(f"{method_name} not found in stream_response.py")


def test_streamer_prints_each_block_under_the_kind_the_ui_registers():
    for kind, method in BLOCK_KINDS.items():
        assert kind in _print_kinds_in(method), (
            f"{method} no longer prints with kind={kind!r}. The UI's "
            f"mark_*_block_start registers that kind, so the collapse would "
            f"silently stop working. Update both sides together."
        )


def test_both_uis_register_exactly_those_kinds():
    """`UIOutput` and `BufferedUI` must agree with the streamer and with
    each other — MultiUI fans the same chunks to both."""
    for rel in ("llm/ui/default/output.py", "llm/ui/buffered_ui.py"):
        source = (SRC / rel).read_text("utf-8")
        tree = ast.parse(source)
        registered = {
            arg.value
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name in ("mark_thinking_block_start", "mark_text_block_start")
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            for arg in call.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
        assert registered == set(BLOCK_KINDS), (
            f"{rel} registers {sorted(registered)} for its collapsible "
            f"blocks; the streamer prints {sorted(BLOCK_KINDS)}."
        )
