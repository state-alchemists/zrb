"""Queued-message echo tracking and redraw (`UIMessageEditing`).

Where a submitted echo landed in the output buffer (`track_echo_span`) and how
it is spliced back after an edit or a paste merge (`redraw_echo`). The Up/Down
recall handlers around them are driven through the keybinding tests.

`MockEditingUI` is the same shape as the output tests' stand-in, trimmed to
what the echo path reaches: it composes the real `UIOutput` and the real
`UIMessageEditing`, over a buffer that really stores text, so the offset
bookkeeping is exercised rather than mocked.
"""

from unittest.mock import MagicMock, patch

from zrb.llm.ui.base.confirmation_state import BaseUIConfirmationState
from zrb.llm.ui.base.message_queue import EchoSpan, QueuedMessage
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput


class MockEditingUI:
    """Stand-in UI composing the real `UIOutput` and `UIMessageEditing`.

    Holds the state both parts reach via `self._ui` (normally supplied by the
    default `UI`) and forwards everything else to whichever part defines it.
    """

    def __init__(self):
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._output_field.buffer = _RecordingBuffer(self._output_field)
        self._input_field = MagicMock()
        self.confirmation = BaseUIConfirmationState()
        self.rendered_blocks = []
        self.rendered_width = None
        self.pending_invalidate = False
        self.invalidate_task = None
        self.markdown_theme = None
        self._is_thinking = False
        self._current_confirmation = None
        self._output = UIOutput(self)
        self._message_editing = UIMessageEditing(self)

    @property
    def output_field(self):
        return self._output_field

    @property
    def input_field(self):
        return self._input_field

    @property
    def is_thinking(self):
        return self._is_thinking

    @property
    def current_confirmation(self):
        return self._current_confirmation

    def invalidate_ui(self):
        pass

    def execute_hook(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        message_editing = self.__dict__.get("_message_editing")
        if message_editing is not None and hasattr(message_editing, name):
            return getattr(message_editing, name)
        output = self.__dict__.get("_output")
        if output is None:
            raise AttributeError(name)
        return getattr(output, name)


class _RecordingBuffer:
    def __init__(self, output_field):
        self._output_field = output_field
        self.cursor_position = 0

    @property
    def text(self):
        return self._output_field.text

    def set_document(self, document, bypass_readonly=False):
        self._output_field.text = document.text
        self.cursor_position = document.cursor_position


def make_entry(text="original", marker="💬", ts="10:00"):
    async def run():
        pass

    entry = QueuedMessage(text=text, attachments=[], kind="message", run=run)
    entry.echo_marker = marker
    entry.echo_timestamp = ts
    return entry


def test_track_echo_span_records_when_echo_lands():
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo
    entry = make_entry()

    ui.track_echo_span(entry, echo)

    span = entry.echo_spans[ui]
    assert (span.start, span.end) == (len("head"), len("head") + len(echo))
    assert span.text == echo


def test_track_echo_span_records_with_writers_trailing_newline():
    # The writer's default separator appends a newline after the echo, so a
    # bare `endswith` span would never record and pastes would fragment.
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo + "\n"
    entry = make_entry()

    ui.track_echo_span(entry, echo)

    span = entry.echo_spans[ui]
    assert (span.start, span.end) == (len("head"), len("head") + len(echo))
    assert ui.output_text[span.start : span.end] == echo


def test_track_echo_span_skips_when_echo_buffered():
    # A pending confirmation diverted the echo from the buffer — nothing to
    # splice later, so the span must not be recorded.
    ui = MockEditingUI()
    ui.output_field.text = "confirmation prompt"
    entry = make_entry()

    ui.track_echo_span(entry, "\n💬 10:00 >> original\n")

    assert entry.echo_spans == {}


def test_redraw_echo_splices_edited_line():
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo + "tail"
    entry = make_entry()
    start = len("head")
    entry.echo_spans[ui] = EchoSpan(start, start + len(echo), echo)

    entry.text = "edited text"
    ui.redraw_echo(entry)

    assert ui.output_text == "head" + "\n💬 10:00 >> edited text\n" + "tail"
    span = entry.echo_spans[ui]
    assert span.start == start
    assert span.end == start + len("\n💬 10:00 >> edited text\n")
    assert span.text == "\n💬 10:00 >> edited text\n"


def test_redraw_echo_drops_span_that_no_longer_holds_the_echo():
    # A terminal resize shifted the transcript without updating the span;
    # splicing at the stale span would corrupt the output, so it is dropped.
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "rewrapped long block now" + echo
    entry = make_entry()
    stale_start = len("old short block")  # span recorded when the block was short
    entry.echo_spans[ui] = EchoSpan(stale_start, stale_start + len(echo), echo)

    entry.text = "edited text"
    ui.redraw_echo(entry)

    assert ui.output_text == "rewrapped long block now" + echo  # untouched
    assert entry.echo_spans == {}


def test_redraw_echo_uses_entry_marker_and_timestamp():
    ui = MockEditingUI()
    echo = "\n⏳ 10:00 >> original\n"
    ui.output_field.text = echo
    entry = make_entry()
    entry.echo_marker = "⏳"
    entry.echo_spans[ui] = EchoSpan(0, len(echo), echo)

    entry.text = "edited"
    ui.redraw_echo(entry)

    assert ui.output_text == "\n⏳ 10:00 >> edited\n"


def test_redraw_echo_drops_stale_span():
    ui = MockEditingUI()
    entry = make_entry()
    entry.echo_spans[ui] = EchoSpan(0, 100, "")  # buffer was rewritten since
    ui.output_field.text = "short"

    ui.redraw_echo(entry)

    assert entry.echo_spans == {}


def test_redraw_echo_is_a_noop_without_span():
    # No span recorded (echo was confirmation-buffered) — nothing to splice.
    ui = MockEditingUI()
    entry = make_entry()
    entry.echo_spans = {}
    ui.output_field.text = "head"

    ui.redraw_echo(entry)

    assert ui.output_text == "head"
    assert entry.echo_spans == {}


def test_redraw_echo_renders_a_message_whose_text_is_markdown():
    # A merge whose combined text turned Markdown renders the WHOLE queued
    # message into the echo, and re-tracks the span so a later edit can still
    # rewrite the display.
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> hello\n"
    ui.output_field.text = "head" + echo + "tail"
    entry = make_entry(text="hello\n- item")
    start = len("head")
    entry.echo_spans[ui] = EchoSpan(start, start + len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        return_value="HELLO\n- ITEM",
    ) as mock_render:
        rewritten = ui.redraw_echo(entry)

    # The full combined message — not `- item` alone — is what got rendered.
    assert mock_render.call_args.args[0] == "hello\n- item"
    assert ui.output_text == "head" + "\n💬 10:00 >> HELLO\n- ITEM\n" + "tail"
    span = entry.echo_spans[ui]
    assert span.start == start
    assert span.end == start + len("\n💬 10:00 >> HELLO\n- ITEM\n")
    assert span.text == "\n💬 10:00 >> HELLO\n- ITEM\n"
    assert rewritten == "\n💬 10:00 >> HELLO\n- ITEM\n"


def test_redraw_echo_renders_markdown_an_edit_introduced():
    """Editing a queued message into Markdown renders it — the redraw decides
    from the entry's current text, so an edit and a paste merge draw the same
    thing. Deciding once at merge time instead left a later edit replacing the
    rendered block with raw text."""
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> plain line\n"
    ui.output_field.text = echo
    entry = make_entry(text="plain line")
    entry.echo_spans[ui] = EchoSpan(0, len(echo), echo)

    entry.text = "# title"
    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        return_value="TITLE",
    ) as mock_render:
        ui.redraw_echo(entry)

    assert mock_render.call_args.args[0] == "# title"
    assert ui.output_text == "\n💬 10:00 >> TITLE\n"


