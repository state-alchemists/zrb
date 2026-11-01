"""MultiUI reaches its children through `AnyUI`'s declared hooks, not by string.

Almost every optional hook a child may implement is declared on `AnyUI` with a
default, so `MultiUI` calls it as `ui.hook(...)` and pyright sees a typo. Three
are left undeclared on purpose -- a UI that has them behaves differently from
one that does not, not merely less (the stream prints its own "Prepare tool
parameters" line without `update_tool_prepare`; the shell tool prints a
command's output live without `update_shell_output`/`finish_shell_output`) --
so declaring a no-op default would change what a UI without them gets. Those
three are dispatched by name, and a typo there silently does nothing on every
child: so the names are pinned here.

`DECLARED_HOOKS` and `OFFERED_HOOKS` together are the canonical list of the
optional hooks a custom UI may implement, documented in
`docs/llm/llm-custom-ui.md`.
"""

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[2]
MULTI_UI = REPO_ROOT / "src" / "zrb" / "llm" / "ui" / "multi_ui.py"
CUSTOM_UI_DOC = REPO_ROOT / "docs" / "llm" / "llm-custom-ui.md"

# Hooks `MultiUI` forwards to children as typed calls; each is declared on
# `AnyUI`. Adding one means adding it to the custom-UI doc in the same diff.
DECLARED_HOOKS = frozenset(
    {
        "accumulate_usage",
        "append_answer",
        "append_markdown",
        "collapse_text_block",
        "collapse_thinking_block",
        "end_tool_call",
        "mark_text_block_start",
        "mark_thinking_block_start",
        "record_tool_call_block",
        "replay_history",
        "reset_context_usage",
        "set_status_badge",
        "set_stream_indentation",
        "settle_text_block",
        "start_tool_call",
        "update_system_info",
    }
)

# Hooks `MultiUI` forwards to the children that offer them, by name.
OFFERED_HOOKS = frozenset(
    {"update_shell_output", "finish_shell_output", "update_tool_prepare"}
)

# Probed on a child but NOT an output-enrichment hook: `start_event_loop` is
# `EventDrivenUI`'s alone and the default TUI deliberately lacks it.
CHILD_CAPABILITY_PROBES = frozenset({"start_event_loop"})


def _calls_named(attr: str) -> list[ast.Call]:
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
    ]


def _offered_names() -> set[str]:
    """Every hook name `MultiUI` looks up on a child by string."""
    names: set[str] = set()
    for node in _calls_named("_fanout_if_offered"):
        first = node.args[0]
        assert isinstance(first, ast.Constant) and isinstance(first.value, str), (
            "_fanout_if_offered's method name must be a string literal so this "
            f"test can see it; got {ast.dump(first)}"
        )
        names.add(first.value)
    return names


def _child_getattr_names() -> set[str]:
    """Literal names probed with `getattr(ui, "name", ...)` on a child."""
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "ui"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value)
    return names


def test_only_the_offered_hooks_are_dispatched_by_string():
    assert _offered_names() == set(OFFERED_HOOKS)
    assert _child_getattr_names() <= set(CHILD_CAPABILITY_PROBES), (
        "MultiUI probes a child by string for "
        f"{sorted(_child_getattr_names() - CHILD_CAPABILITY_PROBES)}. Declare the "
        "hook on AnyUI with a default and call it directly."
    )


def test_every_declared_hook_is_declared_on_any_ui():
    from zrb.llm.any_ui import AnyUI

    missing = sorted(name for name in DECLARED_HOOKS if not hasattr(AnyUI, name))
    assert not missing, f"MultiUI calls {missing}, which AnyUI does not declare."


def test_the_offered_hooks_stay_undeclared():
    """Declaring one would make a UI without it look like it has it: the stream
    would stop printing its own prepare line and the shell tool would stop
    printing a command's output live."""
    from zrb.llm.any_ui import AnyUI

    declared = sorted(name for name in OFFERED_HOOKS if hasattr(AnyUI, name))
    assert not declared


def test_every_hook_exists_on_the_default_ui():
    """The default TUI implements the full optional surface -- it is what the
    hooks were written for, so a typo shows up as a name it lacks."""
    from zrb.llm.ui.default.ui import UI

    missing = sorted(
        name for name in DECLARED_HOOKS | OFFERED_HOOKS if not hasattr(UI, name)
    )
    assert not missing, f"The default UI does not implement {missing}."


def test_every_hook_is_documented():
    doc = CUSTOM_UI_DOC.read_text(encoding="utf-8")
    undocumented = sorted(
        name
        for name in DECLARED_HOOKS | OFFERED_HOOKS
        if f"`{name}(" not in doc and f"`{name}`" not in doc
    )
    assert not undocumented, f"Add {undocumented} to {CUSTOM_UI_DOC.name}."


def _primary_child_probes() -> set[str]:
    """Every name MultiUI looks up by string on its *primary* child.

    `self.main_ui` and `self._uis[0]` are not the optional-hook dispatch above:
    they are state reads off the one child that drives snapshots, rewind, the
    `/plan` badge and the model overrides. Those members are declared in
    `AnyUI`, so they are reached by attribute access and this set is empty.
    """
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id in ("getattr", "hasattr")):
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            continue
        target = ast.unparse(node.args[0])
        if target.startswith("self.main_ui") or target.startswith("self._uis["):
            names.add(node.args[1].value)
    return names


def _fixed_index_child_reads() -> set[str]:
    """Attributes read off a *literally indexed* child, e.g. `self._uis[0].x`.

    `main_ui_index` selects the primary child, so `self._uis[0]` is the primary
    only at the default index. Every other read of primary state goes through
    `self.main_ui`; one that indexes instead silently takes the wrong child's
    session name, approval mode or model.
    """
    tree = ast.parse(MULTI_UI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        value = node.value
        if not isinstance(value, ast.Subscript):
            continue
        if ast.unparse(value.value) != "self._uis":
            continue
        if isinstance(value.slice, ast.Constant):
            names.add(node.attr)
    return names


def test_the_primary_child_is_read_through_the_declared_contract():
    """A `getattr(self.main_ui, "x", default)` says "a UI might not have x".

    Once `x` is in `AnyUI` that is no longer true, and the probe hides the
    opposite failure: a primary child that genuinely lacks it used to fall back
    to the default and disable the feature silently, with nothing for pyright
    to catch. Reaching these members by attribute access is what makes the
    omission a `TypeError` at construction instead.
    """
    probed = _primary_child_probes()
    assert not probed, (
        "MultiUI probes the primary child for "
        f"{sorted(probed)} instead of reading it as declared state. Add the "
        "member to AnyUI (with a default in UIStateDefaultsMixin) and use "
        "attribute access, or -- if it really is optional -- fan it out to "
        "every child through DECLARED_HOOKS rather than the primary alone."
    )


def test_the_primary_child_is_not_reached_by_a_literal_index():
    """`self._uis[0]` is the primary child only when `main_ui_index` is 0.

    It is a constructor argument, so it is not always 0, and a read that
    indexes past `main_ui` takes a different child's state than the one whose
    event loop is driving the session.
    """
    indexed = _fixed_index_child_reads()
    assert not indexed, (
        f"MultiUI reads {sorted(indexed)} off a literally indexed child. Use "
        "`self.main_ui`, which honors main_ui_index, and handle the None case "
        "for a MultiUI with no children."
    )
