from unittest.mock import MagicMock, patch

from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput


class MockOutputUI:
    """Stand-in UI composing the real `UIOutput`.

    Holds the state `UIOutput` reaches via `self._ui` (normally supplied by
    the default `UI`) and forwards everything else (public
    methods/properties) to the composed part.
    """

    def __init__(self):
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._input_field = MagicMock()
        self.conversation_session_name = "test"
        self.cwd = "/test"
        self.yolo = False
        self.model = "test-model"
        self.git_info = "main"
        self.assistant_name = "Zrb"
        self.confirmation_output_buffer = []
        self.rendered_blocks = []
        self.rendered_width = None
        self.pending_invalidate = False
        self.invalidate_task = None
        self.markdown_theme = None
        # This double IS the implementation site for these (mirroring the
        # real `UI`, which owns them directly — `UIOutput` just reads them
        # through the public properties below, one hop, no bounce back).
        self._is_thinking = False
        self._current_confirmation = None
        self._output = UIOutput(self)
        # Public aliases so tests can reach these without a leading-underscore
        # dotted expression (the private-test-access ratchet counts those).
        self.output_part = self._output

    @property
    def output_field(self):
        return self._output_field

    @property
    def input_field(self):
        return self._input_field

    @property
    def is_thinking(self):
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value):
        self._is_thinking = value

    @property
    def current_confirmation(self):
        return self._current_confirmation

    @current_confirmation.setter
    def current_confirmation(self, value):
        self._current_confirmation = value

    def invalidate_ui(self):
        pass

    def execute_hook(self, *args, **kwargs):
        pass

    def set_thinking(self, value):
        self._is_thinking = value

    def set_current_confirmation(self, value):
        self._current_confirmation = value

    def __getattr__(self, name):
        output = self.__dict__.get("_output")
        if output is None:
            raise AttributeError(name)
        return getattr(output, name)


class MockMarkdownUI(MockOutputUI):
    """MockOutputUI with a buffer that really stores text, so the offset-based
    re-wrap can be driven through the public methods."""

    def __init__(self):
        super().__init__()
        self.output_field.buffer = _RecordingBuffer(self.output_field)


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


class MockEditingOutputUI(MockMarkdownUI):
    """MockMarkdownUI plus the composed queued-edit echo tracking/redraw part."""

    def __init__(self):
        super().__init__()
        self._message_editing = UIMessageEditing(self)

    def __getattr__(self, name):
        message_editing = self.__dict__.get("_message_editing")
        if message_editing is not None and hasattr(message_editing, name):
            return getattr(message_editing, name)
        return super().__getattr__(name)


def make_entry(text="original", marker="💬", ts="10:00"):
    async def run():
        pass

    entry = QueuedMessage(text=text, attachments=[], kind="message", run=run)
    entry.echo_marker = marker
    entry.echo_timestamp = ts
    return entry


def test_get_status_bar_text_shows_queued_messages():
    ui = MockOutputUI()
    ui.set_thinking(True)
    ui.queued_message_count = 2

    text = "".join(fragment[1] for fragment in ui.get_status_bar_text())

    assert "2 queued" in text


def test_output_field_width_prefers_the_running_application():
    """GlobalStreamCapture points fds 1/2 at a pipe, so get_terminal_size can
    disagree with what prompt_toolkit is painting; the app's own size wins."""
    ui = MockOutputUI()
    ui.application = MagicMock()
    ui.application.output.get_size.return_value = MagicMock(columns=120)

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 80
        assert ui.output_field_width == 116

        # Unusable app size (e.g. console not detected) falls back.
        ui.application.output.get_size.side_effect = Exception("no console")
        assert ui.output_field_width == 76


def test_track_echo_span_records_when_echo_lands():
    ui = MockEditingOutputUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo
    entry = make_entry()

    ui.track_echo_span(entry, echo)

    assert entry.echo_span == (len("head"), len("head") + len(echo))
    assert entry.echo_text == echo


def test_track_echo_span_skips_when_echo_buffered():
    # A pending confirmation diverted the echo away from the output buffer, so
    # there is nothing to splice later — the span must not be recorded.
    ui = MockEditingOutputUI()
    ui.output_field.text = "confirmation prompt"
    entry = make_entry()

    ui.track_echo_span(entry, "\n💬 10:00 >> original\n")

    assert entry.echo_span is None


def test_redraw_echo_splices_edited_line():
    ui = MockEditingOutputUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo + "tail"
    entry = make_entry()
    start = len("head")
    entry.echo_span = (start, start + len(echo))
    entry.echo_text = echo

    entry.text = "edited text"
    ui.redraw_echo(entry)

    assert ui.output_text == "head" + "\n💬 10:00 >> edited text\n" + "tail"
    assert entry.echo_span == (start, start + len("\n💬 10:00 >> edited text\n"))
    assert entry.echo_text == "\n💬 10:00 >> edited text\n"


