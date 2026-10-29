"""The question's context: out of the panel, in the scrollback echo.

The panel floats over the transcript and takes the focus, so every row it paints
costs a row of the conversation the answer depends on. `#765` let it grow with
the context up to 40% of the terminal, which covered that conversation; the
panel hugs its question and its options again, and the whole context is recorded
in scrollback beside the answer instead. These tests hold that line: the panel's
height moves neither with the context nor with the terminal's rows.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.default import selection as selection_module
from zrb.util.cli import terminal as terminal_module
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


@pytest.fixture
def terminal_rows(monkeypatch):
    """Pin the terminal height, in every namespace the panel could read it.

    CI runs on 24 rows while a local terminal is taller, so a height-sensitive
    test passes here and fails there. The probe is pinned both at its source and
    on the module under test (`raising=False`: a panel that no longer imports it
    by name has no such attribute), and the tests below prove the height makes
    no difference either way.
    """

    def _set(rows: int) -> None:
        size = TerminalSize(columns=80, lines=rows)

        def probe(*args, **kwargs):
            return size

        monkeypatch.setattr(terminal_module, "get_terminal_size", probe)
        monkeypatch.setattr(selection_module, "get_terminal_size", probe, raising=False)

    return _set


def _long_context(sentences: int = 12) -> str:
    return " ".join(
        f"Sentence {i} explains one fact the answer depends on."
        for i in range(sentences)
    )


# --- the panel does not grow ------------------------------------------------


def test_the_panel_paints_no_context(ui, terminal_rows):
    """The panel carries the question and the options, not the context: the
    conversation behind it is what the user reads, and it stays visible."""
    terminal_rows(24)
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = "Read-heavy traffic, 2GB of data, no ops team."
    ui.begin_choice(spec)
    text = _rendered(ui)

    assert "Read-heavy traffic" not in text
    # Question, both options, the free-text row and the key hint all survive.
    assert "Which DB?" in text
    assert "Postgres" in text and "SQLite" in text
    assert "Type my own answer" in text
    assert "↑/↓ move" in text


def test_the_panel_height_does_not_move_with_the_context(ui, terminal_rows):
    """The regression: a long context grew the panel over the transcript."""
    terminal_rows(24)
    ui.begin_choice(_spec([{"label": "A"}, {"label": "B"}]))
    without_context = _painted_line_count(ui)

    spec = _spec([{"label": "A"}, {"label": "B"}])
    spec["context"] = _long_context(40)  # far past any share of a screen
    ui.begin_choice(spec)
    assert _painted_line_count(ui) == without_context


def test_the_panel_height_does_not_move_with_the_terminal_rows(ui, terminal_rows):
    """A 24-row CI terminal and a tall local one paint the same panel — the
    second half of the regression, and the half that passed locally."""
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = _long_context(40)

    terminal_rows(24)
    ui.begin_choice(spec)
    short_terminal = _rendered(ui)

    terminal_rows(60)
    ui.begin_choice(spec)
    assert _rendered(ui) == short_terminal


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


def test_echo_keeps_the_whole_context_the_panel_never_paints(ui, terminal_rows):
    """Scrollback is where the context lives, so nothing of it is lost."""
    terminal_rows(24)
    spec = _spec([{"label": "Postgres"}, {"label": "SQLite"}])
    spec["context"] = _long_context(40)
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
