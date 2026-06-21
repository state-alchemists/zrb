from unittest.mock import MagicMock, patch

from zrb.llm.ui.default.output_mixin import OutputMixin


class MockOutputUI(OutputMixin):
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

    with patch("zrb.llm.ui.default.output_mixin.CFG") as mock_cfg:
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
    with patch("zrb.llm.ui.default.output_mixin.get_terminal_size") as mock_size:
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