def test_redraw_echo_drops_span_that_no_longer_holds_the_echo():
    # A terminal resize re-wrapped a preceding markdown block and shifted the
    # transcript without updating the entry's span. The span is in-bounds but
    # stale, so splicing there would corrupt the output — the redraw must drop
    # it instead (the edit stays effective, the echo is just not rewritten).
    ui = MockEditingOutputUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "rewrapped long block now" + echo
    entry = make_entry()
    stale_start = len("old short block")  # span recorded when the block was short
    entry.echo_span = (stale_start, stale_start + len(echo))
    entry.echo_text = echo

    entry.text = "edited text"
    ui.redraw_echo(entry)

    assert ui.output_text == "rewrapped long block now" + echo  # untouched
    assert entry.echo_span is None


def test_redraw_echo_uses_entry_marker_and_timestamp():
    ui = MockEditingOutputUI()
    echo = "\n⏳ 10:00 >> original\n"
    ui.output_field.text = echo
    entry = make_entry()
    entry.echo_marker = "⏳"
    entry.echo_span = (0, len(echo))

    entry.text = "edited"
    ui.redraw_echo(entry)

    assert ui.output_text == "\n⏳ 10:00 >> edited\n"


def test_redraw_echo_drops_stale_span():
    ui = MockEditingOutputUI()
    entry = make_entry()
    entry.echo_span = (0, 100)  # buffer was rewritten since (e.g. rewind)
    ui.output_field.text = "short"

    ui.redraw_echo(entry)

    assert entry.echo_span is None


def test_redraw_echo_is_a_noop_without_span():
    # No span recorded (echo was confirmation-buffered) — nothing to splice.
    ui = MockEditingOutputUI()
    entry = make_entry()
    entry.echo_span = None
    ui.output_field.text = "head"

    ui.redraw_echo(entry)

    assert ui.output_text == "head"
    assert entry.echo_span is None


def test_replace_output_span_shifts_tracked_blocks_after_span():
    """Splicing a shorter echo must shift rendered-block offsets so a later
    re-wrap still splices at the right position."""
    ui = MockMarkdownUI()
    echo = "\n💬 10:00 >> original\n"
    ui.output_field.text = "head" + echo + "markdown"
    block_start = len("head" + echo)
    ui.rendered_blocks.append(
        [block_start, block_start + len("markdown"), "source", lambda s, w: "markdown"]
    )

    with patch.object(ui.output_part, "schedule_invalidate"):
        replaced = ui.replace_output_span(
            len("head"), len("head") + len(echo), "\n💬 10:00 >> edited\n"
        )

    assert replaced is True
    assert ui.output_text == "head" + "\n💬 10:00 >> edited\n" + "markdown"
    # "original" (8 chars) → "edited" (6): -2 shift applied to the block.
    assert ui.rendered_blocks[0][0] == block_start - 2
    assert ui.rendered_blocks[0][1] == block_start - 2 + len("markdown")


def test_replace_output_span_refuses_stale_span():
    ui = MockMarkdownUI()
    ui.output_field.text = "short"

    with patch.object(ui.output_part, "schedule_invalidate"):
        assert ui.replace_output_span(0, 100, "x") is False


def test_append_toggle_block_shows_collapsed_by_default():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_toggle_block("short", "much longer full text")

    assert "short" in ui.output_text
    assert "much longer full text" not in ui.output_text
    assert len(ui.rendered_blocks) == 1


def test_append_toggle_block_skips_tracking_when_variants_match():
    """No point tracking a block that has nothing to expand into."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_toggle_block("same", "same")

    assert ui.output_text == "same"
    assert ui.rendered_blocks == []


def test_toggle_collapsible_block_at_cursor_expands_then_collapses():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_toggle_block("short", "much longer full text")
        # Cursor follows the tail after the append (see _RecordingBuffer).
        toggled = ui.toggle_collapsible_block_at_cursor()
        expanded = ui.output_text
        toggled_again = ui.toggle_collapsible_block_at_cursor()
        collapsed_again = ui.output_text

    assert toggled is True
    assert "much longer full text" in expanded
    assert toggled_again is True
    assert "short" in collapsed_again
    assert "much longer full text" not in collapsed_again


def test_toggle_collapsible_block_at_cursor_returns_false_without_a_block():
    ui = MockMarkdownUI()
    ui.output_field.text = "plain text, no toggle blocks"
    ui.output_field.buffer.cursor_position = len(ui.output_field.text)

    assert ui.toggle_collapsible_block_at_cursor() is False


def test_toggle_collapsible_block_at_cursor_leaves_state_unchanged_on_stale_span():
    """If the recorded span no longer matches the buffer (stale), the toggle
    must not flip `expanded` or move the tracked offsets — otherwise a later
    toggle would work from corrupted bookkeeping instead of retrying cleanly."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_toggle_block("short", "much longer full text")

    block = ui.rendered_blocks[0]
    # Simulate a stale span (end past the end of the buffer).
    block[1] = len(ui.output_text) + 100
    ui.output_field.buffer.cursor_position = len(ui.output_text)

    result = ui.toggle_collapsible_block_at_cursor()

    assert result is False
    assert block[2].expanded is False
    assert "much longer full text" not in ui.output_text


