"""The question's context in the choice panel: shown, capped, and echoed.

The panel used to show the question alone, so answering meant scrolling back to
the conversation. The context is rendered above the question, the panel grows
with it, and past a share of the terminal height it is ellipsized rather than
allowed to push the options off screen. Scrollback keeps the long form.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.default import selection as selection_module
from zrb.util.cli.terminal import TerminalSize


def _spec(options, multi=False, index=1, total=1):
    return {
        "question": "Which DB?",
        "options": options,
        "multi_select": multi,
        "header": "DB",
        "index": index,
        "total": total,
    }


def _event(text=""):
    event = MagicMock()
    event.current_buffer.text = text
    return event


def _rendered(ui) -> str:
    return "".join(frag[1] for frag in ui.get_choice_text())


def _painted_line_count(ui) -> int:
    return _rendered(ui).count("\n")


def _context_lines(ui) -> list[str]:
    """The context's painted lines, trailing newlines and padding stripped."""
    return [
        frag[1].strip()
        for frag in ui.get_choice_text()
        if frag[0] == "class:choice.context" and frag[1].strip()
    ]


@pytest.fixture
def terminal_rows(monkeypatch):
    """Pin the terminal height the choice panel measures itself against."""

    def _set(rows: int) -> None:
        monkeypatch.setattr(
            selection_module,
            "get_terminal_size",
            lambda *args, **kwargs: TerminalSize(columns=80, lines=rows),
        )

    return _set


def _long_context(sentences: int = 12) -> str:
    return " ".join(
        f"Sentence {i} explains one fact the answer depends on."
        for i in range(sentences)
    )


def test_context_renders_above_the_question_in_muted_style(ui):
    """The panel carries the facts needed to answer, so the user need not
    scroll back to the conversation to answer it."""
    spec = _spec([{"label": "A"}, {"label": "B"}])
    spec["context"] = "Read-heavy traffic, 2GB of data, no ops team."
    ui.begin_choice(spec)
    text = _rendered(ui)

    assert text.index("Read-heavy traffic") < text.index("Which DB?")
    assert "Read-heavy traffic, 2GB of data, no ops team." in text
    context_styles = [
        frag[0] for frag in ui.get_choice_text() if "Read-heavy traffic" in frag[1]
    ]
    assert context_styles == ["class:choice.context"]


def test_context_is_wrapped_to_the_panel_width(ui):
    spec = _spec([{"label": "A"}])
    spec["context"] = _long_context(4)
    ui.begin_choice(spec)

    context_frags = [
        frag[1]
        for frag in ui.get_choice_text()
        if frag[0] == "class:choice.context" and frag[1].strip()
    ]
    assert len(context_frags) > 1, "expected the context to wrap onto several lines"
    # Panel width is 80 here (the stand-in UI's default): one column of padding.
    assert all(len(line.rstrip("\n")) <= 80 for line in context_frags)


def test_short_context_grows_the_panel(ui, terminal_rows):
    """The panel is allowed to grow with the context — that is the point."""
    terminal_rows(40)
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    without_context = _painted_line_count(ui)

    spec = _spec([{"label": "A"}, {"label": "B"}])
    spec["context"] = "Two lines of facts.\nA second line."
    ui.begin_choice(spec)
    assert _painted_line_count(ui) > without_context


def test_long_context_is_truncated_and_the_options_stay_on_screen(ui, terminal_rows):
    terminal_rows(40)
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = _long_context()
    ui.begin_choice(spec)
    text = _rendered(ui)

    # 40 rows × 40% — the panel never paints more than that.
    assert _painted_line_count(ui) <= int(40 * selection_module.CHOICE_HEIGHT_SHARE)
    assert _context_lines(ui)[-1].endswith("…"), "a cut context must say so"
    # Options, the free-text row and the key hint all survive the truncation.
    assert "Postgres" in text and "SQLite" in text
    assert "Type my own answer" in text
    assert "↑/↓ move" in text


def test_a_context_that_fits_is_not_truncated(ui, terminal_rows):
    terminal_rows(60)
    spec = _spec([{"label": "A"}, {"label": "B"}])
    spec["context"] = "One short fact."
    ui.begin_choice(spec)
    assert _context_lines(ui) == ["One short fact."]


def test_no_room_for_context_still_shows_the_options(ui, terminal_rows):
    """On a tiny terminal the options win: the context is dropped, not clipped
    into the option rows."""
    terminal_rows(10)
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = _long_context()
    ui.begin_choice(spec)
    text = _rendered(ui)

    assert "Postgres" in text and "SQLite" in text
    assert "Sentence 0" not in text
    assert _context_lines(ui) == []


def test_context_absent_renders_nothing_extra(ui):
    ui.begin_choice(_spec([{"label": "A"}]))
    assert _context_lines(ui) == []


# --- scrollback echo --------------------------------------------------------


def test_echo_records_the_context(ui):
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = "Read-heavy traffic.\nNo ops team."
    ui.begin_choice(spec)
    ui.confirm_choice()

    joined = "".join(ui.echoes)
    assert "❓ Which DB?" in joined
    assert "  Read-heavy traffic.\n  No ops team.\n" in joined
    assert "✔ Postgres" in joined


def test_echo_keeps_the_whole_context_the_panel_truncated(ui, terminal_rows):
    """The panel ellipsizes a long context; scrollback is where the rest lives."""
    terminal_rows(40)
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = _long_context()
    ui.begin_choice(spec)
    ui.confirm_choice()

    tail = "Sentence 11"
    assert tail not in _rendered(ui)
    assert tail in "".join(ui.echoes)


def test_free_text_answer_echo_records_the_context(ui):
    spec = _spec([{"label": "A"}, {"label": "B"}])
    spec["context"] = "One fact."
    ui.begin_choice(spec)
    ui.move_choice_cursor(99)  # free-text row
    ui.confirm_choice()
    ui.handle_confirmation(_event("my answer"))

    joined = "".join(ui.echoes)
    assert "  One fact.\n" in joined
    assert "✔ my answer" in joined
