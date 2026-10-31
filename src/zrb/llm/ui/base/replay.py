"""History-replay rendering for `BaseUI`: a resumed session renders through
the same paths as a live turn."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.ui.base.user_echo import echo_user_message
from zrb.llm.util.history_formatter import (
    format_args,
    format_timestamp,
    outcome_icon,
    truncate,
)
from zrb.llm.util.live_context_block import split_live_context
from zrb.llm.util.spoken import shown_text

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


class BaseUIReplay:
    """Replay loaded `ModelMessage`s through the live-render paths."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    def replay_history(self, messages: list) -> None:
        """Render loaded `ModelMessage`s the way a live conversation renders."""
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
                self._base_ui.append_to_output(f"\n🤖 {ts_display}>>\n")
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
                raw_content = getattr(part, "content", "") or ""
                if isinstance(raw_content, str):
                    content, live_context = split_live_context(raw_content)
                else:
                    content, live_context = str(raw_content), None
                echo_user_message(
                    self._base_ui.append_to_output,
                    self._base_ui.append_markdown,
                    header=f"\n💬 {ts_display}>> ",
                    body=content.strip(),
                )
                if live_context:
                    self._base_ui.append_to_output(
                        f"\n  🌐 {truncate(live_context, 500)}\n",
                        kind="live_context",
                    )
            elif pkind in ("retry-prompt", "retry-feedback"):
                # `retry-prompt` is the deprecated part, kept so history written
                # before pydantic-ai 2.60 still replays.
                content = str(getattr(part, "content", "") or "")
                self._base_ui.append_to_output(
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
        for part in parts:
            pkind = getattr(part, "part_kind", None)
            if pkind == "thinking":
                content = str(getattr(part, "content", "") or "")
                if content.strip():
                    self._base_ui.append_to_output(
                        f"  💭 {truncate(content, 500)}", kind="thinking"
                    )
            elif pkind == "text":
                content = str(getattr(part, "content", "") or "")
                if content.strip():
                    self._base_ui.append_to_output("\n")
                    # History keeps the markers, because the stop hook reads the
                    # same text for speech; a replayed reply is a screen, and a
                    # screen of run prose takes the run's column.
                    self._base_ui.append_answer(shown_text(content))
            elif pkind == "tool-call":
                self._replay_tool_call(part, pending_tool_calls)

    def _replay_tool_call(self, part, pending_tool_calls: dict[str, str]) -> None:
        """Render a single replayed tool call."""
        tool_name = getattr(part, "tool_name", None) or "unknown"
        tool_call_id = getattr(part, "tool_call_id", None) or "?"
        args_str = format_args(getattr(part, "args", None))
        if tool_call_id and tool_name:
            pending_tool_calls[tool_call_id] = tool_name
        self._base_ui.append_to_output(
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
        # Shared with the history formatter, so a reloaded transcript and a live
        # one cannot disagree about what a retried call looked like.
        status_icon = outcome_icon(outcome)
        content = str(getattr(part, "content", "") or "")
        self._base_ui.append_to_output(
            f"\n  🔠 {tool_call_id} | {tool_name} {status_icon}",
            kind="tool_call",
        )
        body = truncate(content, 200)
        if body.strip():
            for line in body.split("\n")[:3]:
                self._base_ui.append_to_output(f"    {line}", kind="tool_call")
