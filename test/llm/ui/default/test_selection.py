"""Tests for the AskUserQuestion selection widget (UISelection).

The widget's interactive parts (focus, invalidate) are exercised through public
state-driver methods (`move_choice_cursor`, `toggle_choice_current`,
`confirm_choice`) without a live terminal — `get_app()` calls inside the mixin
are guarded and no-op when no app is running.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.default.confirmation import UIConfirmation
from zrb.llm.ui.default.selection import UISelection


class FakeUI:
    """Minimal host composing the real `UISelection` (plus a real
    `UIConfirmation` sibling, so `handle_confirmation`'s fall-through to
    `UIConfirmation`'s base case is exercised exactly as in the real default
    `UI`). `resolve_current` is overridden directly on this stand-in UI —
    `UISelection`/`UIConfirmation` both call `self._ui.resolve_current`,
    so this override is what they both see. `begin_choice`/`end_choice`/
    `handle_confirmation` mirror the real `UI`'s own one-line delegators to
    `UISelection`'s public implementation.
    """

    def __init__(self):
        self.input_field = object()
        self.confirmation_queue = []
        self.current_confirmation = "FUTURE"  # truthy sentinel
        self.resolved: str | None = None
        self.echoes: list[str] = []
        self._confirmation = UIConfirmation(self)
        self._selection = UISelection(self, confirmation=self._confirmation)
        self._selection.init_selection_state()

    def append_to_output(self, *values, **kwargs):
        self.echoes.append("".join(str(v) for v in values))

    def resolve_current(self, text, echo):
        self.resolved = text
        if echo:
            self.echoes.append(echo)
        self.current_confirmation = None
        self.end_choice()
        return True

    def begin_choice(self, spec):
        self._selection.begin_choice(spec)

    def end_choice(self):
        self._selection.end_choice()

    def handle_confirmation(self, event):
        return self._selection.handle_confirmation(event)

    def __getattr__(self, name):
        selection = self.__dict__.get("_selection")
        if selection is not None and hasattr(selection, name):
            return getattr(selection, name)
        confirmation = self.__dict__.get("_confirmation")
        if confirmation is not None:
            return getattr(confirmation, name)
        raise AttributeError(name)


def _event(text=""):
    event = MagicMock()
    event.current_buffer.text = text
    return event


def _spec(options, multi=False, index=1, total=1):
    return {
        "question": "Which DB?",
        "options": options,
        "multi_select": multi,
        "header": "DB",
        "index": index,
        "total": total,
    }


@pytest.fixture
def ui():
    return FakeUI()


def test_begin_choice_activates_without_echoing_question(ui):
    """The widget shows the question; it is not duplicated into scrollback yet."""
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    assert ui.has_active_choice() is True
    assert not any("Which DB?" in e for e in ui.echoes)


def test_resolve_echoes_question_and_answer(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.confirm_choice()
    joined = "".join(ui.echoes)
    assert "Which DB?" in joined
    assert "✔ A" in joined


def test_end_choice_clears_state(ui):
    ui.begin_choice(_spec([{"label": "A"}]))
    ui.end_choice()
    assert ui.has_active_choice() is False
    # Idempotent.
    ui.end_choice()
    assert ui.has_active_choice() is False


def test_render_shows_cursor_marker_and_counter(ui):
    ui.begin_choice(
        _spec(
            [{"label": "A", "description": "first"}, {"label": "B"}], index=2, total=3
        )
    )
    text = "".join(t for _, t in ui.get_choice_text())
    assert "(2/3)" in text
    assert "❯" in text  # cursor on first row
    assert "A" in text and "first" in text
    assert "Type my own answer" in text


def test_render_empty_when_no_active_choice(ui):
    assert ui.get_choice_text() == []


def test_move_cursor_clamps_within_rows(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    # rows = 2 options + 1 free-text = 3 (indices 0..2)
    ui.move_choice_cursor(-5)
    assert ui.choice_cursor == 0
    ui.move_choice_cursor(99)
    assert ui.choice_cursor == 2  # free-text row


def test_single_select_confirm_resolves_highlighted(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(1)
    assert ui.confirm_choice() is True
    assert ui.resolved == "B"
    assert ui.has_active_choice() is False


def test_multi_select_toggle_and_confirm_joins_labels(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True))
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(2)
    ui.toggle_choice_current()  # C
    ui.confirm_choice()
    assert ui.resolved == "A, C"


def test_multi_select_confirm_with_no_toggle_uses_cursor(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}], multi=True))
    ui.move_choice_cursor(1)
    ui.confirm_choice()
    assert ui.resolved == "B"


def test_toggle_ignored_in_single_select(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.toggle_choice_current()
    assert ui.choice_selected == set()


def test_toggle_ignored_on_free_text_row(ui):
    ui.begin_choice(_spec([{"label": "A"}], multi=True))
    ui.move_choice_cursor(99)  # free-text row
    ui.toggle_choice_current()
    assert ui.choice_selected == set()


def test_free_text_row_confirm_closes_widget_without_resolving(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(99)  # free-text row
    assert ui.confirm_choice() is True
    # Future still pending: the next input-field Enter resolves it.
    assert ui.resolved is None
    assert ui.has_active_choice() is False
    assert any("Type your answer" in e for e in ui.echoes)


def test_free_text_after_multi_select_combines_with_typed(ui):
    """Multi-select + 'type my own' → checked options plus the typed answer."""
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True))
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(2)
    ui.toggle_choice_current()  # C
    ui.move_choice_cursor(99)  # to free-text row
    ui.confirm_choice()
    assert ui.has_active_choice() is False
    # Typed answer arrives via the input field's Enter.
    ui.handle_confirmation(_event("custom thing"))
    assert ui.resolved == "A, C, custom thing"


def test_free_text_single_select_returns_only_typed(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(99)  # free-text row
    ui.confirm_choice()
    ui.handle_confirmation(_event("my answer"))
    assert ui.resolved == "my answer"


def test_free_text_with_empty_typed_keeps_checked_options(ui):
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}], multi=True))
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(99)  # free-text row
    ui.confirm_choice()
    ui.handle_confirmation(_event("   "))
    assert ui.resolved == "A"


def test_handle_confirmation_falls_through_without_pending_free_text(ui):
    """With no free-text pending, it delegates to the plain confirmation path."""
    ui.handle_confirmation(_event("plain answer"))
    assert ui.resolved == "plain answer"


def test_confirm_noop_when_no_active_choice(ui):
    assert ui.confirm_choice() is False


def test_operations_noop_when_no_active_choice(ui):
    # Should not raise when nothing is active.
    ui.move_choice_cursor(1)
    ui.toggle_choice_current()
    assert ui.has_active_choice() is False
