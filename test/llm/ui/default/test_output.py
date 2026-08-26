from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from zrb.llm.ui.base.message_queue import QueuedMessage
from zrb.llm.ui.default.message_editing import UIMessageEditing
from zrb.llm.ui.default.output import UIOutput
from zrb.util.cli.help_panel import HelpPanel


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


def test_output_text_property():
    ui = MockOutputUI()
    ui.output_field.text = "current"
    assert ui.output_text == "current"


def test_get_agent_activity_text_scopes_by_conversation_session_name():
    """Item 4, Phase D: the activity panel must read only this UI's own
    session's entries, not bleed in another session's running sub-agents."""
    from zrb.llm.agent.activity import AgentActivityRegistry

    ui = MockOutputUI()
    reg = AgentActivityRegistry()
    reg.start("a", "researcher", session_id="test")
    reg.start("b", "reviewer", session_id="other-session")

    with patch("zrb.llm.ui.default.output.agent_activity_registry", reg):
        frags = ui.get_agent_activity_text()

    rendered = "".join(text for _style, text in frags)
    assert "researcher" in rendered
    assert "reviewer" not in rendered


def test_append_to_output_basic():
    ui = MockOutputUI()
    ui.output_field.text = "line1\n"
    ui.output_field.buffer.cursor_position = 0

    with patch.object(ui.output_part, "schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("line2")
            mock_doc.assert_called()
            assert mock_doc.call_args[0][0] == "line1\nline2\n"


def test_append_to_output_carriage_return():
    ui = MockOutputUI()
    ui.output_field.text = "line1\nStatus: old"
    ui.output_field.buffer.cursor_position = 0

    with patch.object(ui.output_part, "schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("\rStatus: new", end="")
            assert mock_doc.call_args[0][0] == "line1\nStatus: new"


def test_get_info_bar_text_logic():
    ui = MockOutputUI()
    res = ui.get_info_bar_text()
    assert res is not None


def test_get_info_bar_text_omits_persona_when_driving_main_agent():
    """No sub-agent indicator when nothing was swapped (the common case)."""
    from prompt_toolkit.formatted_text import to_formatted_text

    ui = MockOutputUI()
    fragments = to_formatted_text(ui.get_info_bar_text())
    rendered = "".join(text for _style, text, *_ in fragments)
    assert "Sub-agent:" not in rendered


def test_get_info_bar_text_shows_active_subagent_persona():
    """Item 4, Phase D: the UI clue that /load swapped which persona is
    driving new messages."""
    from prompt_toolkit.formatted_text import to_formatted_text

    ui = MockOutputUI()
    ui.active_subagent_persona = "code-reviewer"
    fragments = to_formatted_text(ui.get_info_bar_text())
    rendered = "".join(text for _style, text, *_ in fragments)
    assert "Sub-agent:" in rendered
    assert "code-reviewer" in rendered


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


# ── Live sub-agent view (UIAgentPicker wiring) ───────────────────────────


def test_get_agent_activity_text_shows_picker_hint_when_agents_running():
    """The picker hint shows while at least one sub-agent is actively running."""
    from zrb.llm.agent.activity import AgentActivityRegistry

    ui = MockOutputUI()
    reg = AgentActivityRegistry()
    reg.start("a1", "researcher", task="research x", session_id="test")

    with patch("zrb.llm.ui.default.output.agent_activity_registry", reg):
        with patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            MagicMock(active=lambda session_id: []),
        ):
            frags = ui.get_agent_activity_text()

    rendered = "".join(text for _style, text in frags)
    assert "↓ talk to a sub-agent" in rendered
    assert "researcher" in rendered


def test_get_agent_activity_text_omits_picker_hint_without_live_sessions():
    ui = MockOutputUI()
    no_activity = MagicMock(active=lambda session_id: [])

    with patch("zrb.llm.ui.default.output.agent_activity_registry", no_activity):
        with patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            no_activity,
        ):
            frags = ui.get_agent_activity_text()

    assert frags == []


