"""Assembling the UI a chat session runs on.

Three decisions, all of them about presentation: whether the caller's own UIs
run alone, whether the default terminal UI joins them, and whether two or more
UIs are fanned out through one `MultiUI`. They live beside the backends they
choose between, so a session runner asks for a UI instead of assembling one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.ui.any_ui import AnyUI
    from zrb.llm.ui.multi import MultiUI


def assemble_ui(
    *,
    uis: "Sequence[AnyUI]",
    default_kwargs: dict[str, Any],
    include_default_ui: bool,
    approval_channels: "Sequence[AnyApprovalChannel]",
) -> "AnyUI":
    """The caller's UIs, the default terminal UI, or one `MultiUI` over both.

    `default_kwargs` are the keyword arguments the default UI is built with,
    and they are only spent when it is actually built: a session that brings
    its own UIs never imports the terminal backend.

    Args:
        uis: the UIs already attached, in the order they run.
        default_kwargs: keyword arguments for the default terminal UI.
        include_default_ui: whether the default UI joins *uis*.
        approval_channels: channels an approval request is routed through,
            the first one that answers winning.
    """
    if uis and not include_default_ui:
        if len(uis) == 1:
            return uis[0]
        return _multi_ui(uis, approval_channels)

    # lazy: the default UI loads prompt_toolkit, pdfplumber and vosk.
    from zrb.llm.ui.default.app.lexer import CLIStyleLexer
    from zrb.llm.ui.default.ui import UI

    default_ui = UI(**{**default_kwargs, "output_lexer": CLIStyleLexer()})
    if not uis:
        return default_ui
    ui = _multi_ui([default_ui, *uis], approval_channels)
    ui.set_tool_call_handler(default_ui.tool_call_handler)
    return ui


def _multi_ui(
    uis: "Sequence[AnyUI]",
    approval_channels: "Sequence[AnyApprovalChannel]",
) -> "MultiUI":
    """Combine *uis* into one `MultiUI`, wired to the first approval channel."""
    # lazy: `multi` loads prompt_toolkit and `approval` loads pydantic_ai.
    from zrb.llm.approval import resolve_approval_channel
    from zrb.llm.ui.multi import MultiUI

    ui = MultiUI(list(uis))
    approval_channel = resolve_approval_channel(list(approval_channels))
    if approval_channel is not None:
        ui.set_approval_channel(approval_channel)
    return ui
