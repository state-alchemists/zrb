"""Inert implementations of `AnyUI`'s state members and side-effect hooks.

For UIs that track none of that state (`StdUI`, `BufferedUI`, `MultiUI`), and
the fallback `BaseUI` inherits for any member it does not implement itself.
Bodies live here, not on `AnyUI`, because `any_*.py` is excluded from coverage
and `AnyUI` stays a pure contract. A host that implements a member for real wins
on MRO.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TextIO

from zrb.llm.util.delivery_report import DeliveryOutcome, DeliveryReport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.agent.types import ModelMessage, RequestUsage, RunUsage, UserContent
    from zrb.llm.ui.base.message_queue import QueuedMessage


class UIStateDefaultsMixin:
    """Default `AnyUI` state members for UIs that do not track them."""

    # Class-level defaults so no `__init__` is needed; setters shadow them per
    # instance. Prefixed so they cannot collide with a host's own fields.
    _uidefaults_is_thinking: bool = False
    _uidefaults_llm_task: Any = None
    _uidefaults_model: Any = None
    _uidefaults_multi_ui_parent: Any = None
    # None, not set(): a mutable class attribute would be shared by instances.
    _uidefaults_background_tasks: "set[asyncio.Task] | None" = None
    _uidefaults_small_model: Any = None
    _uidefaults_multimodal_model: Any = None
    _uidefaults_conversation_session_name: str = ""
    _uidefaults_plan_mode_active: bool = False
    _uidefaults_last_output: str = ""

    @property
    def is_thinking(self) -> bool:
        return self._uidefaults_is_thinking

    @is_thinking.setter
    def is_thinking(self, value: bool) -> None:
        self._uidefaults_is_thinking = value

    @property
    def llm_task(self) -> Any:
        return self._uidefaults_llm_task

    @llm_task.setter
    def llm_task(self, value: Any) -> None:
        self._uidefaults_llm_task = value

    @property
    def model(self) -> Any:
        return self._uidefaults_model

    @model.setter
    def model(self, value: Any) -> None:
        self._uidefaults_model = value

    @property
    def yolo(self) -> bool | frozenset:
        """Never auto-approve."""
        return False

    @property
    def multi_ui_parent(self) -> Any:
        return self._uidefaults_multi_ui_parent

    @multi_ui_parent.setter
    def multi_ui_parent(self, parent: Any) -> None:
        self._uidefaults_multi_ui_parent = parent

    @property
    def tool_call_handler(self) -> Any:
        """No handler of its own; callers fall back to an approval channel."""
        return None

    @property
    def small_model(self) -> Any:
        return self._uidefaults_small_model

    @small_model.setter
    def small_model(self, value: Any) -> None:
        self._uidefaults_small_model = value

    @property
    def multimodal_model(self) -> Any:
        return self._uidefaults_multimodal_model

    @multimodal_model.setter
    def multimodal_model(self, value: Any) -> None:
        self._uidefaults_multimodal_model = value

    @property
    def conversation_session_name(self) -> str:
        return self._uidefaults_conversation_session_name

    @conversation_session_name.setter
    def conversation_session_name(self, value: str) -> None:
        self._uidefaults_conversation_session_name = value

    @property
    def plan_mode_active(self) -> bool:
        return self._uidefaults_plan_mode_active

    @plan_mode_active.setter
    def plan_mode_active(self, value: bool) -> None:
        self._uidefaults_plan_mode_active = value

    @property
    def last_output(self) -> str:
        """Nothing rendered."""
        return self._uidefaults_last_output

    @property
    def snapshot_manager(self) -> Any:
        """No snapshots of its own, so nothing to rewind to."""
        return None

    @property
    def history_manager(self) -> Any:
        """No history of its own; the session's manager lives on the primary."""
        return None

    @property
    def background_tasks(self) -> "set[asyncio.Task]":
        """One mutable set per instance, created on first access."""
        if self._uidefaults_background_tasks is None:
            self._uidefaults_background_tasks = set()
        return self._uidefaults_background_tasks

    @property
    def is_turn_running(self) -> bool:
        """No turn of its own to run."""
        return False

    @property
    def is_waiting_for_answer(self) -> bool:
        """No prompt of its own to wait on."""
        return False

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """No prompt of its own to have answered."""
        return False

    def invalidate_ui(self) -> None:
        """No surface to repaint."""

    def set_status_badge(self, key: str, text: str | None) -> None:
        """No status bar to show a badge in."""

    def track_echo_span(self, entry: "QueuedMessage", echo: str) -> None:
        """No output buffer to record an echo span against."""

    def redraw_echo(self, entry: "QueuedMessage") -> str | None:
        """No output buffer to splice a rewritten echo into."""
        return None

    def remove_echo(self, entry: "QueuedMessage") -> None:
        """No output buffer to take a dropped echo out of."""

    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """No confirmations of its own to release."""

    def cancel_current_turn(self, reason: str) -> None:
        """No turn of its own to cancel."""

    def flush_to_parent(self) -> None:
        """Nothing buffered, so nothing to hand upward."""

    def send_queued_messages_now(self) -> DeliveryReport:
        """No queue of its own, so nothing to deliver."""
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)

    # Side-effect hooks. The two that write (`append_markdown`,
    # `record_tool_call_block`) and `replay_history` go through the host's
    # `append_to_output`; every other default does nothing.

    if TYPE_CHECKING:

        def append_to_output(
            self,
            *values: object,
            sep: str = " ",
            end: str = "\n",
            file: TextIO | None = None,
            flush: bool = False,
            kind: str = "text",
        ):
            """The host's writer, which `AnyUI` declares abstract."""

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """No session meter to fold usage into."""

    def reset_context_usage(self) -> None:
        """No context size to forget."""

    def append_markdown(self, markdown_text: str) -> None:
        """Render *markdown_text* and write the text."""
        # lazy: transitively heavy -- the renderer pulls the theme and the
        # markdown stack.
        from zrb.util.cli.markdown import render_markdown

        self.append_to_output(render_markdown(markdown_text, width=None), end="")

    def append_answer(self, markdown_text: str) -> None:
        """No column layout: the answer is shown like any other Markdown."""
        self.append_markdown(markdown_text)

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Nothing to expand later: write the collapsed form as a `tool_call` line."""
        self.append_to_output(collapsed, end="", kind="tool_call")

    def mark_thinking_block_start(self) -> None:
        """No live thinking block to place."""

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool | None:
        """No block tracked: the thinking text stays as streamed."""
        return None

    def mark_text_block_start(self) -> None:
        """No text block to place."""

    def collapse_text_block(self, collapsed: str, full: str) -> bool | None:
        """No block tracked: the streamed text stays as it is."""
        return None

    def settle_text_block(self, source: str) -> None:
        """The streamed copy stays as it is."""

    def set_stream_indentation(self, indent: str) -> None:
        """No wrapping of its own to adjust."""

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """No status bar to time a tool call in."""

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """No status bar to stop a timer in."""

    def replay_history(self, messages: "list[ModelMessage]") -> None:
        """Write the resumed conversation as plain text."""
        # lazy: zrb.llm.util.history_formatter transitively loads pydantic_ai.
        from zrb.llm.util.history_formatter import format_history_as_text

        self.append_to_output(format_history_as_text(messages))

    async def update_system_info(self) -> None:
        """No status line to refresh."""

    def record_submitted_message(self, text: str) -> None:
        """No recall list to remember it in."""

    def take_pending_attachments(self) -> "list[UserContent]":
        """No attachments wait on a UI that keeps none."""
        return []

    def track_rendered_echo(self, entry: "QueuedMessage", header: str) -> None:
        """No output buffer to record an echo span against."""

    def redraw_echoes(self, entries: "Sequence[QueuedMessage]") -> None:
        """No output buffer to rewrite delivered echoes in."""

    def deliver_queued_messages_early(self) -> DeliveryReport:
        """No queue of its own, so nothing to hand to the turn."""
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)
