"""Confirmation-queue handling for the default `UI`.

Concurrent callers (e.g. delegate sub-agents) of `ask_user`/`ask_user_choice`
are queued; each prompt is shown only when its request becomes current.

Each entry is `(future, prompt, spec, agent_id)`. `spec` is `None` for plain
text, else a `ChoiceSpec` rendered by `UISelection`. `agent_id` (`None` for the
main agent) lets an answer typed in a sub-agent's live view resolve that
agent's own request rather than the FIFO head (`_resolve_for_agent`). Text
and choice requests share one active slot so they never contend for input.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.tool.ambient_state import get_session_ownership_key

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI


class UIConfirmation:
    """Per-request confirmation queue used by `ask_user`/`ask_user_choice`.

    `begin_choice`/`end_choice`/`resolve_current` go through `self._ui`,
    which routes them to `UISelection`; a UI composing only this part must
    supply its own no-op `begin_choice`/`end_choice`.
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
        """Queue a request, rendered once it becomes current, and await it."""
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        future: asyncio.Future[str] = asyncio.Future()
        self._ui.confirmation.queue.append((future, prompt, spec, agent_id))

        if self._ui.confirmation.current is None:
            # Render before marking pending: `append_to_output` buffers output
            # while a confirmation is current, which would swallow this prompt.
            self._save_and_clear_input_draft()
            self._render_request(prompt, spec)
            self._ui.confirmation.current = future
            get_app().invalidate()

        try:
            return await future
        finally:
            queue = self._ui.confirmation.queue
            self._ui.confirmation.queue = [
                entry for entry in queue if entry[0] is not future
            ]
            if self._ui.confirmation.current is future:
                self._ui.confirmation.current = None
                self._ui.end_choice()
                self._activate_next_confirmation()

    def _render_request(self, prompt: str, spec: Any) -> None:
        """Render a request: a choice widget when `spec` is set, else text."""
        if spec is not None:
            self._ui.begin_choice(spec)
        elif prompt:
            self._ui.append_to_output(prompt, end="")

    def _save_and_clear_input_draft(self) -> None:
        """Stash the half-typed message and clear the field for the answer.

        The answer is read from the input buffer, so a draft would otherwise
        be taken as a free-text denial. Restored once the queue drains.
        """
        if self._saved_draft is not None:
            return
        input_field = getattr(self._ui, "input_field", None)
        if input_field is None:
            return
        buffer = input_field.buffer
        self._saved_draft = (buffer.text, buffer.cursor_position)
        buffer.text = ""

    def _restore_input_draft(self) -> None:
        """Put the stashed draft back into the input field, if any."""
        saved = self._saved_draft
        if saved is None:
            return
        self._saved_draft = None
        input_field = getattr(self._ui, "input_field", None)
        if input_field is None:
            return
        text, cursor = saved
        buffer = input_field.buffer
        buffer.text = text
        buffer.cursor_position = cursor

    def submit_user_answer(self, text: str) -> bool:
        """Resolve the current confirmation prompt with the given answer (public API)."""
        return self._ui.resolve_current(text, echo=text + "\n")

    def resolve_current(self, text: str, echo: str | None) -> bool:
        """Resolve the active request with `text`; optionally echo to output."""
        if self._ui.confirmation.current is None:
            return False
        if echo:
            # Callers bake the trailing newline into `echo`.
            self._ui.append_to_output(echo, end="")
        if not self._ui.confirmation.current.done():
            self._ui.confirmation.current.set_result(text)
        self._ui.confirmation.current = None
        self._ui.end_choice()
        self._activate_next_confirmation()
        return True

    def _flush_confirmation_buffer(self):
        """Flush buffered main-agent output to the output window."""
        if not self._ui.confirmation.output_buffer:
            return
        content = "".join(self._ui.confirmation.output_buffer)
        self._ui.confirmation.output_buffer.clear()
        # Clear the slot so append_to_output's buffer guard lets this through.
        saved = self._ui.confirmation.current
        self._ui.confirmation.current = None
        self._ui.append_to_output(content)
        self._ui.confirmation.current = saved

    def _activate_next_confirmation(self):
        """Activate the next confirmation in the queue after one completes."""
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        self._flush_confirmation_buffer()

        pending_queue = self._ui.confirmation.queue
        self._ui.confirmation.queue = [
            entry for entry in pending_queue if not entry[0].done()
        ]

        queue = self._ui.confirmation.queue
        if queue and self._ui.confirmation.current is None:
            future, prompt, spec, _agent_id = queue[0]
            # Render before marking pending, as in `_enqueue_request`.
            self._render_request(prompt, spec)
            self._ui.confirmation.current = future
        elif not self._ui.confirmation.queue:
            # The queue drained: restore the half-typed draft.
            self._restore_input_draft()

        # Refresh so the status bar reflects the new confirmation state.
        get_app().invalidate()

    def cancel_pending_confirmations(self, flush: bool = True):
        """Cancel pending confirmations so blocked `ask_user` calls release (public API).

        Args:
            flush: Whether to flush the confirmation output buffer first;
                ``False`` on exit, where the write is wasted latency.
        """
        if flush:
            self._flush_confirmation_buffer()
        for future, _, _, _ in self._ui.confirmation.queue:
            if not future.done():
                future.cancel()
        self._ui.confirmation.queue.clear()
        self._ui.confirmation.current = None
        self._ui.end_choice()
        self._restore_input_draft()

    def handle_confirmation(self, event) -> bool:
        buff = event.current_buffer
        text = buff.text
        viewing_agent_id = getattr(self._ui, "viewing_agent_id", None)
        CFG.LOGGER.debug(
            "confirmation debug: viewing_agent_id=%r queue=%r current_is=%r",
            viewing_agent_id,
            [
                (entry_agent_id, fut.done())
                for fut, _, _, entry_agent_id in self._ui.confirmation.queue
            ],
            "current" if self._ui.confirmation.current is not None else None,
        )
        if viewing_agent_id is not None:
            # In a sub-agent's view, answer only that agent's own request;
            # with none pending, the text falls through as a chat message.
            if self._resolve_for_agent(viewing_agent_id, text):
                buff.reset()
                return True
            return False
        if self._ui.confirmation.current is None:
            return False
        # Reset before resolving, which restores the stashed draft here.
        buff.reset()
        return self._ui.resolve_current(text, echo=text + "\n")

    def _resolve_for_agent(self, agent_id: str, text: str) -> bool:
        """Resolve `agent_id`'s own pending confirmation, if any.

        Unlike `resolve_current`, may resolve a request that is not yet the
        FIFO head; the answer is echoed into that agent's live view.
        """
        for future, _, _, entry_agent_id in self._ui.confirmation.queue:
            if entry_agent_id != agent_id or future.done():
                continue
            if future is self._ui.confirmation.current:
                self._ui.resolve_current(text, echo=None)
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

        session_id = get_session_ownership_key(
            getattr(self._ui, "conversation_session_name", "")
        )
        entry = live_subagent_session_registry.get(session_id, agent_id)
        if entry is not None:
            entry.buffered_ui.append_to_output(f"{text}\n")
