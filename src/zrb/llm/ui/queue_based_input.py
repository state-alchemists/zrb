"""Shared queue-based input handling for event-driven/polling UI backends.

Composed into `EventDrivenUI` and `PollingUI`, which both need "block on
`get_input()` until a message arrives via `handle_incoming_message()`" but
differ in how they push output (event callback vs. polled queue) — see those
two classes for what each still owns.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
    from zrb.llm.task.llm_task import LLMTask
    from zrb.task.any_task import AnyTask


class QueueBasedInput:
    """`input_queue`/`get_input`/`handle_incoming_message`, shared verbatim.

    Host-class contract: state and methods owned by the concrete UI class
    composing this part (`SimpleUI.__init__` sets `_llm_task`; the host's own
    `__init__` sets `_input_queue`/`_waiting_for_input`). Declared here so
    static type checkers can verify accesses; the block does not run at
    runtime.
    """

    if TYPE_CHECKING:
        _llm_task: "LLMTask"
        _input_queue: "asyncio.Queue[str]"
        _waiting_for_input: bool
        _custom_commands: "list[AnyCustomCommand]"

        async def print(self, text: str, kind: str = "text") -> None: ...

        def _submit_user_message(
            self, llm_task: "AnyTask", user_message: str
        ) -> None: ...

    @property
    def input_queue(self) -> "asyncio.Queue[str]":
        """The queue incoming messages land on.

        The public read seam for the queue — without it a caller (or a test)
        asserting on queue state has to reach for the private attribute. Prefer
        `handle_incoming_message()` for *routing* a message in.
        """
        return self._input_queue

    async def get_input(self, prompt: str) -> str:
        """Blocks until handle_incoming_message() receives a response."""
        if prompt:
            await self.print(f"❓ {prompt}", kind="text")
        self._waiting_for_input = True
        try:
            return await self._input_queue.get()
        finally:
            self._waiting_for_input = False

    def handle_incoming_message(self, text: str):
        """Call this when a message arrives from your backend.

        Routes the message to the appropriate handler:
        - If waiting for input (ask_user blocked), it goes to the queue
        - If it matches a custom slash command, the resolved prompt is sent
        - Otherwise, it's submitted as a new user message to the LLM
        """
        if self._waiting_for_input:
            self._input_queue.put_nowait(text)
        else:
            effective = self._resolve_incoming_command(text)
            self._submit_user_message(self._llm_task, effective)

    def _resolve_incoming_command(self, text: str) -> str:
        """Resolve a custom slash command if the text starts with ``/``.

        Returns the resolved prompt or the original text unchanged.
        Built-in CLI commands (``/exit``, ``/save``, …) are not handled
        here — those belong to the interactive prompt_toolkit UI only.
        """
        # lazy: zrb internal but lightweight — no heavy deps
        from zrb.llm.custom_command.resolver import resolve_custom_command

        if isinstance(text, str):
            resolved = resolve_custom_command(text, self._custom_commands)
            if resolved is not None:
                return resolved
        return text
