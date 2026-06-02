"""Confirmation-queue handling for the default `UI`.

Multiple parallel callers (e.g. delegate sub-agents) can each request user
input through `ask_user`; this mixin queues them so each waits its turn,
shows the prompt only when the request becomes current, and cleans up on
cancel.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING


class ConfirmationMixin:
    """Per-request confirmation queue used by `ask_user`."""

    # Host-class contract: state owned by `BaseUI.__init__`. Declared here so
    # static type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _confirmation_queue: list[tuple[asyncio.Future[str], str]]
        _confirmation_output_buffer: list[str]
        _current_confirmation: asyncio.Future[str] | None

    async def ask_user(self, prompt: str) -> str:
        """Prompt the user for input via the main input field.

        Queues confirmation requests so multiple concurrent callers each wait
        their turn. The prompt is shown only when the caller becomes current.
        """
        # lazy: heavy third-party
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

    def submit_user_answer(self, text: str) -> bool:
        """Resolve the current confirmation prompt with the given answer (public API)."""
        if self._current_confirmation is not None:
            self.append_to_output(text + "\n")
            if not self._current_confirmation.done():
                self._current_confirmation.set_result(text)
            self._current_confirmation = None
            self._activate_next_confirmation()
            return True
        return False

    def cancel_pending_confirmations(self):
        """Cancel pending confirmations so blocked `ask_user` calls release (public API)."""
        self._cancel_pending_confirmations()

    def _flush_confirmation_buffer(self):
        """Flush buffered main-agent output to the output window."""
        if not self._confirmation_output_buffer:
            return
        content = "".join(self._confirmation_output_buffer)
        self._confirmation_output_buffer.clear()
        # Bypass the buffer guard in append_to_output
        saved = self._current_confirmation
        self._current_confirmation = None
        self.append_to_output(content)
        self._current_confirmation = saved

    def _activate_next_confirmation(self):
        """Activate the next confirmation in the queue after one completes."""
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        self._flush_confirmation_buffer()

        self._confirmation_queue = [
            (f, p) for f, p in self._confirmation_queue if not f.done()
        ]

        if self._confirmation_queue and self._current_confirmation is None:
            future, prompt = self._confirmation_queue[0]
            self._current_confirmation = future
            if prompt:
                self.append_to_output(prompt, end="")

        # Always refresh so the status bar reflects the new confirmation state
        # (including the transition back to "working" or "ready" when queue empties).
        get_app().invalidate()

    def _cancel_pending_confirmations(self, flush: bool = True):
        """Cancel pending confirmations so blocked `ask_user` calls release.

        Args:
            flush: Whether to flush the confirmation output buffer first.
                Pass ``False`` from the Ctrl+C / exit path (the app is about
                to exit, so writing buffered tokens is wasted work and adds
                latency to the abort).
        """
        if flush:
            self._flush_confirmation_buffer()
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
