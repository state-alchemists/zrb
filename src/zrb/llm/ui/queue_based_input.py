"""Queue-based input handling composed into `EventDrivenUI`."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from zrb.llm.custom_command.resolver import run_custom_command
from zrb.llm.input_source import InputProvenance

if TYPE_CHECKING:
    from zrb.llm.ui.simple_ui_base import SimpleUI


class QueueBasedInput:
    """Blocks `get_input()` until `handle_incoming_message()` delivers."""

    def __init__(self, simple_ui: "SimpleUI") -> None:
        self._simple_ui = simple_ui
        self._input_queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._waiting_for_input = False
        self._waiting_since = 0.0
        self._last_ended_since = float("-inf")

    @property
    def input_queue(self) -> "asyncio.Queue[str]":
        """The queue incoming messages land on; route via
        `handle_incoming_message()`."""
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

    def _submit_message(self, text: str, source: InputProvenance | None) -> None:
        if source is None:
            self._simple_ui.submit_message(text)
        else:
            self._simple_ui.submit_message(text, source)

    def handle_incoming_message(self, text: str, source: InputProvenance | None = None):
        """Route a message from your backend: to a blocked `ask_user`, to a
        custom slash command, or else as a new user message."""
        if self.waiting_for_input:
            self.input_queue.put_nowait(text)
            return
        outcome = (
            run_custom_command(text, self._simple_ui.custom_commands, self._simple_ui)
            if isinstance(text, str)
            else None
        )
        if outcome is None:
            self._submit_message(text, source)
        elif outcome.prompt is not None:
            self._submit_message(outcome.prompt, source)
        elif outcome.reply:
            asyncio.ensure_future(self._simple_ui.print(outcome.reply, kind="text"))
