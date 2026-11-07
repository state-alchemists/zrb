"""Inert tools role: a UI that shows no tool call and confirms none itself.

`tool_call_handler` is None, so a caller falls back to an approval channel, and
`yolo` is False, so nothing is ever auto-approved on a UI that did not say so.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui_tools import AnyUITools


class UIToolsDefaults:
    """The tools role for a UI with no tool-call surface of its own."""

    @property
    def tools(self) -> "AnyUITools":
        """A UI that shows and confirms a tool call is its own tool surface."""
        return cast("AnyUITools", self)

    @property
    def tool_call_handler(self) -> Any:
        """No handler of its own; callers fall back to an approval channel."""
        return None

    @property
    def yolo(self) -> bool | frozenset:
        """Never auto-approve."""
        return False

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """No status bar to time a tool call in."""

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """No status bar to stop a timer in."""

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """No confirmations of its own to release."""
