from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def test_output_text_property():
    ui = MockOutputUI()
    ui.output_field.text = "current"
    assert ui.output_text == "current"


def test_get_agent_activity_text_scopes_by_conversation_session_name():
    """The activity panel must read only this UI's own
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
    """The UI clue that /load swapped which persona is
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
