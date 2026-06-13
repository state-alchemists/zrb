"""History-replay rendering for `BaseUI`.

Renders a loaded conversation history through the same visual paths a live
turn uses, so a resumed session looks like a fresh one. Split out of `ui.py`
to keep that file focused; the methods still run on the composed `BaseUI`
instance (see the host-class contract below), mirroring `CommandsMixin`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.util.history_formatter import format_args, format_timestamp, truncate
from zrb.util.cli.markdown import render_markdown

if TYPE_CHECKING:
    from typing import Any

    from rich.theme import Theme


class HistoryReplayMixin:
    """Replay loaded `ModelMessage`s through the live-render paths."""

    # Host-class contract: state and methods owned by `BaseUI`. Declared here
    # so type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _markdown_theme: "Theme | None"

        def append_to_output(self, *values: Any, **kwargs: Any) -> None: ...

        def _get_output_field_width(self) -> int | None: ...

    def replay_history(self, messages: list) -> None:
        """Public entry point for replaying loaded conversation history."""
        return self._replay_history(messages)

    def _replay_history(self, messages: list) -> None:
        """Render loaded conversation history through live-message paths.

        Replays each ModelMessage so loaded sessions visually match a fresh
        conversation: user lines and assistant headers render normally,
        assistant text goes through markdown rendering, and tool calls/returns
        use the same faint style as while streaming.
        """
        if not messages:
            return
        pending_tool_calls: dict[str, str] = {}
        for msg in messages:
            kind = getattr(msg, "kind", None)
            timestamp = format_timestamp(getattr(msg, "timestamp", None))
            ts_display = f"{timestamp} " if timestamp else ""
            parts = getattr(msg, "parts", []) or []
            if kind == "request":
                self._replay_request_parts(parts, ts_display, pending_tool_calls)
            elif kind == "response":
                self.append_to_output(f"\n🤖 {ts_display}>>\n")
                self._replay_response_parts(parts, pending_tool_calls)

    def _replay_request_parts(
        self,
        parts: list,
        ts_display: str,
        pending_tool_calls: dict[str, str],
    ) -> None:
        """Render parts of a replayed ModelRequest (user/tool-return/retry)."""
        for part in parts:
            pkind = getattr(part, "part_kind", None)
            if pkind == "tool-return":
                self._replay_tool_return(part, pending_tool_calls)
            elif pkind == "user-prompt":
                content = str(getattr(part, "content", "") or "")
                self.append_to_output(f"\n💬 {ts_display}>> {content.strip()}\n")
            elif pkind == "retry-prompt":
                content = str(getattr(part, "content", "") or "")
                self.append_to_output(
                    f"\n  🔄 Retry: {truncate(content, 200)}\n",
                    kind="tool_call",
                )
            # system-prompt parts are skipped during replay

    def _replay_response_parts(
        self,
        parts: list,
        pending_tool_calls: dict[str, str],
    ) -> None:
        """Render parts of a replayed ModelResponse (thinking/text/tool-call)."""
        width = self._get_output_field_width()
        for part in parts:
            pkind = getattr(part, "part_kind", None)
            if pkind == "thinking":
                content = str(getattr(part, "content", "") or "")
                if content.strip():
                    self.append_to_output(
                        f"  💭 {truncate(content, 500)}", kind="thinking"
                    )
            elif pkind == "text":
                content = str(getattr(part, "content", "") or "")
                if content.strip():
                    self.append_to_output("\n")
                    self.append_to_output(
                        render_markdown(
                            content, width=width, theme=self._markdown_theme
                        )
                    )
            elif pkind == "tool-call":
                self._replay_tool_call(part, pending_tool_calls)

    def _replay_tool_call(self, part, pending_tool_calls: dict[str, str]) -> None:
        """Render a single replayed tool call."""
        tool_name = getattr(part, "tool_name", None) or "unknown"
        tool_call_id = getattr(part, "tool_call_id", None) or "?"
        args_str = format_args(getattr(part, "args", None))
        if tool_call_id and tool_name:
            pending_tool_calls[tool_call_id] = tool_name
        self.append_to_output(
            f"  🧰 {tool_call_id} | {tool_name} {args_str}", kind="tool_call"
        )

    def _replay_tool_return(self, part, pending_tool_calls: dict[str, str]) -> None:
        """Render a single replayed tool return."""
        tool_call_id = getattr(part, "tool_call_id", None) or "?"
        tool_name = (
            getattr(part, "tool_name", None)
            or pending_tool_calls.get(tool_call_id)
            or "unknown"
        )
        outcome = getattr(part, "outcome", "success")
        status_icon = "✅" if str(outcome) == "success" else "❌"
        content = str(getattr(part, "content", "") or "")
        self.append_to_output(
            f"\n  🔠 {tool_call_id} | {tool_name} {status_icon}",
            kind="tool_call",
        )
        body = truncate(content, 200)
        if body.strip():
            for line in body.split("\n")[:3]:
                self.append_to_output(f"    {line}", kind="tool_call")
