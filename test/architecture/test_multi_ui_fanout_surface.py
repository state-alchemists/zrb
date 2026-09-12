"""`_fanout` on MultiUI dispatches by string, which no type checker sees.

A child UI is not required to implement these -- `_fanout` skips any child
that doesn't, deliberately, so a Telegram channel can ignore the TUI's
block-collapsing hooks. That optional-capability shape is fine. What it cannot
survive is a *typo*: `_fanout("accumulat_usage")` silently does nothing on
every child, forever, and nothing fails.

So the names are pinned here instead. `FANOUT_METHODS` is also the canonical
list of the optional enrichment hooks a custom UI may implement, documented in
`docs/llm/llm-custom-ui.md`.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
MULTI_UI = REPO_ROOT / "src" / "zrb" / "llm" / "ui" / "multi_ui.py"

# Every method MultiUI fans out to children by name. Adding one here means
# adding it to the custom-UI doc's optional-hooks list in the same diff.
FANOUT_METHODS = frozenset(
    {
        "accumulate_usage",
        "collapse_text_block",
        "collapse_thinking_block",
        "finish_shell_output",
        "mark_text_block_start",
        "mark_thinking_block_start",
        "replay_history",
        "update_shell_output",
        "update_tool_prepare",
    }
)


def _fanout_call_names() -> set[str]:
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "_fanout"):
            continue
        assert node.args, "_fanout called with no method name"
        first = node.args[0]
        assert isinstance(first, ast.Constant) and isinstance(first.value, str), (
            "_fanout's method name must be a string literal so this test can "
            f"see it; got {ast.dump(first)}"
        )
        names.add(first.value)
    return names


def test_every_fanout_name_is_recorded():
    called = _fanout_call_names()
    assert called == set(FANOUT_METHODS), (
        "_fanout call sites on MultiUI drifted from the recorded list. A name "
        "here that is not a real method silently does nothing on every child: "
        f"added={sorted(called - FANOUT_METHODS)} "
        f"removed={sorted(FANOUT_METHODS - called)}"
    )


def test_every_fanout_name_exists_on_the_default_ui():
    """The default TUI implements the full optional surface -- it is what the
    hooks were written for, so a typo shows up as a name it lacks."""
    from zrb.llm.ui.default.ui import UI

    missing = sorted(name for name in FANOUT_METHODS if not hasattr(UI, name))
    assert not missing, (
        f"MultiUI fans out to {missing}, which the default UI does not "
        "implement -- either a typo, or a hook that no longer exists."
    )
