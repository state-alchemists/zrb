"""Shared queue-based input handling for event-driven UI backends.

Composed into `EventDrivenUI`, which needs "block on `get_input()` until a
message arrives via `handle_incoming_message()`" — see that class for what
it still owns.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from zrb.llm.custom_command.resolver import run_custom_command

if TYPE_CHECKING:
    from zrb.llm.ui.simple_ui_base import SimpleUI


class QueueBasedInput:
    """`input_queue`/`get_input`/`handle_incoming_message`, shared verbatim.

    Owns the queue and the waiting flag itself rather than reaching into
    `EventDrivenUI` state: only `print()`, `submit_message()` and
    `custom_commands` are read from `self._simple_ui`, and those are already
    public. `_llm_task` is reassignable via the `llm_task` property after
    construction on the owner, not this part.
    """

    def __init__(self, simple_ui: "SimpleUI") -> None:
        self._simple_ui = simple_ui
        self._input_queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._waiting_for_input = False
        self._waiting_since = 0.0
        self._last_ended_since = float("-inf")

    @property
    def input_queue(self) -> "asyncio.Queue[str]":
        """The queue incoming messages land on.

        The public read seam for the queue — without it a caller (or a test)
        asserting on queue state has to reach for the private attribute. Prefer
        `handle_incoming_message()` for *routing* a message in.
        """
        return self._input_queue

    @property
    def waiting_for_input(self) -> bool:
        """Whether `get_input` is currently blocked waiting for a response."""
        return self._waiting_for_input

    @waiting_for_input.setter
    def waiting_for_input(self, value: bool) -> None:
        if value and not self._waiting_for_input:
            self._waiting_since = time.monotonic()
        elif not value and self._waiting_for_input:
            self._last_ended_since = self._waiting_since
        self._waiting_for_input = value

    @property
    def waiting_since(self) -> float | None:
        """`time.monotonic()` when `get_input` began waiting, ``None`` when
        it is not waiting."""
        return self._waiting_since if self._waiting_for_input else None

    def is_answered_since(self, asked_at: float) -> bool:
        """Whether the first wait begun at or after *asked_at* has ended.
        Waits run one at a time, so that is the latest ended one."""
        return self._last_ended_since >= asked_at

    async def get_input(self, prompt: str) -> str:
        """Blocks until handle_incoming_message() receives a response."""
        if prompt:
            await self._simple_ui.print(f"❓ {prompt}", kind="text")
        self.waiting_for_input = True
        try:
            return await self.input_queue.get()
        finally:
            self.waiting_for_input = False

    def handle_incoming_message(self, text: str):
        """Call this when a message arrives from your backend.

        Routes the message to the appropriate handler:
        - If waiting for input (ask_user blocked), it goes to the queue
        - If it matches a custom slash command, the resolved prompt is sent,
          or the command runs in-process and its reply is printed
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self.waiting_for_input:
            self.input_queue.put_nowait(text)
            return
        outcome = (
            run_custom_command(text, self._simple_ui.custom_commands, self._simple_ui)
            if isinstance(text, str)
            else None
        )
        if outcome is None:
            self._simple_ui.submit_message(text)
        elif outcome.prompt is not None:
            self._simple_ui.submit_message(outcome.prompt)
        elif outcome.reply:
            asyncio.ensure_future(self._simple_ui.print(outcome.reply, kind="text"))
