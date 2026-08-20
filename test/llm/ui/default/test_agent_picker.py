"""Tests for the sub-agent picker and live-view state (UIAgentPicker).

The widget's interactive parts (focus, invalidate) are exercised through the
public state-driver methods without a live terminal — `get_app()` calls inside
the mixin are guarded and no-op when no app is running. The live sub-agent
registry and the activity registry are replaced with lightweight fakes; the
picker only ever reads the former and reads the latter for per-row status.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from zrb.llm.ui.default.agent_picker import UIAgentPicker


class FakeUI:
    """Minimal host composing the real `UIAgentPicker`.

    Wires the state/methods the part reaches via `self._ui` (normally
    supplied by the default `UI`) and forwards everything else
    (public methods, properties, and the widget's own attributes the tests
    poke directly) to the composed part.
    """

    def __init__(self):
        self.conversation_session_name = "test_session"
        self.input_field = MagicMock()
        self.input_field.buffer = MagicMock(text="", cursor_position=0)
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._output_field.buffer = MagicMock(cursor_position=0)
        self.confirmation_queue: list = []
        self._picker = UIAgentPicker(self)
        self._picker.init_agent_picker_state()

    @property
    def output_text(self) -> str:
        return self._output_field.text

    def set_output_text(self, text: str) -> None:
        self._output_field.text = text
        self._output_field.buffer.cursor_position = len(text)

    def __getattr__(self, name):
        picker = self.__dict__.get("_picker")
        if picker is None:
            raise AttributeError(name)
        return getattr(picker, name)


class FakeLiveRegistry:
    """Stands in for `live_subagent_session_registry` in these tests."""

    def __init__(self, *sessions):
        self.sessions = {s.agent_id: s for s in sessions}
        self.cancelled = []

    def active(self, session_id):
        return list(self.sessions.values())

    def get(self, session_id, agent_id):
        return self.sessions.get(agent_id)

    def cancel(self, session_id, agent_id):
        self.cancelled.append((session_id, agent_id))
        session = self.sessions.get(agent_id)
        if session is None:
            return False
        return session.cancel_result if hasattr(session, "cancel_result") else True


def _session(agent_id, agent_name="researcher", buffer_text=""):
    buffered_ui = MagicMock()
    buffered_ui.get_buffered_output.return_value = buffer_text
    return SimpleNamespace(
        agent_id=agent_id,
        agent_name=agent_name,
        buffered_ui=buffered_ui,
        state="idle",
    )


def _activity(agent_id, ordinal=1, task="write report"):
    return SimpleNamespace(
        agent_id=agent_id, name="researcher", ordinal=ordinal, task=task, last_line=""
    )


def _open(ui, sessions):
    """Open the picker with the given sessions patched in, return the ui."""
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(*sessions),
    ):
        assert ui.open_agent_picker() is True
    return ui


def test_open_agent_picker_false_without_sessions():
    ui = FakeUI()
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(),
    ):
        assert ui.open_agent_picker() is False
    assert ui.has_active_agent_picker() is False


def test_open_agent_picker_opens_with_sessions():
    ui = FakeUI()
    _open(ui, [_session("a"), _session("b")])
    assert ui.has_active_agent_picker() is True
    assert ui.picker_cursor == 0


def test_move_agent_picker_cursor_clamps():
    ui = FakeUI()
    _open(ui, [_session("a"), _session("b")])
    ui.move_agent_picker_cursor(99)
    assert ui.picker_cursor == 1
    ui.move_agent_picker_cursor(-99)
    assert ui.picker_cursor == 0
    # No-op when closed.
    ui.close_agent_picker()
    ui.move_agent_picker_cursor(1)
    assert ui.picker_cursor == 0


def test_close_agent_picker_clears_without_viewing():
    ui = FakeUI()
    _open(ui, [_session("a")])
    ui.close_agent_picker()
    assert ui.has_active_agent_picker() is False
    assert ui.viewing_agent_id is None


def test_confirm_agent_picker_enters_view():
    ui = FakeUI()
    ui.set_output_text("main transcript")
    _open(ui, [_session("a", agent_name="researcher"), _session("b")])
    ui.move_agent_picker_cursor(1)
    assert ui.confirm_agent_picker() is True
    assert ui.viewing_agent_id == "b"
    assert ui.has_active_agent_picker() is False


def test_confirm_agent_picker_noop_when_closed():
    ui = FakeUI()
    assert ui.confirm_agent_picker() is False
    assert ui.viewing_agent_id is None


def test_enter_agent_view_parks_main_and_shows_subagent():
    ui = FakeUI()
    ui.set_output_text("main transcript")
    session = _session("a", buffer_text="sub-agent output")

    ui.enter_agent_view(session)

    assert ui.viewing_agent_id == "a"
    assert ui.saved_main_output == "main transcript"
    assert ui.output_text == "sub-agent output"


def test_enter_agent_view_same_agent_is_idempotent():
    ui = FakeUI()
    ui.set_output_text("main transcript")
    session = _session("a", buffer_text="sub-agent output")

    ui.enter_agent_view(session)
    ui.set_output_text("more sub-agent output")
    ui.enter_agent_view(session)  # same agent — must not re-park

    assert ui.saved_main_output == "main transcript"
    assert ui.output_text == "more sub-agent output"


def test_sync_output_to_viewed_agent_updates_and_converges():
    ui = FakeUI()
    session = _session("a", buffer_text="first")
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.output_text == "first"
        # Unchanged — no-op (must not re-invalidate forever).
        ui.sync_output_to_viewed_agent()
        assert ui.output_text == "first"
        # New buffered output is picked up on the next sync.
        session.buffered_ui.get_buffered_output.return_value = "first\nsecond"
        ui.sync_output_to_viewed_agent()
        assert ui.output_text == "first\nsecond"


def test_sync_output_returns_to_main_when_session_vanishes():
    ui = FakeUI()
    ui.set_output_text("main transcript")
    session = _session("a", buffer_text="sub-agent output")

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.output_text == "sub-agent output"
        # The session is torn down mid-view; the next sync exits the view.
        with patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            FakeLiveRegistry(),
        ):
            ui.sync_output_to_viewed_agent()
        assert ui.viewing_agent_id is None
        assert ui.output_text == "main transcript"


def test_exit_agent_view_restores_main():
    ui = FakeUI()
    ui.set_output_text("main transcript")
    session = _session("a", buffer_text="sub-agent output")

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.output_text == "sub-agent output"
        ui.exit_agent_view()

    assert ui.viewing_agent_id is None
    assert ui.saved_main_output is None
    assert ui.output_text == "main transcript"


def test_exit_agent_view_noop_when_not_viewing():
    ui = FakeUI()
    ui.set_output_text("main")
    ui.exit_agent_view()
    assert ui.viewing_agent_id is None
    assert ui.output_text == "main"


def test_cancel_viewed_agent_cancels_running_session_and_echoes():
    ui = FakeUI()
    session = _session("a", buffer_text="sub-agent output")
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.cancel_viewed_agent() is True
        session.buffered_ui.append_to_output.assert_called_with("\n<Esc> Canceled\n")
    assert ui.viewing_agent_id == "a"  # Esc cancels, it does not leave the view


def test_cancel_viewed_agent_noop_when_subagent_has_nothing_in_flight():
    ui = FakeUI()
    session = _session("a")
    session.cancel_result = False
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.cancel_viewed_agent() is False
        session.buffered_ui.append_to_output.assert_not_called()


def test_cancel_viewed_agent_noop_when_not_viewing():
    ui = FakeUI()
    assert ui.cancel_viewed_agent() is False


def test_picker_renders_running_and_finished_rows():
    ui = FakeUI()
    running = _session("a", agent_name="researcher")
    finished = _session("b", agent_name="reviewer")
    _open(ui, [running, finished])
    # The first is still tracked by the activity registry (running); the second
    # has finished, so its activity entry is gone.
    with patch(
        "zrb.llm.ui.default.agent_picker.agent_activity_registry",
        MagicMock(active=lambda session_id: [_activity("a", ordinal=3, task="report")]),
    ):
        text = "".join(t for _s, t in ui.get_agent_picker_text())

    assert "Select a sub-agent" in text
    assert "researcher" in text
    assert "#3" in text  # running row shows the activity ordinal
    assert "report" in text
    assert "[running]" in text
    assert "reviewer" in text
    assert "[finished]" in text
    assert "↑/↓ move · enter talk · esc cancel" in text


def test_picker_render_empty_when_closed():
    ui = FakeUI()
    assert ui.get_agent_picker_text() == []


def test_picker_flags_agent_with_pending_approval():
    """Regression: with several agents in flight, the picker must show
    *which* one has an unanswered approval request -- otherwise a user can
    pick the wrong one and think 'y' answered it (it just gets queued
    behind whichever is current instead)."""
    ui = FakeUI()
    pending_future = MagicMock(done=lambda: False)
    resolved_future = MagicMock(done=lambda: True)
    ui.confirmation_queue = [
        (pending_future, "", None, "a"),
        (resolved_future, "", None, "b"),
    ]
    _open(
        ui, [_session("a", agent_name="writer"), _session("b", agent_name="reviewer")]
    )

    text = "".join(t for _s, t in ui.get_agent_picker_text())

    assert (
        "writer" in text
        and "needs approval" in text.split("writer")[1].split("reviewer")[0]
    )
    assert "needs approval" not in text.split("reviewer")[1]


def test_picker_left_arrow_closes_picker_without_touching_view():
    """Regression: the picker can be reopened while already viewing an agent
    (Down Arrow has no `_viewing_agent_id` guard). Left previously had no
    binding on the picker's own control, so it fell through to the app-level
    Left and silently exited the agent view while the picker Float stayed
    drawn on top -- Left appeared to do nothing, and the next Escape then hit
    the app-level handler with the view already cleared, cancelling the main
    task instead of the sub-agent. Left on the picker's own control must only
    close the picker, leaving whatever view was already active untouched."""
    ui = FakeUI()
    session = _session("a", buffer_text="sub-agent output")
    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
        FakeLiveRegistry(session),
    ):
        ui.enter_agent_view(session)
        assert ui.viewing_agent_id == "a"

        _open(ui, [session])  # reopen the picker while already viewing "a"
        assert ui.has_active_agent_picker() is True

        kb = ui.agent_picker_window.content.key_bindings
        bindings = kb.get_bindings_for_keys(("left",))
        assert bindings, "expected a 'left' binding on the picker's own control"
        bindings[-1].handler(MagicMock())

    assert ui.has_active_agent_picker() is False
    assert ui.viewing_agent_id == "a"  # untouched -- still viewing the same agent


def test_picker_no_indicator_when_nothing_pending():
    ui = FakeUI()
    ui.confirmation_queue = []
    _open(ui, [_session("a")])

    text = "".join(t for _s, t in ui.get_agent_picker_text())

    assert "needs approval" not in text
