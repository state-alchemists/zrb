"""Confirmation queue for the default `UI`.

Concurrent text and choice requests share one FIFO active slot; sub-agent
answers can resolve the matching request by `agent_id`.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.tool.ambient_state import get_session_ownership_key
from zrb.llm.tool_call.choice_spec_format import get_option_label

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI


class UIConfirmation:
    """Per-request confirmation queue used by `ask_user` and `ask_user_choice`."""

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
        self._ui.confirmation.handle_asked(future)

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
        """Save and clear the input draft while awaiting an answer."""
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
        """Resolve the current prompt, normalizing matching choice labels."""
        spec = self._ui.confirmation.current_spec
        answer = _match_choice_label(spec, text) if spec is not None else text
        return self._ui.resolve_current(answer, echo=answer + "\n")

    def resolve_current(self, text: str, echo: str | None) -> bool:
        """Resolve the active request with `text`; optionally echo to output."""
        current = self._ui.confirmation.current
        if current is None:
            return False
        # Cleared first, or the echo is held behind the buffered output.
        self._ui.confirmation.current = None
        if echo:
            # Callers bake the trailing newline into `echo`.
            self._ui.append_to_output(echo, end="")
        if not current.done():
            current.set_result(text)
        self._ui.end_choice()
        self._activate_next_confirmation()
        return True

    def _flush_confirmation_buffer(self):
        """Flush buffered main-agent output to the output window."""
        held = self._ui.confirmation.output_buffer
        if not held:
            return
        chunks = list(held)
        held.clear()
        # Clear the slot so append_to_output's buffer guard lets this through.
        saved = self._ui.confirmation.current
        self._ui.confirmation.current = None
        for content, kind in chunks:
            self._ui.append_to_output(content, end="", kind=kind)
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
        """Cancel pending confirmations; optionally flush buffered output first."""
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


def _match_choice_label(spec: Any, text: str) -> str:
    """The option label(s) *text* names, joined like the selection widget
    joins them, else *text* as a free-text answer. A multi-select answer
    lists options separated by commas or "and": "1, 3", "red and blue"."""
    options = spec.get("options", []) if isinstance(spec, dict) else []
    labels = [get_option_label(option, index) for index, option in enumerate(options)]
    whole = _match_one_label(labels, text)
    if whole is not None:
        return whole
    if not spec.get("multi_select"):
        return text
    parts = [part for part in re.split(r",|\band\b", text) if part.strip()]
    matched = [_match_one_label(labels, part) for part in parts]
    if not matched or None in matched:
        return text
    return ", ".join(dict.fromkeys(label for label in matched if label))


def _match_one_label(labels: list[str], text: str) -> str | None:
    # Most exact first: "1" names the label "1" before the first option, and
    # "C" names "C" before "C++", which normalizes to "c" too.
    exact = text.strip().casefold()
    for label in labels:
        if label.strip().casefold() == exact:
            return label
    wanted = _normalize(text)
    if wanted.isdigit() and 1 <= int(wanted) <= len(labels):
        return labels[int(wanted) - 1]
    for label in labels:
        if _normalize(label) == wanted:
            return label
    return None


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())
