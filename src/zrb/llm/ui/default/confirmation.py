"""Confirmation-queue handling for the default `UI`.

Multiple parallel callers (e.g. delegate sub-agents) can each request user
input through `ask_user`/`ask_user_choice`; this mixin queues them so each
waits its turn, shows the prompt only when the request becomes current, and
cleans up on cancel.

Each queue entry is `(future, prompt, spec, agent_id)`. `spec` is `None` for
a plain text confirmation (rendered by printing `prompt`); when set it is a
`ChoiceSpec` rendered by `UISelection` as an arrow-key-selectable widget.
`agent_id` is the originating sub-agent's id (`None` for the main agent),
propagated from `BufferedUI.ask_user`/`ask_user_choice` — it lets a keypress
made while viewing a sub-agent's live view resolve that agent's own request
instead of whichever one the main FIFO happens to have made current (see
`_resolve_for_agent`). Both kinds share a single active slot
(`_current_confirmation`) so text confirmations and choices never contend
for input at the same time.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI


class UIConfirmation:
    """Per-request confirmation queue used by `ask_user`/`ask_user_choice`.

    The choice-widget hooks (`_begin_choice`/`_end_choice`) and `_resolve_current`
    are called through `self._ui` rather than same-part `self`: the composed
    `UI` delegates them to `UISelection` (which renders the actual widget), and a
    test double that wants different behavior overrides them directly on its own
    stand-in UI. A standalone UI that composes only `UIConfirmation` must
    supply its own no-op `_begin_choice`/`_end_choice`.
    """

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._saved_draft: tuple[str, int] | None = None

    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Prompt the user for free-text input via the main input field."""
        return await self._enqueue_request(prompt, None, agent_id)

    async def ask_user_choice(self, spec: Any, agent_id: str | None = None) -> str:
        """Ask a structured multiple-choice question via the selection widget."""
        return await self._enqueue_request("", spec, agent_id)

    async def _enqueue_request(
        self, prompt: str, spec: Any, agent_id: str | None = None
    ) -> str:
        """Queue a request and await its answer.

        Queues so multiple concurrent callers each wait their turn. The request
        is rendered only when the caller becomes current.
        """
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        future: asyncio.Future[str] = asyncio.Future()
        self._ui._confirmation_queue.append((future, prompt, spec, agent_id))

        if self._ui._current_confirmation is None:
            # Render BEFORE marking a confirmation pending. Order is
            # load-bearing: `append_to_output` buffers anything appended while
            # `_current_confirmation` is set and the agent is still thinking, so
            # main-agent tokens don't interleave with a prompt. Setting it first
            # would route this very prompt into that buffer — it would never
            # show, leaving the user at "waiting for confirmation" with no
            # question (e.g. AskUserQuestion, whose whole prompt arrives here).
            self._save_and_clear_input_draft()
            self._render_request(prompt, spec)
            self._ui._current_confirmation = future
            get_app().invalidate()

        try:
            return await future
        finally:
            queue = self._ui._confirmation_queue
            self._ui._confirmation_queue = [
                entry for entry in queue if entry[0] is not future
            ]
            if self._ui._current_confirmation is future:
                self._ui._current_confirmation = None
                self._ui._end_choice()
                self._activate_next_confirmation()

    def _render_request(self, prompt: str, spec: Any) -> None:
        """Render a request: a choice widget when `spec` is set, else text."""
        if spec is not None:
            self._ui._begin_choice(spec)
        elif prompt:
            self._ui.append_to_output(prompt, end="")

    def _save_and_clear_input_draft(self) -> None:
        """Stash the half-typed message and clear the field for the answer.

        The confirmation answer is read from the input field's buffer, so any
        text the user had already typed would otherwise be swallowed as a
        free-text denial. Stash it (text + cursor) on the first activation and
        restore it once the queue drains (`_restore_input_draft`).
        """
        if getattr(self, "_saved_draft", None) is not None:
            return
        input_field = getattr(self._ui, "_input_field", None)
        if input_field is None:
            return
        buffer = input_field.buffer
        self._saved_draft = (buffer.text, buffer.cursor_position)
        buffer.text = ""

    def _restore_input_draft(self) -> None:
        """Put the stashed draft back into the input field, if any."""
        saved = getattr(self, "_saved_draft", None)
        if saved is None:
            return
        self._saved_draft = None
        input_field = getattr(self._ui, "_input_field", None)
        if input_field is None:
            return
        text, cursor = saved
        buffer = input_field.buffer
        buffer.text = text
        buffer.cursor_position = cursor

    def submit_user_answer(self, text: str) -> bool:
        """Resolve the current confirmation prompt with the given answer (public API)."""
        return self._ui._resolve_current(text, echo=text + "\n")

    def cancel_pending_confirmations(self):
        """Cancel pending confirmations so blocked `ask_user` calls release (public API)."""
        self._cancel_pending_confirmations()

    def _resolve_current(self, text: str, echo: str | None) -> bool:
        """Resolve the active request with `text`; optionally echo to output."""
        if self._ui._current_confirmation is None:
            return False
        if echo:
            self._ui.append_to_output(echo)
        if not self._ui._current_confirmation.done():
            self._ui._current_confirmation.set_result(text)
        self._ui._current_confirmation = None
        self._ui._end_choice()
        self._activate_next_confirmation()
        return True

    def _flush_confirmation_buffer(self):
        """Flush buffered main-agent output to the output window."""
        if not self._ui._confirmation_output_buffer:
            return
        content = "".join(self._ui._confirmation_output_buffer)
        self._ui._confirmation_output_buffer.clear()
        # Bypass the buffer guard in append_to_output
        saved = self._ui._current_confirmation
        self._ui._current_confirmation = None
        self._ui.append_to_output(content)
        self._ui._current_confirmation = saved

    def _activate_next_confirmation(self):
        """Activate the next confirmation in the queue after one completes."""
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        self._flush_confirmation_buffer()

        pending_queue = self._ui._confirmation_queue
        self._ui._confirmation_queue = [
            entry for entry in pending_queue if not entry[0].done()
        ]

        queue = self._ui._confirmation_queue
        if queue and self._ui._current_confirmation is None:
            future, prompt, spec, _agent_id = queue[0]
            # Same ordering contract as _enqueue_request(): render before marking
            # pending, else append_to_output's buffer guard swallows the prompt.
            self._render_request(prompt, spec)
            self._ui._current_confirmation = future
        elif not self._ui._confirmation_queue:
            # The queue drained: hand the half-typed message back to the user.
            self._restore_input_draft()

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
        for future, _, _, _ in self._ui._confirmation_queue:
            if not future.done():
                future.cancel()
        self._ui._confirmation_queue.clear()
        self._ui._current_confirmation = None
        self._ui._end_choice()
        self._restore_input_draft()

    def _handle_confirmation(self, event) -> bool:
        # lazy: circular — base.ui -> config -> ... -> confirmation
        from zrb.config.config import CFG

        buff = event.current_buffer
        text = buff.text
        viewing_agent_id = getattr(self._ui, "_viewing_agent_id", None)
        CFG.LOGGER.debug(
            "confirmation debug: viewing_agent_id=%r queue=%r current_is=%r",
            viewing_agent_id,
            [
                (entry_agent_id, fut.done())
                for fut, _, _, entry_agent_id in self._ui._confirmation_queue
            ],
            "current" if self._ui._current_confirmation is not None else None,
        )
        if viewing_agent_id is not None:
            # Looking at a sub-agent's live view: an answer targets that
            # specific agent's own pending request, never whichever request
            # the main FIFO happens to have made current (which may belong to
            # a different sub-agent, or the main agent). If this agent has
            # nothing pending, fall through to plain dispatch (the text
            # becomes a chat message to it) rather than resolving someone
            # else's confirmation.
            if self._resolve_for_agent(viewing_agent_id, text):
                buff.reset()
                return True
            return False
        if self._ui._current_confirmation is None:
            return False
        # Clear the answer text BEFORE resolving: resolving hands any stashed
        # draft back into this same buffer, and resetting after the fact would
        # wipe it.
        buff.reset()
        return self._ui._resolve_current(text, echo=text + "\n")

    def _resolve_for_agent(self, agent_id: str, text: str) -> bool:
        """Resolve `agent_id`'s own pending confirmation, if any.

        Unlike `_resolve_current`, this may resolve a request that is still
        queued (not yet the FIFO head) — finding it here means we're
        answering from that agent's own live view, so the answer is echoed
        there instead of the main transcript.
        """
        for future, _, _, entry_agent_id in self._ui._confirmation_queue:
            if entry_agent_id != agent_id or future.done():
                continue
            if future is self._ui._current_confirmation:
                self._ui._resolve_current(text, echo=None)
            else:
                future.set_result(text)
            self._echo_to_agent(agent_id, text)
            return True
        return False

    def _echo_to_agent(self, agent_id: str, text: str) -> None:
        """Echo an answer into `agent_id`'s own buffered live view."""
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

        session_id = getattr(self._ui, "_conversation_session_name", "")
        entry = live_subagent_session_registry.get(session_id, agent_id)
        if entry is not None:
            entry.buffered_ui.append_to_output(f"{text}\n")
