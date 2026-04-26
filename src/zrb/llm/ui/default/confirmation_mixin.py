"""Confirmation-queue handling for the default `UI`.

Multiple parallel callers (e.g. delegate sub-agents) can each request user
input through `ask_user`; this mixin queues them so each waits its turn,
shows the prompt only when the request becomes current, and cleans up on
cancel.
"""

from __future__ import annotations

import asyncio


class ConfirmationMixin:
    """Per-request confirmation queue used by `ask_user`."""

    async def ask_user(self, prompt: str) -> str:
        """Prompt the user for input via the main input field.

        Queues confirmation requests so multiple concurrent callers each wait
        their turn. The prompt is shown only when the caller becomes current.
        """
        from prompt_toolkit.application import get_app

        future: asyncio.Future[str] = asyncio.Future()
        self._confirmation_queue.append((future, prompt))

        if self._current_confirmation is None:
            self._current_confirmation = future
            if prompt:
                self.append_to_output(prompt, end="")
            get_app().invalidate()

        try:
            return await future
        finally:
            self._confirmation_queue = [
                (f, p) for f, p in self._confirmation_queue if f is not future
            ]
            if self._current_confirmation is future:
                self._current_confirmation = None
                self._activate_next_confirmation()

    def _activate_next_confirmation(self):
        """Activate the next confirmation in the queue after one completes."""
        from prompt_toolkit.application import get_app

        self._confirmation_queue = [
            (f, p) for f, p in self._confirmation_queue if not f.done()
        ]

        if self._confirmation_queue and self._current_confirmation is None:
            future, prompt = self._confirmation_queue[0]
            self._current_confirmation = future
            if prompt:
                self.append_to_output(prompt, end="")
            get_app().invalidate()

    def _cancel_pending_confirmations(self):
        """Cancel pending confirmations so blocked `ask_user` calls release."""
        for future, _ in self._confirmation_queue:
            if not future.done():
                future.cancel()
        self._confirmation_queue.clear()
        self._current_confirmation = None

    def _handle_confirmation(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if self._current_confirmation is not None:
            self.append_to_output(text + "\n")
            if not self._current_confirmation.done():
                self._current_confirmation.set_result(text)
            self._current_confirmation = None
            self._activate_next_confirmation()
            buff.reset()
            return True
        return False
