"""The `/btw` panel: one question, one answer, closed by Esc.

The panel owns only its own state and text; where it sits on screen is the
`Float` the default `UI` builds around `side_question_window`. The keys it
receives while it holds the focus are pinned in `test_side_question_keys.py`.
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
        self.insert_input_text = MagicMock(name="insert_input_text")

    def render_markdown(self, text: str, width: int | None = None) -> str:
        return f"<md width={width}>{text}</md>"


class _ReflowingFakeUI(_FakeUI):
    """A narrower width renders *more* output, the way real re-wrapping does
    for markdown whose line count grows as it narrows (e.g. a code block) —
    needed to reproduce a stale end-of-buffer cursor after a resize."""

    def render_markdown(self, text: str, width: int | None = None) -> str:
        wraps = max(1, 80 // (width or 80))
        return "\n".join([text] * wraps)


class _WordWrappingFakeUI(_FakeUI):
    """Wraps the answer every `width` characters, the way real markdown
    rendering reflows a long line onto more of them as it narrows — needed to
    show a mid-buffer cursor landing on the wrong line when a raw offset is
    carried over instead of a (line, column) pair."""

    def render_markdown(self, text: str, width: int | None = None) -> str:
        w = width or 80
        return "\n".join(text[i : i + w] for i in range(0, len(text), w))


@pytest.fixture(autouse=True)
def no_application():
    """A unit test runs without a prompt_toolkit application to move the focus
    in. The tests that care which widget it names patch the same seam again."""
    with patch("zrb.llm.ui.default.side_question.focus_widget"):
        yield


@pytest.fixture
def part() -> UISideQuestion:
    panel = UISideQuestion(_FakeUI())
    panel.init_side_question_state()
    return panel


def _window(part: UISideQuestion):
    window = part.side_question_window
    assert window is not None
    return window


def _text(part: UISideQuestion) -> str:
    return _window(part).buffer.text


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
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.begin("why?")
        focus.reset_mock()
        part.dismiss()

    assert part.is_active is False
    assert _text(part) == ""
    focus.assert_called_once_with(ui.input_field, "Input-field")


def test_begin_moves_the_focus_to_the_panel():
    """Every key the user presses then reaches the panel's own bindings, so
    Up/Down scroll the answer instead of recalling a message into the input."""
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.begin("why?")

    focus.assert_called_once_with(part.side_question_window, "Side-question")
    assert part.is_active is True


def test_a_pending_prompt_also_keeps_the_focus():
    """`/btw` is routed ahead of a pending approval, so the panel can open over
    one. That field is what the turn is blocked on and keeps the focus."""
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


def test_rewrap_re_renders_the_shown_answer_at_the_new_width():
    """A resize must not leave the answer wrapped for the old width."""
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("because of Rayleigh scattering")

    ui.output_field_width = 40
    part.rewrap()

    assert "<md width=40>because of Rayleigh scattering</md>" in _text(part)


def test_rewrap_does_nothing_when_the_width_is_unchanged():
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("because")
    before = _text(part)

    part.rewrap()

    assert _text(part) == before


def test_rewrap_does_nothing_while_the_panel_is_closed():
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("because")
    part.dismiss()

    ui.output_field_width = 40
    part.rewrap()

    assert _text(part) == ""


def test_rewrap_does_nothing_while_the_panel_shows_a_pending_or_failure_message():
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")

    ui.output_field_width = 40
    part.rewrap()
    assert "thinking" in _text(part)

    part.fail("boom")
    ui.output_field_width = 20
    part.rewrap()
    assert "❌ boom" in _text(part)


def test_rewrap_keeps_the_readers_scroll_position():
    """Unlike a fresh answer, a resize must not jump the reader back to the top."""
    ui = _FakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("because")
    window = part.side_question_window
    assert window is not None
    window.buffer.cursor_position = 3

    ui.output_field_width = 40
    part.rewrap()

    assert window.buffer.cursor_position == 3


def test_rewrap_keeps_a_reader_at_the_end_when_the_rewrap_grows_the_text():
    """A reader scrolled to the bottom (e.g. watching a long answer stream in)
    must stay at the bottom, even though re-wrapping narrower makes the
    rendered answer longer and the old cursor offset would land mid-buffer."""
    ui = _ReflowingFakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("short answer")
    window = part.side_question_window
    assert window is not None
    window.buffer.cursor_position = len(window.buffer.text)

    ui.output_field_width = 10
    part.rewrap()

    assert window.buffer.cursor_position == len(window.buffer.text)


def test_rewrap_keeps_a_mid_buffer_reader_on_the_same_line_index():
    """A resize that re-wraps the answer onto more lines must not let a
    mid-buffer cursor drift onto an unrelated line just because the raw
    character count before it changed: it should stay anchored to the same
    line index (and as much of its column as the new, shorter line has)
    instead of a stale offset landing on whatever now sits at that count."""
    ui = _WordWrappingFakeUI()
    part = UISideQuestion(ui)
    part.init_side_question_state()
    part.begin("why?")
    part.end("AAAAABBBBBCCCCCDDDDD")
    window = part.side_question_window
    assert window is not None
    old_lines = window.buffer.text.split("\n")
    assert old_lines[2] == "AAAAABBBBBCCCCCDDDDD"
    # Column 15 of that line: the start of the run of "D"s.
    window.buffer.cursor_position = len(old_lines[0]) + 1 + len(old_lines[1]) + 1 + 15

    ui.output_field_width = 10
    part.rewrap()

    new_text = window.buffer.text
    before_cursor = new_text[: window.buffer.cursor_position]
    new_lines = new_text.split("\n")
    assert new_lines[2] == "AAAAABBBBB"
    assert new_lines[3] == "CCCCCDDDDD"
    # Still on line index 2 — the reflow split that one line in two, so a raw
    # offset would have overshot onto line 3 ("CCCCCDDDDD") instead.
    assert before_cursor.count("\n") == 2
    assert before_cursor.endswith("AAAAABBBBB")


def test_show_puts_a_command_reply_in_the_panel_under_its_title(part):
    part.show("Usage", "  every recorded run\n\n  model  runs")

    assert part.is_active is True
    assert _text(part).startswith("  Usage")
    assert "every recorded run" in _text(part)
    assert "model  runs" in _text(part)


def test_a_shown_table_is_not_put_through_the_markdown_renderer(part):
    """`/usage` lays its columns out itself; re-wrapping would break them."""
    part.show("Usage", "  model    runs\n  gpt-4o      3")

    assert "<md" not in _text(part)
    assert "  gpt-4o      3" in _text(part)


def test_show_replaces_a_pending_side_question(part):
    part.begin("why is the sky blue?")
    token = part.begin("something else")

    part.show("Usage", "  every recorded run")

    assert "Usage" in _text(part)
    assert "thinking" not in _text(part)
    # The side answer still on its way no longer owns the panel.
    part.end("because of Rayleigh scattering", token)
    assert "Rayleigh" not in _text(part)


def test_show_keeps_the_focus_where_a_waiting_prompt_needs_it():
    ui = _FakeUI(is_waiting_for_answer=True)
    part = UISideQuestion(ui)
    part.init_side_question_state()
    with patch("zrb.llm.ui.default.side_question.focus_widget") as focus:
        part.show("Usage", "  every recorded run")

    focus.assert_not_called()
