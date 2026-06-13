"""Tests for the AskUserQuestion selection widget (SelectionMixin).

The widget's interactive parts (focus, invalidate) are exercised through public
state-driver methods (`move_choice_cursor`, `toggle_choice_current`,
`confirm_choice`) without a live terminal — `get_app()` calls inside the mixin
are guarded and no-op when no app is running.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.default.confirmation_mixin import ConfirmationMixin
from zrb.llm.ui.default.selection_mixin import SelectionMixin


class FakeUI(SelectionMixin, ConfirmationMixin):
    """Minimal host wiring the hooks SelectionMixin expects.

    Inherits ConfirmationMixin so `_handle_confirmation`'s super() fall-through
    is exercised exactly as in the real default `UI` MRO.
    """

    def __init__(self):
        self._input_field = object()
        self._current_confirmation = "FUTURE"  # truthy sentinel
        self.resolved: str | None = None
        self.echoes: list[str] = []
        self._init_selection_state()

    def append_to_output(self, *values, **kwargs):
        self.echoes.append("".join(str(v) for v in values))

    def _resolve_current(self, text, echo):
        self.resolved = text
        if echo:
            self.echoes.append(echo)
        self._current_confirmation = None
        self._end_choice()
        return True


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
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    assert ui.has_active_choice() is True
    assert not any("Which DB?" in e for e in ui.echoes)


def test_resolve_echoes_question_and_answer(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.confirm_choice()
    joined = "".join(ui.echoes)
    assert "Which DB?" in joined
    assert "✔ A" in joined


def test_end_choice_clears_state(ui):
    ui._begin_choice(_spec([{"label": "A"}]))
    ui._end_choice()
    assert ui.has_active_choice() is False
    # Idempotent.
    ui._end_choice()
    assert ui.has_active_choice() is False


def test_render_shows_cursor_marker_and_counter(ui):
    ui._begin_choice(
        _spec(
            [{"label": "A", "description": "first"}, {"label": "B"}], index=2, total=3
        )
    )
    text = "".join(t for _, t in ui._get_choice_text())
    assert "(2/3)" in text
    assert "❯" in text  # cursor on first row
    assert "A" in text and "first" in text
    assert "Type my own answer" in text


def test_render_empty_when_no_active_choice(ui):
    assert ui._get_choice_text() == []


def test_move_cursor_clamps_within_rows(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    # rows = 2 options + 1 free-text = 3 (indices 0..2)
    ui.move_choice_cursor(-5)
    assert ui._choice_cursor == 0
    ui.move_choice_cursor(99)
    assert ui._choice_cursor == 2  # free-text row


def test_single_select_confirm_resolves_highlighted(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(1)
    assert ui.confirm_choice() is True
    assert ui.resolved == "B"
    assert ui.has_active_choice() is False


def test_multi_select_toggle_and_confirm_joins_labels(ui):
    ui._begin_choice(
        _spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True)
    )
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(2)
    ui.toggle_choice_current()  # C
    ui.confirm_choice()
    assert ui.resolved == "A, C"


def test_multi_select_confirm_with_no_toggle_uses_cursor(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}], multi=True))
    ui.move_choice_cursor(1)
    ui.confirm_choice()
    assert ui.resolved == "B"


def test_toggle_ignored_in_single_select(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.toggle_choice_current()
    assert ui._choice_selected == set()


def test_toggle_ignored_on_free_text_row(ui):
    ui._begin_choice(_spec([{"label": "A"}], multi=True))
    ui.move_choice_cursor(99)  # free-text row
    ui.toggle_choice_current()
    assert ui._choice_selected == set()


def test_free_text_row_confirm_closes_widget_without_resolving(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(99)  # free-text row
    assert ui.confirm_choice() is True
    # Future still pending: the next input-field Enter resolves it.
    assert ui.resolved is None
    assert ui.has_active_choice() is False
    assert any("Type your answer" in e for e in ui.echoes)


def test_free_text_after_multi_select_combines_with_typed(ui):
    """Multi-select + 'type my own' → checked options plus the typed answer."""
    ui._begin_choice(
        _spec([{"label": "A"}, {"label": "B"}, {"label": "C"}], multi=True)
    )
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(2)
    ui.toggle_choice_current()  # C
    ui.move_choice_cursor(99)  # to free-text row
    ui.confirm_choice()
    assert ui.has_active_choice() is False
    # Typed answer arrives via the input field's Enter.
    ui._handle_confirmation(_event("custom thing"))
    assert ui.resolved == "A, C, custom thing"


def test_free_text_single_select_returns_only_typed(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    ui.move_choice_cursor(99)  # free-text row
    ui.confirm_choice()
    ui._handle_confirmation(_event("my answer"))
    assert ui.resolved == "my answer"


def test_free_text_with_empty_typed_keeps_checked_options(ui):
    ui._begin_choice(_spec([{"label": "A"}, {"label": "B"}], multi=True))
    ui.toggle_choice_current()  # A
    ui.move_choice_cursor(99)  # free-text row
    ui.confirm_choice()
    ui._handle_confirmation(_event("   "))
    assert ui.resolved == "A"


def test_handle_confirmation_falls_through_without_pending_free_text(ui):
    """With no free-text pending, it delegates to the plain confirmation path."""
    ui._handle_confirmation(_event("plain answer"))
    assert ui.resolved == "plain answer"


def test_confirm_noop_when_no_active_choice(ui):
    assert ui.confirm_choice() is False


def test_operations_noop_when_no_active_choice(ui):
    # Should not raise when nothing is active.
    ui.move_choice_cursor(1)
    ui.toggle_choice_current()
    assert ui.has_active_choice() is False
