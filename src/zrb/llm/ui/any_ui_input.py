"""The UI's input side: asking, queueing, and withdrawing a message."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent
    from zrb.llm.shared.input_source import InputProvenance
    from zrb.llm.util.delivery_report import DeliveryReport


class AnyUIInput(ABC):
    """Questions to the user, and the queue a typed message enters."""

    @abstractmethod
    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""

    @abstractmethod
    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive shell command, handing it the real terminal."""

    def submit_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """Queue *user_message* the way a typed one is queued: steered into the
        running turn at its next model request, or run as the next turn when the
        session is idle.

        *source* names where the words came from, or is None for words that are
        not the user's. A UI that keeps no queue (a headless run has no idle
        session to wake) leaves the message alone, so a sender that is not
        the user — a finished background command — never assumes it arrived.
        """

    def withdraw_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """Take back a message `submit_message` queued that has not started.

        For a sender whose message became moot before anything read it — a
        finished background command whose result the model has since fetched.
        A message already read, or whose turn started, is beyond recall, and a UI
        that keeps no queue has nothing to take back: both leave it alone.
        """

    @abstractmethod
    def send_queued_messages_now(self) -> DeliveryReport:
        """Deliver the queued messages into the running turn, now.

        The report says what the attempt did: delivered into the live run,
        fell back to interrupting the turn, or moved nothing. A UI with no
        queue of its own moves nothing.
        """

    @abstractmethod
    def deliver_queued_messages_early(self) -> DeliveryReport:
        """Hand the ready queued messages to the running turn at a checkpoint.

        The run loop calls it as it builds each model request, and nothing is
        interrupted. A UI with no queue moves nothing.
        """

    @property
    @abstractmethod
    def is_waiting_for_answer(self) -> bool:
        """Whether a tool approval or a question is waiting for the user."""

    @property
    @abstractmethod
    def pending_answer_since(self) -> "float | None":
        """When the pending prompt appeared, as a `time.monotonic()` value, or
        ``None`` when nothing is pending or the UI cannot date it.

        A word spoken before that moment is not an answer to that prompt, so a
        "yes" said to nothing never approves a tool call that showed up while
        the words were still being recorded (ADR-0076)."""

    @abstractmethod
    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether the first prompt asked at or after *asked_at* (a
        `time.monotonic()` value) has been answered or cancelled. ``False``
        before it is asked, or when the UI cannot tell."""

    @abstractmethod
    def submit_answer(self, text: str) -> None:
        """Answer the pending prompt with *text*; with none pending, submit it
        as a message. Hands-free dictation delivers a spoken answer this way."""

    @abstractmethod
    def record_submitted_message(self, text: str) -> None:
        """Remember a message the user submitted, for recall."""

    @abstractmethod
    def take_pending_attachments(self) -> "list[UserContent]":
        """Hand over, and clear, the attachments waiting for the next message."""
