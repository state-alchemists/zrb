"""Shared queue-based input handling for event-driven/polling UI backends.

Composed into `EventDrivenUI` and `PollingUI`, which both need "block on
`get_input()` until a message arrives via `handle_incoming_message()`" but
differ in how they push output (event callback vs. polled queue) — see those
two classes for what each still owns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from zrb.llm.ui.simple_ui_base import SimpleUI


class QueueBasedInput:
    """`input_queue`/`get_input`/`handle_incoming_message`, shared verbatim.

    Takes the owning `EventDrivenUI`/`PollingUI` (a `SimpleUI`) rather than
    copying its state: `_input_queue`/`_waiting_for_input` are owned and set
    by the owner's own `__init__` (tests reassign `_waiting_for_input`
    directly), and `_llm_task` is reassignable via the `llm_task` property
    after construction — both must stay live reads through the owner, not a
    value cached here at construction time.
    """

    def __init__(self, owner: "SimpleUI") -> None:
        self._owner = owner

    @property
    def input_queue(self) -> "asyncio.Queue[str]":
        """The queue incoming messages land on.

        The public read seam for the queue — without it a caller (or a test)
        asserting on queue state has to reach for the private attribute. Prefer
        `handle_incoming_message()` for *routing* a message in.
        """
        return self._owner._input_queue

    async def get_input(self, prompt: str) -> str:
        """Blocks until handle_incoming_message() receives a response."""
        if prompt:
            await self._owner.print(f"❓ {prompt}", kind="text")
        self._owner._waiting_for_input = True
        try:
            return await self._owner._input_queue.get()
        finally:
            self._owner._waiting_for_input = False

    def handle_incoming_message(self, text: str):
        """Call this when a message arrives from your backend.

        Routes the message to the appropriate handler:
        - If waiting for input (ask_user blocked), it goes to the queue
        - If it matches a custom slash command, the resolved prompt is sent
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self._owner._waiting_for_input:
            self._owner._input_queue.put_nowait(text)
        else:
            effective = self._resolve_incoming_command(text)
            self._owner._submit_user_message(self._owner._llm_task, effective)

    def _resolve_incoming_command(self, text: str) -> str:
        """Resolve a custom slash command if the text starts with ``/``.

        Returns the resolved prompt or the original text unchanged.
        Built-in CLI commands (``/exit``, ``/save``, …) are not handled
        here — those belong to the interactive prompt_toolkit UI only.
        """
        # lazy: zrb internal but lightweight — no heavy deps
        from zrb.llm.custom_command.resolver import resolve_custom_command

        if isinstance(text, str):
            resolved = resolve_custom_command(text, self._owner._custom_commands)
            if resolved is not None:
                return resolved
        return text
