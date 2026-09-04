import os

from zrb.config.config import Config


class TestLLMUIConfigSetters:
    """Test Config property setters by verifying they write to os.environ."""

    _original_env: dict[str, str] = {}

    def test_llm_assistant_name_setter(self, monkeypatch):
        config = Config()
        config.LLM_ASSISTANT_NAME = "assistant"
        assert os.environ["ZRB_LLM_ASSISTANT_NAME"] == "assistant"

    def test_llm_assistant_ascii_art_setter(self, monkeypatch):
        config = Config()
        config.LLM_ASSISTANT_ASCII_ART = "art"
        assert os.environ["ZRB_LLM_ASSISTANT_ASCII_ART"] == "art"

    def test_llm_assistant_jargon_setter(self, monkeypatch):
        config = Config()
        config.LLM_ASSISTANT_JARGON = "llm-jargon"
        assert os.environ["ZRB_LLM_ASSISTANT_JARGON"] == "llm-jargon"

    def test_llm_ui_style_title_bar_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_TITLE_BAR = "style1"
        assert os.environ["ZRB_LLM_UI_STYLE_TITLE_BAR"] == "style1"

    def test_llm_ui_style_info_bar_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_INFO_BAR = "style2"
        assert os.environ["ZRB_LLM_UI_STYLE_INFO_BAR"] == "style2"

    def test_llm_ui_style_frame_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_FRAME = "style3"
        assert os.environ["ZRB_LLM_UI_STYLE_FRAME"] == "style3"

    def test_llm_ui_style_frame_label_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_FRAME_LABEL = "style4"
        assert os.environ["ZRB_LLM_UI_STYLE_FRAME_LABEL"] == "style4"

    def test_llm_ui_style_input_frame_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_INPUT_FRAME = "style5"
        assert os.environ["ZRB_LLM_UI_STYLE_INPUT_FRAME"] == "style5"

    def test_llm_ui_style_thinking_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_THINKING = "style6"
        assert os.environ["ZRB_LLM_UI_STYLE_THINKING"] == "style6"

    def test_llm_ui_style_faint_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_FAINT = "style7"
        assert os.environ["ZRB_LLM_UI_STYLE_FAINT"] == "style7"

    def test_llm_ui_style_output_field_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_OUTPUT_FIELD = "style8"
        assert os.environ["ZRB_LLM_UI_STYLE_OUTPUT_FIELD"] == "style8"

    def test_llm_ui_style_input_field_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_INPUT_FIELD = "style9"
        assert os.environ["ZRB_LLM_UI_STYLE_INPUT_FIELD"] == "style9"

    def test_llm_ui_style_text_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_TEXT = "style10"
        assert os.environ["ZRB_LLM_UI_STYLE_TEXT"] == "style10"

    def test_llm_ui_style_status_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_STATUS = "style11"
        assert os.environ["ZRB_LLM_UI_STYLE_STATUS"] == "style11"

    def test_llm_ui_style_bottom_toolbar_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_STYLE_BOTTOM_TOOLBAR = "style12"
        assert os.environ["ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR"] == "style12"

    def test_llm_ui_command_summarize_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_SUMMARIZE = ["/compress", "/compact"]
        assert os.environ["ZRB_LLM_UI_COMMAND_SUMMARIZE"] == "/compress,/compact"

    def test_llm_ui_command_attach_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_ATTACH = ["/attach"]
        assert os.environ["ZRB_LLM_UI_COMMAND_ATTACH"] == "/attach"

    def test_llm_ui_command_exit_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_EXIT = ["/q", "/quit"]
        assert os.environ["ZRB_LLM_UI_COMMAND_EXIT"] == "/q,/quit"

    def test_llm_ui_command_info_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_INFO = ["/info"]
        assert os.environ["ZRB_LLM_UI_COMMAND_INFO"] == "/info"

    def test_llm_ui_command_save_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_SAVE = ["/save"]
        assert os.environ["ZRB_LLM_UI_COMMAND_SAVE"] == "/save"

    def test_llm_ui_command_load_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_LOAD = ["/load"]
        assert os.environ["ZRB_LLM_UI_COMMAND_LOAD"] == "/load"

    def test_llm_ui_command_yolo_toggle_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_YOLO_TOGGLE = ["/yolo"]
        assert os.environ["ZRB_LLM_UI_COMMAND_YOLO_TOGGLE"] == "/yolo"

    def test_llm_ui_command_redirect_output_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_REDIRECT_OUTPUT = [">", "/redirect"]
        assert os.environ["ZRB_LLM_UI_COMMAND_REDIRECT_OUTPUT"] == ">,/redirect"

    def test_llm_ui_command_exec_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_EXEC = ["!", "/exec"]
        assert os.environ["ZRB_LLM_UI_COMMAND_EXEC"] == "!,/exec"

    def test_llm_ui_command_set_model_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_SET_MODEL = ["/model"]
        assert os.environ["ZRB_LLM_UI_COMMAND_SET_MODEL"] == "/model"

    def test_llm_ui_command_btw_setter(self, monkeypatch):
        config = Config()
        config.LLM_UI_COMMAND_BTW = ["/btw"]
        assert os.environ["ZRB_LLM_UI_COMMAND_BTW"] == "/btw"
