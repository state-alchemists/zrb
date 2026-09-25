"""Sub-agent picker and live-view state for the default `UI`.

Down Arrow on an empty input opens a picker of the live (running or
just-finished) sub-agent sessions in `live_subagent_session_registry`; Enter
switches the output pane to that sub-agent's buffered transcript and routes
typed messages to it. In that view, Left returns to the main session and Esc
cancels the sub-agent's work.

* Picker widget: `_picker_sessions` / `_picker_cursor` / `_agent_picker_window`
  (a focusable `Window` in a `Float`, like `UISelection`).
* Live view: `_viewing_agent_id` / `_saved_main_output`. The pane is a
  redraw-time snapshot of the sub-agent's buffer (`sync_output_to_viewed_agent`)
  and the main transcript is parked in `saved_main_output`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.tool.ambient_state import get_session_ownership_key
from zrb.llm.ui.default.app.focus import focus_widget, invalidate_app
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
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

        sessions = live_subagent_session_registry.active(
            get_session_ownership_key(self._ui.conversation_session_name)
        )
        if not sessions:
            return False
        self._picker_sessions = list(sessions)
        self._picker_cursor = 0
        focus_widget(self._agent_picker_window, "Agent-picker")
        self._invalidate()
        return True

    def close_agent_picker(self) -> None:
        """Dismiss the picker without entering any view (public API)."""
        if not self._picker_sessions:
            return
        self._picker_sessions = []
        self._picker_cursor = 0
        focus_widget(self._ui.input_field, "Input-field")
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

        Stops in-flight work and drops queued messages without leaving the
        view. Returns ``False`` when not viewing or nothing was in flight; on
        success notes ``<Esc> Canceled`` in the sub-agent's own buffer.
        """
        if self._viewing_agent_id is None:
            return False
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

        session_id = get_session_ownership_key(self._ui.conversation_session_name)
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

        Called from the after-render hook while viewing. No-op when the
        content is unchanged, so a quiet sub-agent does not repaint forever.
        """
        if self._viewing_agent_id is None:
            return
        session = self._get_viewed_session(self._viewing_agent_id)
        if session is None:
            # Torn down while viewed: return to the main transcript.
            self.exit_agent_view()
            return
        self._show_viewed_agent_output(session.buffered_ui.get_buffered_output())

    def toggle_viewed_agent_block(self) -> bool:
        """Toggle the collapsible block at the output cursor in the viewed
        sub-agent's own `BufferedUI` scope (public API).

        Returns `False` when not viewing, the session vanished, or nothing
        was toggled.
        """
        if self._viewing_agent_id is None:
            return False
        session = self._get_viewed_session(self._viewing_agent_id)
        if session is None:
            return False
        offset = self._ui.output_field.buffer.cursor_position
        toggled = session.buffered_ui.toggle_collapsible_block_at_offset(offset)
        if toggled:
            self._show_viewed_agent_output(session.buffered_ui.get_buffered_output())
        return toggled

    def _get_viewed_session(self, agent_id: str) -> "LiveSubAgentSession | None":
        # lazy: transitively heavy via internal — live_session.py imports
        # run_agent (zrb.llm.agent.run.runner), which pulls in pydantic_ai.
        from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

        return live_subagent_session_registry.get(
            get_session_ownership_key(self._ui.conversation_session_name),
            agent_id,
        )

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
            # The picker can open over an agent view; binding Left here keeps
            # it from reaching the app-level Left, which would exit that view
            # behind the still-drawn picker.
            self.close_agent_picker()

        control = FormattedTextControl(
            self.get_agent_picker_text, focusable=True, key_bindings=kb
        )
        # Wrap rather than clip long names and activity lines.
        return Window(
            content=control,
            style="class:agent-picker",
            dont_extend_height=True,
            wrap_lines=True,
        )

    # --- rendering -------------------------------------------------------

    def get_agent_picker_text(self) -> "StyleAndTextTuples":
        if not self._picker_sessions:
            return []
        activity = agent_activity_registry.active(
            session_id=get_session_ownership_key(self._ui.conversation_session_name)
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

        Flags which of several in-flight sub-agents is blocked on approval.
        """
        confirmation = getattr(self._ui, "confirmation", None)
        queue = [] if confirmation is None else confirmation.queue
        return any(
            entry_agent_id == agent_id and not future.done()
            for future, _, _, entry_agent_id in queue
        )

    # --- helpers ---------------------------------------------------------

    def _invalidate(self) -> None:
        invalidate_app("Agent-picker")
