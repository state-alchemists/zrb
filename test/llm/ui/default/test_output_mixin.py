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
