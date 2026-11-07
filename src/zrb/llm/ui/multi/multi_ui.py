"""The composite UI: one conversation, shown on several interfaces.

`MultiUI` owns the state and the children; everything it *does* with them lives
in the parts around it:

- `state` — the children, the shared queue, and the conversation behind them.
- `fanout` — every path to a child, best-effort.
- `tools` — a tool call's lifecycle, and the one confirmation for all children.
- `turn` — whether a turn is running, and how it stops.
- `streaming` — one turn, streamed everywhere.
- `input` — the shared queue, the raced prompts, the choice widget.
- `run` — the event loop that drives the main child and unwinds the rest.

The parts inherit from one another in that order, so a part may call the parts
above it without a forward declaration.
"""

from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.any_ui_display import AnyUIDisplay
from zrb.llm.ui.fallback.resolution import (
    register_ui_combiner,
    register_ui_main_getter,
)

from .run import MultiUIRunLoop


class MultiUI(MultiUIRunLoop, AnyUI, AnyUIDisplay):
    """UI wrapper that broadcasts output to multiple UIs and waits for first response.

    Output goes to every child; input takes the first child's answer; all
    children share one message queue; the main UI runs the main event loop.
    Child UIs route `submit_user_message` through this wrapper.

    Usage:
        multi_ui = MultiUI([terminal_ui, telegram_ui])
        # Child UIs should route submit_user_message through multi_ui
        llm_task.set_ui(multi_ui)
    """


def _combine_uis(uis: "list[AnyUI]") -> "AnyUI":
    """Build the combined UI the L0 resolver asks for."""
    return MultiUI(uis)


def _get_main_ui(ui: "AnyUI") -> "AnyUI":
    """*ui*'s primary member when it is a `MultiUI` that has one, else *ui*."""
    if isinstance(ui, MultiUI) and ui.main_ui is not None:
        return ui.main_ui
    return ui


register_ui_combiner(_combine_uis)
register_ui_main_getter(_get_main_ui)
