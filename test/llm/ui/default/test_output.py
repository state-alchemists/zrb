from unittest.mock import MagicMock, patch

from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput
from zrb.util.cli.help_panel import HelpPanel


class MockOutputUI(UIOutput):
    def __init__(self):
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._input_field = MagicMock()
        self._conversation_session_name = "test"
        self._cwd = "/test"
        self.yolo = False
        self._model = "test-model"
        self._git_info = "main"
        self._assistant_name = "Zrb"
        self.is_thinking = False
        self.current_confirmation = None

    def invalidate_ui(self):
        pass

    def execute_hook(self, *args, **kwargs):
        pass


def test_output_text_property():
    ui = MockOutputUI()
    ui._output_field.text = "current"
    assert ui.output_text == "current"


def test_append_to_output_basic():
    ui = MockOutputUI()
    ui._output_field.text = "line1\n"
    ui._output_field.buffer.cursor_position = 0

    with patch.object(ui, "_schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("line2")
            mock_doc.assert_called()
            assert mock_doc.call_args[0][0] == "line1\nline2\n"


def test_append_to_output_carriage_return():
    ui = MockOutputUI()
    ui._output_field.text = "line1\nStatus: old"
    ui._output_field.buffer.cursor_position = 0

    with patch.object(ui, "_schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("\rStatus: new", end="")
            assert mock_doc.call_args[0][0] == "line1\nStatus: new"


def test_get_info_bar_text_logic():
    ui = MockOutputUI()
    res = ui.get_info_bar_text()
    assert res is not None


def test_get_info_bar_text_accepts_style_strings_with_spaces():
    """Regression: INFO_* knobs hold full prompt_toolkit style strings (e.g.
    "ansired bold"). The old HTML-attribute path raised
    '"fg" attribute contains a space.' on any multi-token value; the fragment-based
    bar must render such values without error."""
    from prompt_toolkit.formatted_text import to_formatted_text

    ui = MockOutputUI()
    ui.yolo = True

    with patch("zrb.llm.ui.default.output.CFG") as mock_cfg:
        mock_cfg.LLM_UI_STYLE_INFO_YOLO_ON = "ansired bold"
        mock_cfg.LLM_UI_STYLE_INFO_YOLO_PARTIAL = "ansiyellow bold"
        mock_cfg.LLM_UI_STYLE_INFO_YOLO_OFF = "ansigreen"
        mock_cfg.LLM_UI_STYLE_INFO_PLAN_ON = "ansiblue bold"
        mock_cfg.LLM_UI_STYLE_INFO_PLAN_OFF = "ansigreen"

        res = ui.get_info_bar_text()
        # Must not raise (the old HTML path crashed here on the space).
        fragments = to_formatted_text(res)

    styles = [style for style, _text, *_ in fragments]
    assert any("ansired bold" in s for s in styles)


def test_get_info_bar_text_partial_yolo_lists_tools():
    """Selective YOLO renders the tool list with the PARTIAL style."""
    from prompt_toolkit.formatted_text import to_formatted_text

    ui = MockOutputUI()
    ui.yolo = frozenset({"Read", "Write"})

    res = ui.get_info_bar_text()
    text = "".join(t for _style, t, *_ in to_formatted_text(res))
    assert "[Read,Write]" in text


def test_output_field_width_logic():
    ui = MockOutputUI()
    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        # Standard width
        mock_size.return_value.columns = 80
        assert ui.output_field_width == 76

        # Narrow width (should return None)
        mock_size.return_value.columns = 10
        assert ui.output_field_width is None

        # Error case (should return None)
        mock_size.side_effect = Exception("error")
        assert ui.output_field_width is None


def test_get_status_bar_text_logic():
    ui = MockOutputUI()
    res = ui.get_status_bar_text()
    assert "Ready" in res[0][1]

    ui.is_thinking = True
    res2 = ui.get_status_bar_text()
    assert "working" in res2[0][1]

    ui.is_thinking = False
    ui.current_confirmation = "mock_confirmation"
    res3 = ui.get_status_bar_text()
    assert "confirmation" in res3[0][1]


class MockMarkdownUI(MockOutputUI):
    """MockOutputUI with a buffer that really stores text, so the offset-based
    re-wrap can be driven through the public methods."""

    def __init__(self):
        super().__init__()
        self._rendered_blocks = []
        self._rendered_width = None
        self._markdown_theme = None
        self._output_field.buffer = _RecordingBuffer(self._output_field)


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


def test_append_markdown_rewraps_on_resize():
    """Rich hard-wraps at render time, so a width change must re-render the
    tracked markdown while leaving the surrounding plain text untouched."""
    ui = MockMarkdownUI()
    paragraph = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo"

    with patch.object(ui, "_schedule_invalidate"):
        with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 34
            ui.append_to_output("before")
            ui.append_markdown(paragraph)
            ui.append_to_output("after")
            narrow = ui.output_text

            mock_size.return_value.columns = 200
            ui.rewrap_output()
            wide = ui.output_text

    assert narrow.startswith("before\n") and narrow.endswith("after\n")
    assert wide.startswith("before\n") and wide.endswith("after\n")
    assert "kilo" in wide
    # Fewer line breaks once the terminal got wider.
    assert wide.count("\n") < narrow.count("\n")


def test_rewrap_output_is_a_noop_at_unchanged_width():
    ui = MockMarkdownUI()

    with patch.object(ui, "_schedule_invalidate"):
        with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 60
            ui.append_markdown("hello **world**")
            ui.rewrap_output()
            first = ui.output_text
            ui.rewrap_output()

            assert ui.output_text == first


def test_print_help_panel_rerenders_on_resize_without_truncating():
    """The help panel is tracked like markdown: a resize re-lays it out, and
    no width ever clips a command description."""
    ui = MockMarkdownUI()
    long_description = (
        "Set model (usage: /model <model-name>, /model small <model-name>)"
    )
    ui.get_help_panel = lambda art="", header="": HelpPanel(
        commands=[("/model", long_description)],
        shortcuts=[("Ctrl+J", "Insert a newline (multi-line input)")],
        art="<art-line-1>\n<art-line-2>",
    )

    with patch.object(ui, "_schedule_invalidate"):
        with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
            mock_size.return_value.columns = 60
            ui.print_help()
            narrow = ui.output_text

            mock_size.return_value.columns = 160
            ui.rewrap_output()
            wide = ui.output_text

    for rendered in (narrow, wide):
        assert "<art-line-1>" in rendered and "<art-line-2>" in rendered
        assert "..." not in rendered
        for word in long_description.split():
            assert word in rendered
    # The narrow render had to wrap the description onto more lines.
    assert narrow.count("\n") > wide.count("\n")


def test_get_status_bar_text_shows_queued_messages():
    ui = MockOutputUI()
    ui.is_thinking = True
    ui.queued_message_count = 2

    text = "".join(fragment[1] for fragment in ui.get_status_bar_text())

    assert "2 queued" in text


def test_output_field_width_prefers_the_running_application():
    """GlobalStreamCapture points fds 1/2 at a pipe, so get_terminal_size can
    disagree with what prompt_toolkit is painting; the app's own size wins."""
    ui = MockOutputUI()
    ui._application = MagicMock()
    ui._application.output.get_size.return_value = MagicMock(columns=120)

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 80
        assert ui.output_field_width == 116

        # Unusable app size (e.g. console not detected) falls back.
        ui._application.output.get_size.side_effect = Exception("no console")
        assert ui.output_field_width == 76


# ── Queued-message echo splicing (UIMessageEditing + UIOutput) ──────────


class MockEditingOutputUI(MockMarkdownUI, UIMessageEditing):
    """MockMarkdownUI plus the queued-edit echo tracking/redraw methods."""

    def __init__(self):
        super().__init__()
        self._queued_edit_entry = None
        self._queued_edit_draft = ""
        self._pending_invalidate = False


def make_entry(text="original", marker="💬", ts="10:00"):
    async def run():
        pass

    entry = QueuedMessage(text=text, attachments=[], kind="message", run=run)
    entry.echo_marker = marker
    entry.echo_timestamp = ts
    return entry


def test_track_echo_span_records_when_echo_lands():
    ui = MockEditingOutputUI()
    echo = "\n💬 10:00 >> original\n"
    ui._output_field.text = "head" + echo
    entry = make_entry()

    ui._track_echo_span(entry, echo)

    assert entry.echo_span == (len("head"), len("head") + len(echo))


def test_track_echo_span_skips_when_echo_buffered():
    # A pending confirmation diverted the echo away from the output buffer, so
    # there is nothing to splice later — the span must not be recorded.
    ui = MockEditingOutputUI()
    ui._output_field.text = "confirmation prompt"
    entry = make_entry()

    ui._track_echo_span(entry, "\n💬 10:00 >> original\n")

    assert entry.echo_span is None


def test_redraw_echo_splices_edited_line():
    ui = MockEditingOutputUI()
    echo = "\n💬 10:00 >> original\n"
    ui._output_field.text = "head" + echo + "tail"
    entry = make_entry()
    start = len("head")
    entry.echo_span = (start, start + len(echo))

    entry.text = "edited text"
    ui._redraw_echo(entry)

    assert ui.output_text == "head" + "\n💬 10:00 >> edited text\n" + "tail"
    assert entry.echo_span == (start, start + len("\n💬 10:00 >> edited text\n"))


def test_redraw_echo_uses_entry_marker_and_timestamp():
    ui = MockEditingOutputUI()
    echo = "\n⏳ 10:00 >> original\n"
    ui._output_field.text = echo
    entry = make_entry()
    entry.echo_marker = "⏳"
    entry.echo_span = (0, len(echo))

    entry.text = "edited"
    ui._redraw_echo(entry)

    assert ui.output_text == "\n⏳ 10:00 >> edited\n"


def test_redraw_echo_drops_stale_span():
    ui = MockEditingOutputUI()
    entry = make_entry()
    entry.echo_span = (0, 100)  # buffer was rewritten since (e.g. rewind)
    ui._output_field.text = "short"

    ui._redraw_echo(entry)

    assert entry.echo_span is None


def test_redraw_echo_is_a_noop_without_span():
    # No span recorded (echo was confirmation-buffered) — nothing to splice.
    ui = MockEditingOutputUI()
    entry = make_entry()
    entry.echo_span = None
    ui._output_field.text = "head"

    ui._redraw_echo(entry)

    assert ui.output_text == "head"
    assert entry.echo_span is None


def test_replace_output_span_shifts_tracked_blocks_after_span():
    """Splicing a shorter echo must shift rendered-block offsets so a later
    re-wrap still splices at the right position."""
    ui = MockMarkdownUI()
    echo = "\n💬 10:00 >> original\n"
    ui._output_field.text = "head" + echo + "markdown"
    block_start = len("head" + echo)
    ui._rendered_blocks.append(
        [block_start, block_start + len("markdown"), "source", lambda s, w: "markdown"]
    )

    with patch.object(ui, "_schedule_invalidate"):
        replaced = ui.replace_output_span(
            len("head"), len("head") + len(echo), "\n💬 10:00 >> edited\n"
        )

    assert replaced is True
    assert ui.output_text == "head" + "\n💬 10:00 >> edited\n" + "markdown"
    # "original" (8 chars) → "edited" (6): -2 shift applied to the block.
    assert ui._rendered_blocks[0][0] == block_start - 2
    assert ui._rendered_blocks[0][1] == block_start - 2 + len("markdown")


def test_replace_output_span_refuses_stale_span():
    ui = MockMarkdownUI()
    ui._output_field.text = "short"

    with patch.object(ui, "_schedule_invalidate"):
        assert ui.replace_output_span(0, 100, "x") is False
