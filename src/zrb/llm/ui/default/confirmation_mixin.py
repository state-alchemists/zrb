"""Confirmation-queue handling for the default `UI`.

Multiple parallel callers (e.g. delegate sub-agents) can each request user
input through `ask_user`/`ask_user_choice`; this mixin queues them so each
waits its turn, shows the prompt only when the request becomes current, and
cleans up on cancel.

Each queue entry is `(future, prompt, spec)`. `spec` is `None` for a plain
text confirmation (rendered by printing `prompt`); when set it is a
`ChoiceSpec` rendered by `SelectionMixin` as an arrow-key-selectable widget.
Both kinds share a single active slot (`_current_confirmation`) so text
confirmations and choices never contend for input at the same time.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import TextIO


class ConfirmationMixin:
    """Per-request confirmation queue used by `ask_user`/`ask_user_choice`."""

    # Host-class contract: state owned by `BaseUI.__init__`. Declared here so
    # static type checkers can verify accesses; the block does not run at
    # runtime.
    if TYPE_CHECKING:
        _confirmation_queue: list[tuple[asyncio.Future[str], str, Any]]
        _confirmation_output_buffer: list[str]
        _current_confirmation: asyncio.Future[str] | None

        # From OutputMixin
        def append_to_output(
            self,
            *values: object,
            sep: str = " ",
            end: str = "\n",
            file: "TextIO | None" = None,
            flush: bool = False,
            kind: str = "text",
        ) -> None: ...

    # Choice-widget hooks. No-ops by default; `SelectionMixin` overrides them
    # (it precedes this mixin in the default `UI` MRO) to render the widget.
    # Keeping defaults here lets `ConfirmationMixin` work standalone.
    def _begin_choice(self, spec: Any) -> None:
        pass

    def _end_choice(self) -> None:
        pass

    async def ask_user(self, prompt: str) -> str:
        """Prompt the user for free-text input via the main input field."""
        return await self._enqueue_request(prompt, None)

    async def ask_user_choice(self, spec: Any) -> str:
        """Ask a structured multiple-choice question via the selection widget."""
        return await self._enqueue_request("", spec)

    async def _enqueue_request(self, prompt: str, spec: Any) -> str:
        """Queue a request and await its answer.

        Queues so multiple concurrent callers each wait their turn. The request
        is rendered only when the caller becomes current.
        """
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        future: asyncio.Future[str] = asyncio.Future()
        self._confirmation_queue.append((future, prompt, spec))

        if self._current_confirmation is None:
            # Render BEFORE marking a confirmation pending. Order is
            # load-bearing: `append_to_output` buffers anything appended while
            # `_current_confirmation` is set and the agent is still thinking, so
            # main-agent tokens don't interleave with a prompt. Setting it first
            # would route this very prompt into that buffer — it would never
            # show, leaving the user at "waiting for confirmation" with no
            # question (e.g. AskUserQuestion, whose whole prompt arrives here).
            self._render_request(prompt, spec)
            self._current_confirmation = future
            get_app().invalidate()

        try:
            return await future
        finally:
            self._confirmation_queue = [
                entry for entry in self._confirmation_queue if entry[0] is not future
            ]
            if self._current_confirmation is future:
                self._current_confirmation = None
                self._end_choice()
                self._activate_next_confirmation()

    def _render_request(self, prompt: str, spec: Any) -> None:
        """Render a request: a choice widget when `spec` is set, else text."""
        if spec is not None:
            self._begin_choice(spec)
        elif prompt:
            self.append_to_output(prompt, end="")

    def submit_user_answer(self, text: str) -> bool:
        """Resolve the current confirmation prompt with the given answer (public API)."""
        return self._resolve_current(text, echo=text + "\n")

    def cancel_pending_confirmations(self):
        """Cancel pending confirmations so blocked `ask_user` calls release (public API)."""
        self._cancel_pending_confirmations()

    def _resolve_current(self, text: str, echo: str | None) -> bool:
        """Resolve the active request with `text`; optionally echo to output."""
        if self._current_confirmation is None:
            return False
        if echo:
            self.append_to_output(echo)
        if not self._current_confirmation.done():
            self._current_confirmation.set_result(text)
        self._current_confirmation = None
        self._end_choice()
        self._activate_next_confirmation()
        return True

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
            entry for entry in self._confirmation_queue if not entry[0].done()
        ]

        if self._confirmation_queue and self._current_confirmation is None:
            future, prompt, spec = self._confirmation_queue[0]
            # Same ordering contract as _enqueue_request(): render before marking
            # pending, else append_to_output's buffer guard swallows the prompt.
            self._render_request(prompt, spec)
            self._current_confirmation = future

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
        for future, _, _ in self._confirmation_queue:
            if not future.done():
                future.cancel()
        self._confirmation_queue.clear()
        self._current_confirmation = None
        self._end_choice()

    def _handle_confirmation(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        if self._resolve_current(text, echo=text + "\n"):
            buff.reset()
            return True
        return False
