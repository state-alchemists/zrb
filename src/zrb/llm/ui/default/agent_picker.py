"""Sub-agent picker and live-view state for the default `UI`.

The "talk to a running sub-agent directly" feature: press Down Arrow with an
empty input field to open a picker listing every live (running or just-finished)
sub-agent session tracked by `live_subagent_session_registry`; pick one with
Enter to switch the output pane to that sub-agent's own buffered transcript and
route typed messages to it. While viewing, Left Arrow returns to the main
session (navigation — it never touches the sub-agent's work); Esc cancels what
the sub-agent is doing, mirroring how Esc behaves on the main agent.

State lives in two places on this part (exposed publicly — `picker_cursor`,
`agent_picker_window`, `viewing_agent_id`, `saved_main_output` — for whichever
sibling needs it, reached via `self._ui`):

* `_picker_sessions` / `_picker_cursor` / `_agent_picker_window` — the picker
  widget itself (a focusable `Window` shown as a `Float`, same approach as
  `UISelection`; no nested `Application`).
* `_viewing_agent_id` / `_saved_main_output` — the live view. While viewing, the
  output pane is a redraw-time snapshot of the sub-agent's buffer (see
  `sync_output_to_viewed_agent`), the main transcript is parked in
  `saved_main_output`, and Enter routes to the sub-agent instead of the main
  session (see `UIKeybindings._handle_enter_dispatch`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.agent.activity import agent_activity_registry
from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from zrb.llm.agent.subagent.live_session import LiveSubAgentSession
    from zrb.llm.ui.default.ui import UI


class UIAgentPicker:
    """Sub-agent picker + live-view state (part of the default `UI`)."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui
        self._viewing_agent_id: str | None = None
        self._saved_main_output: str | None = None
        self._picker_sessions: list = []
        self._picker_cursor: int = 0
        self._agent_picker_window: Any = None

    def init_agent_picker_state(self) -> None:
        """Initialize the picker widget and the live-view state (hidden)."""
        self._viewing_agent_id = None
        self._saved_main_output = None
        self._picker_sessions = []
        self._picker_cursor = 0
        self._agent_picker_window = self._create_agent_picker_window()

    def has_active_agent_picker(self) -> bool:
        """Whether the sub-agent picker is currently being shown (public API)."""
        return bool(self._picker_sessions)

    @property
    def viewing_agent_id(self) -> str | None:
        """The sub-agent the output pane currently shows, if any."""
        return self._viewing_agent_id

    @viewing_agent_id.setter
    def viewing_agent_id(self, value: str | None) -> None:
        self._viewing_agent_id = value

    @property
    def saved_main_output(self) -> str | None:
        """The main transcript parked while viewing a sub-agent, if any."""
        return self._saved_main_output

    @saved_main_output.setter
    def saved_main_output(self, value: str | None) -> None:
        self._saved_main_output = value

    @property
    def picker_cursor(self) -> int:
        """Index of the highlighted row in the sub-agent picker."""
        return self._picker_cursor

    @property
    def agent_picker_window(self) -> Any:
        """The picker's own focusable `Window` (a `Float` shown over the output pane)."""
        return self._agent_picker_window

    def open_agent_picker(self) -> bool:
        """Show the picker when this session has tracked sub-agents.

        Returns ``False`` (leaving the Down Arrow free for history recall)
        when nothing is trackable. Called from ``UIMessageEditing.handle_down_arrow``.
        """
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import (
            live_subagent_session_registry,
        )

        sessions = live_subagent_session_registry.active(
            self._ui.conversation_session_name
        )
        if not sessions:
            return False
        self._picker_sessions = list(sessions)
        self._picker_cursor = 0
        try:
            # lazy: heavy third-party
            from prompt_toolkit.application import get_app

            get_app().layout.focus(self._agent_picker_window)
        except Exception as e:
            # Layout not ready (e.g. before first render) — focus on next paint.
            CFG.LOGGER.debug(f"Agent-picker focus failed: {e}")
        self._invalidate()
        return True

    def close_agent_picker(self) -> None:
        """Dismiss the picker without entering any view (public API)."""
        if not self._picker_sessions:
            return
        self._picker_sessions = []
        self._picker_cursor = 0
        try:
            # lazy: heavy third-party
            from prompt_toolkit.application import get_app

            get_app().layout.focus(self._ui.input_field)
        except Exception as e:
            # Layout not ready — focus on next paint.
            CFG.LOGGER.debug(f"Input-field focus failed: {e}")
        self._invalidate()

    def move_agent_picker_cursor(self, delta: int) -> None:
        """Move the picker cursor by `delta`, clamped (public API)."""
        if not self._picker_sessions:
            return
        count = len(self._picker_sessions)
        self._picker_cursor = max(0, min(count - 1, self._picker_cursor + delta))
        self._invalidate()

    def confirm_agent_picker(self) -> bool:
        """Enter the highlighted sub-agent's live view (public API).

        Returns ``False`` when the picker is not active; ``True`` after
        switching (or when already viewing that agent).
        """
        if not self._picker_sessions:
            return False
        session = self._picker_sessions[self._picker_cursor]
        self.enter_agent_view(session)
        self.close_agent_picker()
        return True

    def enter_agent_view(self, session: "LiveSubAgentSession") -> None:
        """Switch the output pane to `session`'s buffered transcript.

        Parks the main transcript (the output pane's current text) so Left can
        restore it exactly, then syncs the pane to the sub-agent's buffer.
        """
        if self._viewing_agent_id == session.agent_id:
            return
        self._saved_main_output = self._ui.output_text
        self._viewing_agent_id = session.agent_id
        self._show_viewed_agent_output(session.buffered_ui.get_buffered_output())

    def exit_agent_view(self) -> None:
        """Return the output pane to the main transcript (Left while viewing)."""
        if self._viewing_agent_id is None:
            return
        self._viewing_agent_id = None
        if self._saved_main_output is not None:
            self._ui.set_output_text(self._saved_main_output)
            self._saved_main_output = None
        self._invalidate()

    def cancel_viewed_agent(self) -> bool:
        """Cancel what the viewed sub-agent is doing (Esc while viewing).

        Mirrors the main agent's Esc: it stops the sub-agent's in-flight work
        and drops its queued messages — it does *not* leave the view (Left
        does that). Returns ``False`` when not viewing or when the sub-agent
        had nothing in flight to cancel. On success, a ``<Esc> Canceled`` note
        lands in the sub-agent's own buffer so its live view reflects it.
        """
        if self._viewing_agent_id is None:
            return False
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import (
            live_subagent_session_registry,
        )

        session_id = self._ui.conversation_session_name
        agent_id = self._viewing_agent_id
        if not live_subagent_session_registry.cancel(session_id, agent_id):
            return False
        entry = live_subagent_session_registry.get(session_id, agent_id)
        if entry is not None:
            entry.buffered_ui.append_to_output("\n<Esc> Canceled\n")
        self._invalidate()
        return True

    def sync_output_to_viewed_agent(self) -> None:
        """Copy the viewed sub-agent's buffered output into the output pane.

        Called from the app's after-render hook (the periodic
        ``LLM_UI_REFRESH_INTERVAL`` redraw) while `_viewing_agent_id` is set.
        No-op when the content is unchanged, so a quiet sub-agent does not
        re-invalidate the app forever.
        """
        if self._viewing_agent_id is None:
            return
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import (
            live_subagent_session_registry,
        )

        session = live_subagent_session_registry.get(
            self._ui.conversation_session_name, self._viewing_agent_id
        )
        if session is None:
            # The session was torn down while we were viewing it — return to main.
            self.exit_agent_view()
            return
        self._show_viewed_agent_output(session.buffered_ui.get_buffered_output())

    def toggle_viewed_agent_block(self) -> bool:
        """Expand/collapse the collapsible block at the output cursor, in
        the currently-viewed sub-agent's own scope (public API).

        The sub-agent's `BufferedUI` tracks its own toggle blocks
        independently of the main transcript's `UIOutput.rendered_blocks`
        (see `BufferedUI.toggle_collapsible_block_at_offset`) — this method
        is the routing point `UI.toggle_collapsible_block` calls into while
        `viewing_agent_id` is set, so Ctrl+O always operates on whatever is
        actually displayed. Returns `False` when not viewing, when the
        session vanished, or when nothing was found to toggle.
        """
        if self._viewing_agent_id is None:
            return False
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import (
            live_subagent_session_registry,
        )

        session = live_subagent_session_registry.get(
            self._ui.conversation_session_name, self._viewing_agent_id
        )
        if session is None:
            return False
        offset = self._ui.output_field.buffer.cursor_position
        toggled = session.buffered_ui.toggle_collapsible_block_at_offset(offset)
        if toggled:
            self._show_viewed_agent_output(session.buffered_ui.get_buffered_output())
        return toggled

    def _show_viewed_agent_output(self, content: str) -> None:
        if content == self._ui.output_text:
            return
        self._ui.set_output_text(content)

    # --- widget construction --------------------------------------------

    def _create_agent_picker_window(self) -> Any:
        # lazy: heavy third-party
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        kb = KeyBindings()

        @kb.add("up")
        def _(event):
            self.move_agent_picker_cursor(-1)

        @kb.add("down")
        def _(event):
            self.move_agent_picker_cursor(1)

        @kb.add("enter")
        def _(event):
            self.confirm_agent_picker()

        @kb.add("escape")
        def _(event):
            self.close_agent_picker()

        @kb.add("left")
        def _(event):
            # The picker can be reopened while already viewing an agent (Down
            # Arrow works regardless of `_viewing_agent_id` — see
            # `UIMessageEditing.handle_down_arrow`). Without this, Left had no
            # binding on the picker's own control, so it fell through to the
            # app-level Left (`viewing_sub_agent`-filtered, in keybindings.py),
            # which silently exited the agent view while the picker Float
            # stayed drawn on top of it — Left appeared to do nothing, and the
            # next Escape then hit the app-level handler with
            # `_viewing_agent_id` already cleared, cancelling the main task
            # instead of the sub-agent. Closing just the picker here (like
            # Escape) leaves whatever view was already active untouched.
            self.close_agent_picker()

        control = FormattedTextControl(
            self.get_agent_picker_text, focusable=True, key_bindings=kb
        )
        return Window(
            content=control, style="class:agent-picker", dont_extend_height=True
        )

    # --- rendering -------------------------------------------------------

    def get_agent_picker_text(self) -> "StyleAndTextTuples":
        if not self._picker_sessions:
            return []
        activity = agent_activity_registry.active(
            session_id=self._ui.conversation_session_name
        )
        by_id = {entry.agent_id: entry for entry in activity}
        frags: StyleAndTextTuples = [
            ("class:agent-picker.question bold", " Select a sub-agent to talk to\n")
        ]
        for i, session in enumerate(self._picker_sessions):
            frags += self._render_picker_row(i, session, by_id.get(session.agent_id))
        frags.append(
            ("class:agent-picker.hint", "\n ↑/↓ move · enter talk · esc cancel\n")
        )
        return frags

    def _render_picker_row(
        self,
        i: int,
        session: "LiveSubAgentSession",
        activity_entry: Any,
    ) -> "StyleAndTextTuples":
        cursor = "❯ " if i == self._picker_cursor else "  "
        style = (
            "class:agent-picker.selected"
            if i == self._picker_cursor
            else "class:agent-picker.option"
        )
        running = activity_entry is not None
        if running:
            label = f"{session.agent_name} #{activity_entry.ordinal}"
        else:
            label = session.agent_name
        state = "running" if running else "finished"
        row: StyleAndTextTuples = [(style, f" {cursor}{label}")]
        if running and activity_entry.task:
            row.append(
                (
                    "class:agent-picker.desc",
                    f"  — {truncate_display(activity_entry.task, 50)}",
                )
            )
        row.append((style, f" [{state}]"))
        if self._agent_needs_approval(session.agent_id):
            row.append(("class:agent-picker.needs-approval", " ⏳ needs approval"))
        row.append((style, "\n"))
        return row

    def _agent_needs_approval(self, agent_id: str) -> bool:
        """Whether `agent_id` has an unresolved confirmation request queued.

        Lets the picker flag *which* running agent(s) are actually blocked on
        an approval — without it, a user with several sub-agents in flight has
        no way to tell them apart and may confirm-answer the wrong one (its
        request just gets queued behind whichever is current).
        """
        queue = getattr(self._ui, "confirmation_queue", [])
        return any(
            entry_agent_id == agent_id and not future.done()
            for future, _, _, entry_agent_id in queue
        )

    # --- helpers ---------------------------------------------------------

    def _invalidate(self) -> None:
        try:
            # lazy: heavy third-party
            from prompt_toolkit.application import get_app

            get_app().invalidate()
        except Exception as e:
            # No active app to repaint — safe to ignore.
            CFG.LOGGER.debug(f"Agent-picker invalidate failed: {e}")
