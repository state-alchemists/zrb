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
from unittest.mock import MagicMock

from pydantic_ai.messages import TextPart, ThinkingPart

from zrb.llm.util.stream_response import StreamEventHandler

REPO_ROOT = pathlib.Path(__file__).parents[2]
SRC = REPO_ROOT / "src" / "zrb"

BLOCK_KINDS = {"thinking", "streaming"}


def test_streamer_prints_each_block_under_the_kind_the_ui_registers():
    print_fn = MagicMock()
    handler = StreamEventHandler(print_fn=print_fn)
    for part in (ThinkingPart(content="hmm"), TextPart(content="hello")):
        event = MagicMock()
        event.part = part
        handler.handle_part_start(event)
    printed_kinds = {call.args[1] for call in print_fn.call_args_list}
    assert printed_kinds == BLOCK_KINDS, (
        f"StreamEventHandler prints its blocks under {sorted(printed_kinds)}. "
        f"The UI's mark_*_block_start registers {sorted(BLOCK_KINDS)}, so the "
        f"collapse would silently stop working. Update both sides together."
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
        assert registered == BLOCK_KINDS, (
            f"{rel} registers {sorted(registered)} for its collapsible "
            f"blocks; the streamer prints {sorted(BLOCK_KINDS)}."
        )