def test_redraw_echo_returns_to_raw_text_when_an_edit_drops_the_markdown():
    """The reverse direction: a rendered echo edited back to plain text is
    drawn verbatim, and its tracked block re-renders to itself so a later
    resize cannot splice stale Markdown back over it."""
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> hello\n"
    ui.output_field.text = echo
    entry = make_entry(text="hello\n- item")
    entry.echo_spans[ui] = EchoSpan(0, len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown", return_value="HELLO\n- ITEM"
    ):
        ui.redraw_echo(entry)
    entry.text = "just words"
    ui.redraw_echo(entry)

    assert ui.output_text == "\n💬 10:00 >> just words\n"
    # One block, still covering only the body, and re-rendering to itself.
    assert len(ui.rendered_blocks) == 1
    block = ui.rendered_blocks[0]
    assert ui.output_text[block[0] : block[1]] == "just words"
    assert block[3](block[2], 40) == "just words"


def test_redraw_echo_tracks_the_rendered_body_for_rewrap():
    """A redrawn Markdown echo is a tracked block, so a terminal resize
    re-renders it at the new width instead of leaving it wrapped for the old
    one. It is tracked over the body alone — the header and the separator
    newline are width-independent and must survive the re-render."""
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> hello\n"
    ui.output_field.text = "head" + echo
    entry = make_entry(text="hello\n- item")
    start = len("head")
    entry.echo_spans[ui] = EchoSpan(start, start + len(echo), echo)

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 60
        with patch(
            "zrb.llm.ui.default.output.render_markdown",
            side_effect=lambda text, width=None, theme=None: f"[{width}]{text}",
        ):
            ui.redraw_echo(entry)
            assert "head\n💬 10:00 >> [56]hello\n- item\n" == ui.output_text
            block = ui.rendered_blocks[0]
            assert ui.output_text[block[0] : block[1]] == "[56]hello\n- item"

            mock_size.return_value.columns = 100
            ui.rewrap_output()

    assert ui.output_text == "head\n💬 10:00 >> [96]hello\n- item\n"


def test_redraw_echo_replaces_its_own_block_instead_of_stacking_them():
    """Each redraw re-records the block at the same offset. Appending one per
    redraw would leave `rendered_blocks` holding overlapping stale spans, and
    `rewrap_output` walks that list accumulating a shift."""
    ui = MockEditingUI()
    echo = "\n💬 10:00 >> hello\n"
    ui.output_field.text = echo
    entry = make_entry(text="hello\n- item")
    entry.echo_spans[ui] = EchoSpan(0, len(echo), echo)

    with patch(
        "zrb.llm.ui.default.output.render_markdown",
        side_effect=lambda text, width=None, theme=None: text.upper(),
    ):
        ui.redraw_echo(entry)
        entry.text = "hello\n- item\n- more"
        ui.redraw_echo(entry)

    assert len(ui.rendered_blocks) == 1
    assert ui.output_text == "\n💬 10:00 >> HELLO\n- ITEM\n- MORE\n"
