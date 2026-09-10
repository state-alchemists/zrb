"""Shared queue-based input handling for event-driven UI backends.

Composed into `EventDrivenUI`, which needs "block on `get_input()` until a
message arrives via `handle_incoming_message()`" — see that class for what
it still owns.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.llm.custom_command.resolver import resolve_custom_command

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
        self._waiting_for_input = value

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
        - If it matches a custom slash command, the resolved prompt is sent
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self.waiting_for_input:
            self.input_queue.put_nowait(text)
        else:
            effective = self._resolve_incoming_command(text)
            self._simple_ui.submit_message(effective)

    def _resolve_incoming_command(self, text: str) -> str:
        """Resolve a custom slash command if the text starts with ``/``.

        Returns the resolved prompt or the original text unchanged.
        Built-in CLI commands (``/exit``, ``/save``, …) are not handled
        here — those belong to the interactive prompt_toolkit UI only.
        """
        if isinstance(text, str):
            resolved = resolve_custom_command(text, self._simple_ui.custom_commands)
            if resolved is not None:
                return resolved
        return text
