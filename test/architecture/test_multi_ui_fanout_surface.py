"""MultiUI dispatches optional child hooks by string, which no type checker sees.

A child UI is not required to implement these -- the dispatch skips any child
that doesn't, deliberately, so a Telegram channel can ignore the TUI's
block-collapsing hooks. That optional-capability shape is fine. What it cannot
survive is a *typo*: `_fanout("accumulat_usage")` silently does nothing on
every child, forever, and nothing fails.

Two dispatch shapes carry these names and both are checked: `_fanout("name")`,
and the ad-hoc `getattr(ui, "name", None)` used by the hooks that need a
fallback for children lacking them (`append_markdown` renders for the child,
`record_tool_call_block` degrades to a plain line).

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
        "append_markdown",
        "collapse_text_block",
        "collapse_thinking_block",
        "finish_shell_output",
        "mark_text_block_start",
        "mark_thinking_block_start",
        "record_tool_call_block",
        "replay_history",
        "update_shell_output",
        "update_system_info",
        "update_tool_prepare",
    }
)

# Probed on a child but NOT an output-enrichment hook, so not in the doc's
# optional-hooks table: `start_event_loop` is `EventDrivenUI`'s alone and the
# default TUI deliberately lacks it.
CHILD_CAPABILITY_PROBES = frozenset({"start_event_loop"})


def _dispatched_names() -> set[str]:
    """Every hook name MultiUI looks up on a child by string, via either shape."""
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "_fanout":
            assert node.args, "_fanout called with no method name"
            first = node.args[0]
            assert isinstance(first, ast.Constant) and isinstance(first.value, str), (
                "_fanout's method name must be a string literal so this test "
                f"can see it; got {ast.dump(first)}"
            )
            names.add(first.value)
            continue
        # `getattr(ui, "name", None)` — `ui` is the loop variable over
        # `self._uis`; probes against `self.main_ui`, `sys` etc. are not
        # child-hook dispatch and are skipped.
        if (
            isinstance(func, ast.Name)
            and func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "ui"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            name = node.args[1].value
            if name not in CHILD_CAPABILITY_PROBES:
                names.add(name)
    return names


def test_every_fanout_name_is_recorded():
    called = _dispatched_names()
    assert called == set(FANOUT_METHODS), (
        "Child-hook dispatch on MultiUI drifted from the recorded list. A name "
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