def test_toggle_collapsible_block_at_cursor_shifts_later_blocks():
    """Toggling an earlier block must keep a later block's offsets correct —
    the same shift bookkeeping `replace_output_span` already guarantees for
    markdown/help-panel blocks."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_toggle_block("first", "first EXPANDED")
        ui.append_to_output("between")
        ui.append_toggle_block("second", "second EXPANDED")

        second_block = ui.rendered_blocks[1]
        expected_second_text = ui.output_text[second_block[0] : second_block[1]]

        # Point the cursor at the first block and toggle it.
        ui.output_field.buffer.cursor_position = 0
        toggled = ui.toggle_collapsible_block_at_cursor()

    assert toggled is True
    # The second block's recorded span must still slice out its own text
    # after the first block grew.
    assert ui.output_text[second_block[0] : second_block[1]] == expected_second_text


def test_rewrap_output_preserves_toggle_block_expanded_state():
    """A toggle block's renderer ignores width and reads `expanded`, so a
    resize-triggered rewrap must not revert an expanded block to collapsed."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 60
            ui.append_toggle_block("short", "much longer full text")
            ui.output_field.buffer.cursor_position = len(ui.output_field.text)
            ui.toggle_collapsible_block_at_cursor()
            assert "much longer full text" in ui.output_text

            mock_size.return_value.columns = 120
            ui.rewrap_output()

    assert "much longer full text" in ui.output_text


def test_mark_and_collapse_thinking_block_wraps_the_streamed_span():
    """Thinking streams live (unlike tool-call blocks, nothing is withheld);
    `collapse_thinking_block` retroactively wraps that already-printed span,
    using the caller-supplied `full` text (not re-read from the buffer —
    see the carriage-return regression test below for why)."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before ")
        ui.mark_thinking_block_start()
        ui.append_to_output("a long stream of live thinking text", end="")
        collapsed = ui.collapse_thinking_block(
            "🧠 Thought\n", "a long stream of live thinking text"
        )

    assert collapsed is True
    assert "a long stream of live thinking text" not in ui.output_text
    assert "🧠 Thought" in ui.output_text
    assert ui.output_text.startswith("before ")
    assert len(ui.rendered_blocks) == 1
    # The full original text is still one toggle away.
    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.output_field.buffer.cursor_position = len(ui.output_text)
        ui.toggle_collapsible_block_at_cursor()
    assert ui.output_text.startswith("before ")
    assert "a long stream of live thinking text" in ui.output_text


def test_collapse_thinking_block_ignores_buffer_mangled_by_carriage_return():
    """Regression: the passed-in `full` must win even when the *rendered*
    span no longer matches it (e.g. a stray \\r rewrote part of the live
    line) — this is the whole reason `full` is a parameter instead of being
    re-derived from the buffer."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.mark_thinking_block_start()
        # \r erases back to the start of the current line — simulates what
        # append_to_output's spinner handling does to any \r-bearing chunk.
        ui.append_to_output("first part\rsecond part", end="")
        # What's actually on screen right now is only "second part" — but a
        # caller that accumulated the untouched original still has it all.
        assert "first part" not in ui.output_text

        collapsed = ui.collapse_thinking_block("🧠 Thought\n", "first part second part")
        ui.output_field.buffer.cursor_position = len(ui.output_text)
        ui.toggle_collapsible_block_at_cursor()

    assert collapsed is True
    assert "first part" in ui.output_text
    assert "second part" in ui.output_text


def test_collapse_thinking_block_without_a_mark_is_a_noop():
    ui = MockMarkdownUI()
    ui.output_field.text = "no marked thinking block here"

    assert ui.collapse_thinking_block("🧠 Thought\n", "thinking text") is False
    assert ui.output_text == "no marked thinking block here"


def test_collapse_thinking_block_without_full_text_is_a_noop():
    """Nothing was actually accumulated — nothing to collapse into, so this
    must not create a broken (empty-when-expanded) block."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.mark_thinking_block_start()

    assert ui.collapse_thinking_block("🧠 Thought\n", "") is False