def test_get_agent_activity_text_shows_back_hint_while_viewing():
    """While a sub-agent's live view is showing, the activity panel stops
    listing running sub-agents (and the picker hint) and instead advertises
    that Left returns to the parent session."""
    ui = MockOutputUI()
    ui.viewing_agent_id = "a1"
    running = MagicMock(active=lambda session_id: [object()])
    live = MagicMock(active=lambda session_id: [object()])

    with patch("zrb.llm.ui.default.output.agent_activity_registry", running):
        with patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            live,
        ):
            frags = ui.get_agent_activity_text()

    rendered = "".join(text for _style, text in frags)
    assert "Press ← to return to the parent" in rendered
    assert "↓ talk to a sub-agent" not in rendered


def test_get_agent_activity_text_unchanged_when_not_viewing():
    """Outside the live view the panel still lists running sub-agents."""
    from zrb.llm.agent.activity import AgentActivityRegistry

    ui = MockOutputUI()
    reg = AgentActivityRegistry()
    reg.start("a", "researcher", task="research x", session_id="test")

    with patch("zrb.llm.ui.default.output.agent_activity_registry", reg):
        with patch(
            "zrb.llm.agent.subagent.live_session.live_subagent_session_registry",
            MagicMock(active=lambda session_id: []),
        ):
            frags = ui.get_agent_activity_text()

    rendered = "".join(text for _style, text in frags)
    assert "researcher" in rendered
    assert "Press ← to return to the parent" not in rendered


def test_get_info_bar_text_shows_viewing_sub_agent():
    from prompt_toolkit.formatted_text import to_formatted_text

    ui = MockOutputUI()
    ui.viewing_agent_id = "abc123"
    session = SimpleNamespace(agent_name="researcher")

    with patch(
        "zrb.llm.agent.subagent.live_session.live_subagent_session_registry"
    ) as mock_reg:
        mock_reg.get.return_value = session
        fragments = to_formatted_text(ui.get_info_bar_text())

    rendered = "".join(text for _style, text, *_ in fragments)
    assert "Sub-agent:" in rendered
    assert "researcher" in rendered
    assert "(viewing · ← back)" in rendered


def test_append_to_output_redirects_into_saved_main_output_while_viewing():
    # While the output pane shows a sub-agent's buffer, main-transcript appends
    # accumulate into the parked snapshot instead of corrupting the live view.
    ui = MockOutputUI()
    ui.output_field.text = "sub-agent live output"
    ui.viewing_agent_id = "abc123"
    ui.saved_main_output = "main transcript\n"

    with patch.object(ui.output_part, "schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("new main line")

    assert ui.saved_main_output == "main transcript\nnew main line\n"
    assert ui.output_text == "sub-agent live output"  # pane untouched
    mock_doc.assert_not_called()


def test_append_to_output_redirect_merges_carriage_returns():
    ui = MockOutputUI()
    ui.viewing_agent_id = "abc123"
    ui.saved_main_output = "Status: old"

    with patch.object(ui.output_part, "schedule_invalidate"):
        with patch("prompt_toolkit.document.Document") as mock_doc:
            ui.append_to_output("\rStatus: new", end="")

    assert ui.saved_main_output == "Status: new"
    mock_doc.assert_not_called()


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

    ui.set_thinking(True)
    res2 = ui.get_status_bar_text()
    assert "working" in res2[0][1]

    ui.set_thinking(False)
    ui.set_current_confirmation("mock_confirmation")
    res3 = ui.get_status_bar_text()
    assert "confirmation" in res3[0][1]


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


def test_append_markdown_rewraps_on_resize():
    """Rich hard-wraps at render time, so a width change must re-render the
    tracked markdown while leaving the surrounding plain text untouched."""
    ui = MockMarkdownUI()
    paragraph = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo"

    with patch.object(ui.output_part, "schedule_invalidate"):
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

    with patch.object(ui.output_part, "schedule_invalidate"):
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

    with patch.object(ui.output_part, "schedule_invalidate"):
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


# ── Queued-message echo splicing (UIMessageEditing + UIOutput) ──────────


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


def test_collapse_thinking_block_consumes_the_mark_once():
    """A second collapse call without a fresh mark must be a no-op, not
    re-collapse (or corrupt) whatever now sits at the old offset."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.mark_thinking_block_start()
        ui.append_to_output("thinking", end="")
        ui.collapse_thinking_block("🧠 Thought\n", "thinking")
        after_first = ui.output_text
        result = ui.collapse_thinking_block("🧠 Thought\n", "thinking")

    assert result is False
    assert ui.output_text == after_first
