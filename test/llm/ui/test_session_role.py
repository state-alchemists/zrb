"""The session role is a narrowing of the UI, not a second object beside it.

`ui.session` hands out the UI itself, because every implementation in zrb is its
own session: `BaseUI` tracks the conversation, `MultiUI` reads it off its primary
child, `BufferedUI` off the UI it wraps. A part that forwarded to the host would
pass every call-site test and still break the first subclass that overrides
`model`, so these tests pin the identity and the override rather than the calls.
"""

from __future__ import annotations

from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.any_ui_session import AnyUISession
from zrb.llm.ui.fallback.state_defaults import UIStateDefaultsMixin


class _StatefulUI(UIStateDefaultsMixin):
    """A UI that tracks a model, the way a backend with a real session would."""

    def __init__(self) -> None:
        self._model = "the-ui-model"

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value) -> None:
        self._model = value


def test_the_accessor_hands_out_the_ui_itself():
    ui = _StatefulUI()

    assert ui.session is ui


def test_a_subclass_override_is_what_the_session_reports():
    """The role must not carry a copy of the state it names."""
    ui = _StatefulUI()

    assert ui.session.model == "the-ui-model"

    ui.session.model = "switched"

    assert ui.model == "switched"


def test_a_ui_that_tracks_no_state_still_answers_for_the_role():
    ui = _StatefulUI()

    assert ui.session.model == "the-ui-model"
    assert ui.session.is_thinking is False
    assert ui.session.conversation_session_name == ""
    assert ui.session.is_turn_running is False
    assert ui.session.background_tasks is ui.session.background_tasks


def test_the_aggregate_no_longer_inherits_the_session_role():
    """A caller typed against `AnyUI` sees `session`; the fifteen members are the
    role's, so a new one cannot widen the aggregate."""
    assert hasattr(AnyUI, "session")
    assert not issubclass(AnyUI, AnyUISession)
