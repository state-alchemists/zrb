"""Capture partial agent-run state for retry context.

Accumulates stream events during ``_execution_loop`` so that when a run is
cancelled or fails, a prose summary of what was attempted can be injected
into the next turn's history — preventing the LLM from repeating the same
mistakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zrb.util.truncate import truncate_display

_TOOL_RESULT_PREVIEW_CHARS = 500


@dataclass
class PartialRunAccumulator:
    """Collects tool calls/results from stream events for retry context.

    Events are recorded during ``_execution_loop``'s ``async for event in stream``.
    On cancellation or error, ``build_summary()`` produces a prose description
    of tool calls and results accumulated before interruption.
    """

    # Parallel calls stream all their ToolCallEvents before any result, so
    # pending calls are keyed by tool_call_id rather than held in one slot.
    _pending_calls: dict[str, tuple[str, str]] = field(default_factory=dict)
    # Public output: (tool_name, args_preview, result_preview) for each tool that
    # completed before the run was interrupted. Read by ``build_summary()`` and by
    # callers deciding whether a summary is worth appending.
    completed_tools: list[tuple[str, str, str]] = field(default_factory=list)
    has_partial_text: bool = False
    is_interrupted: bool = False
    error: str = ""
    # Live reference to the in-progress run's `RunContext.messages` — the same
    # list object the pydantic-ai graph appends to in place, so it reflects
    # everything done so far (including dangling tool calls mid-step) even
    # though `agent.run()` hasn't returned yet. Read by the outer exception/
    # cancellation handlers in `_execution_loop` as a fresher fallback than the
    # last completed `agent.run()` call's `run_history`. `None` until the first
    # event of a run arrives.
    latest_history: list[Any] | None = None

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
            args = event.part.args
            self._pending_calls[event.part.tool_call_id] = (
                event.part.tool_name,
                (
                    truncate_display(str(args), _TOOL_RESULT_PREVIEW_CHARS)
                    if args is not None
                    else ""
                ),
            )

        elif isinstance(event, ToolResultEvent):
            pending = self._pending_calls.pop(event.part.tool_call_id, None)
            if pending is not None and pending[0] == event.part.tool_name:
                result_preview = truncate_display(
                    str(event.part.content), _TOOL_RESULT_PREVIEW_CHARS
                )
                self.completed_tools.append((*pending, result_preview))

    def build_summary(self) -> str:
        lines: list[str] = []
        lines.append("[SYSTEM: PREVIOUS ATTEMPT FAILED]")

        if self.error:
            lines.append(f"Error: {self.error}")

        if self.is_interrupted:
            lines.append(
                "The previous attempt was interrupted before completing — "
                "usually by the user, which can mean they disagreed with its "
                "direction."
            )

        if self.completed_tools:
            lines.append(
                "Before failing, the agent made these tool calls (results cut "
                f"at {_TOOL_RESULT_PREVIEW_CHARS} characters — re-read anything "
                "you need in full):"
            )
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
            "Review the work already done to avoid repeating it. The results "
            "above are real; the approach that produced them may not be right. "
            "Follow the user's latest message over the earlier plan."
        )
        return "\n".join(lines)
