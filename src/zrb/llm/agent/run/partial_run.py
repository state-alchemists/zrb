"""Capture partial agent-run state for retry context.

Accumulates stream events during ``_execution_loop`` so that when a run is
cancelled or fails, a prose summary of what was attempted can be injected
into the next turn's history — preventing the LLM from repeating the same
mistakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TOOL_RESULT_PREVIEW_CHARS = 500


@dataclass
class PartialRunAccumulator:
    """Collects tool calls/results from stream events for retry context.

    Events are recorded during ``_execution_loop``'s ``async for event in stream``.
    On cancellation or error, ``build_summary()`` produces a prose description
    of tool calls and results accumulated before interruption.
    """

    _current_tool_name: str | None = None
    _current_tool_args: str | None = None
    _current_tool_call_id: str | None = None
    # Public output: (tool_name, args_preview, result_preview) for each tool that
    # completed before the run was interrupted. Read by ``build_summary()`` and by
    # callers deciding whether a summary is worth appending.
    completed_tools: list[tuple[str, str, str]] = field(default_factory=list)
    has_partial_text: bool = False
    is_interrupted: bool = False
    error: str = ""

    def record_event(self, event: Any) -> None:
        # lazy: heavy third-party deferral
        from pydantic_ai import (
            PartStartEvent,
            ToolCallEvent,
            ToolResultEvent,
        )
        from pydantic_ai.messages import TextPart

        if isinstance(event, PartStartEvent):
            if isinstance(event.part, TextPart):
                self.has_partial_text = True

        elif isinstance(event, ToolCallEvent):
            self._current_tool_name = event.part.tool_name
            self._current_tool_args = (
                self._truncate(str(event.part.args))
                if event.part.args is not None
                else ""
            )
            self._current_tool_call_id = event.part.tool_call_id

        elif isinstance(event, ToolResultEvent):
            tool_name = event.part.tool_name
            if tool_name is not None and tool_name == self._current_tool_name:
                result_preview = self._truncate(str(event.part.content))
                self.completed_tools.append(
                    (tool_name, self._current_tool_args or "", result_preview)
                )
            self._current_tool_name = None
            self._current_tool_args = None
            self._current_tool_call_id = None

    def build_summary(self) -> str:
        lines: list[str] = []
        lines.append("[SYSTEM: PREVIOUS ATTEMPT FAILED]")

        if self.error:
            lines.append(f"Error: {self.error}")

        if self.is_interrupted:
            lines.append("The previous attempt was interrupted before completing.")

        if self.completed_tools:
            lines.append("Before failing, the agent made these tool calls:")
            for name, args, result in self.completed_tools:
                lines.append(f"  → {name}")
                if args:
                    lines.append(f"    Args: {args}")
                lines.append(f"    Result: {result}")

        if self.has_partial_text:
            lines.append(
                "The agent had started writing a text response that was " "cut off."
            )

        lines.append(
            "Review the work already done to avoid repeating it. "
            "If the results above are useful, continue from them directly."
        )
        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_chars: int = _TOOL_RESULT_PREVIEW_CHARS) -> str:
        if len(text) > max_chars:
            return text[:max_chars] + "..."
        return text
