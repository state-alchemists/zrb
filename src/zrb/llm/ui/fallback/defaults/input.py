"""Inert input role: a UI with no queue and no prompt of its own.

A UI that keeps no queue silently drops what it is handed, which is the promise a
background command relies on when it wakes a session that has nowhere to put the
result: the sender must not assume it arrived. The two questions the role asks —
`ask_user`, `run_interactive_command` — have no default at all, because a UI
without them cannot ask the user anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from zrb.llm.util.delivery_report import DeliveryOutcome, DeliveryReport

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.shared.input_source import InputProvenance
    from zrb.llm.ui.any_ui_input import AnyUIInput


class UIInputDefaults:
    """The input role for a UI that keeps no queue and answers no prompt."""

    @property
    def input(self) -> "AnyUIInput":
        """A UI that asks and queues its own messages is its own input side."""
        return cast("AnyUIInput", self)

    @property
    def is_waiting_for_answer(self) -> bool:
        """No prompt of its own to wait on."""
        return False

    @property
    def pending_answer_since(self) -> "float | None":
        """No prompt of its own to date."""
        return None

    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """No prompt of its own to have answered."""
        return False

    def submit_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """No queue of its own, so the message goes nowhere.

        A sender that is not the user — a finished background command, a
        sub-agent's report — must not assume it arrived; see
        `AnyUIInput.submit_message`.
        """

    def withdraw_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """No queue of its own, so there is nothing to take back."""

    def submit_answer(self, text: str) -> None:
        """Answer the pending prompt with *text*; with no queue, a no-op."""
        self.submit_message(text, None)

    def send_queued_messages_now(self) -> DeliveryReport:
        """No queue of its own, so nothing to deliver."""
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)

    def deliver_queued_messages_early(self) -> DeliveryReport:
        """No queue of its own, so nothing to hand to the turn."""
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)

    def record_submitted_message(self, text: str) -> None:
        """No recall list to remember it in."""

    def take_pending_attachments(self) -> "list[UserContent]":
        """No attachments wait on a UI that keeps none."""
        return []
