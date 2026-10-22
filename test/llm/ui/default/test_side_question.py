"""The `/btw` panel: one question, one answer, closed by Esc.

The panel owns only its own state and text; where it sits on screen is the
`Float` the default `UI` builds around `side_question_window`.
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.side_question import UISideQuestion


class _FakeUI:
    """The bits of the default `UI` the panel reads."""

    def __init__(self, is_waiting_for_answer: bool = False):
        self.input_field = MagicMock(name="input_field")
        self.output_field_width = 80
        self.is_waiting_for_answer = is_waiting_for_answer

    def render_markdown(self, text: str, width: int | None = None) -> str:
        return f"<md width={width}>{text}</md>"


@pytest.fixture
def part() -> UISideQuestion:
    panel = UISideQuestion(_FakeUI())
    panel.init_side_question_state()
    return panel


def _text(part: UISideQuestion) -> str:
    window = part.side_question_window
    assert window is not None
    return window.buffer.text


def test_nothing_is_shown_before_a_question_is_asked(part):
    assert part.is_active is False
    assert _text(part) == ""


def test_begin_shows_the_question_and_says_the_answer_is_coming(part):
    part.begin("why is the sky blue?")

    assert part.is_active is True
    assert _text(part).startswith("💭 why is the sky blue?")
    assert "thinking" in _text(part)


def test_end_renders_the_answer_at_the_pane_width_and_keeps_the_question(part):
    part.begin("why?")

    part.end("because of Rayleigh scattering")

    assert _text(part).startswith("💭 why?")
    assert "<md width=80>because of Rayleigh scattering</md>" in _text(part)


def test_fail_says_why_the_question_could_not_be_answered(part):
    part.begin("why?")

    part.fail("RuntimeError: provider down")

    assert "❌ RuntimeError: provider down" in _text(part)


def test_dismiss_closes_the_panel_and_gives_the_input_its_focus_back():
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.dismiss()

    assert part.is_active is False
    assert _text(part) == ""
    focus.assert_called_once_with(ui.input_field, "Input-field")


def test_begin_does_not_take_focus_from_a_pending_prompt():
    """`/btw` runs ahead of a pending approval; the panel must not steal the
    focus from the answer the turn is blocked on."""
    panel = UISideQuestion(_FakeUI(is_waiting_for_answer=True))
    panel.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        panel.begin("why?")

    focus.assert_not_called()
    assert panel.is_active is True


def test_a_long_answer_scrolls_inside_a_fixed_height(part):
    from zrb.llm.ui.default.side_question import PANEL_HEIGHT

    part.begin("why?")
    part.end("\n".join(f"line {i}" for i in range(200)))

    window = part.side_question_window
    assert window is not None
    # A `TextArea` forwards its height to the `Window` it renders through.
    assert window.window.height == PANEL_HEIGHT


def test_an_answer_for_a_replaced_question_is_dropped(part):
    """A slower first `/btw` must not overwrite the panel a newer one opened."""
    first = part.begin("first question")
    part.begin("second question")

    part.end("the first answer", first)

    assert _text(part).startswith("💭 second question")
    assert "the first answer" not in _text(part)
    assert "thinking" in _text(part)


def test_a_failure_for_a_replaced_question_is_dropped(part):
    first = part.begin("first question")
    part.begin("second question")

    part.fail("RuntimeError: provider down", first)

    assert "❌" not in _text(part)
    assert _text(part).startswith("💭 second question")


def test_the_current_questions_answer_is_shown(part):
    request = part.begin("why?")

    part.end("because", request)

    assert "<md width=80>because</md>" in _text(part)


def test_cancelling_an_earlier_question_leaves_the_newer_panel_open(part):
    first = part.begin("first question")
    part.begin("second question")

    part.cancel(first)

    assert part.is_active is True
    assert _text(part).startswith("💭 second question")


def test_cancelling_the_current_question_closes_the_panel(part):
    request = part.begin("why?")

    part.cancel(request)

    assert part.is_active is False
    assert _text(part) == ""


def test_an_answer_arriving_after_esc_is_dropped(part):
    request = part.begin("why?")
    part.dismiss()

    part.end("an answer nobody is waiting for", request)

    assert part.is_active is False
    assert _text(part) == ""
