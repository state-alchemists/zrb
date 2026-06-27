import logging
import os

from zrb.config.config import Config


class TestConfigSetters:
    """Test Config property setters by verifying they write to os.environ."""

    _original_env: dict[str, str] = {}

    def setup_method(self):
        """Save original environment before each test."""
        self._original_env = dict(os.environ)

    def teardown_method(self):
        """Restore original environment after each test to avoid pollution."""
        # Remove any keys that weren't in original
        keys_to_delete = [k for k in os.environ if k not in self._original_env]
        for key in keys_to_delete:
            del os.environ[key]
        # Restore original values
        for key, value in self._original_env.items():
            if os.environ.get(key) != value:
                os.environ[key] = value

    def test_env_prefix_setter(self, monkeypatch):
        config = Config()
        config.ENV_PREFIX = "MYAPP"
        assert os.environ["_ZRB_ENV_PREFIX"] == "MYAPP"

    def test_shell_setter(self, monkeypatch):
        config = Config()
        config.SHELL = "my-shell"
        assert os.environ["ZRB_SHELL"] == "my-shell"

    def test_editor_setter(self, monkeypatch):
        config = Config()
        config.EDITOR = "my-editor"
        assert os.environ["ZRB_EDITOR"] == "my-editor"

    def test_diff_edit_command_tpl_setter(self, monkeypatch):
        config = Config()
        config.DIFF_EDIT_COMMAND_TPL = "my-diff"
        assert os.environ["ZRB_DIFF_EDIT_COMMAND"] == "my-diff"

    def test_init_modules_setter(self, monkeypatch):
        config = Config()
        config.INIT_MODULES = ["mod1", "mod2"]
        assert os.environ["ZRB_INIT_MODULES"] == "mod1,mod2"

    def test_root_group_name_setter(self, monkeypatch):
        config = Config()
        config.ROOT_GROUP_NAME = "my-root"
        assert os.environ["ZRB_ROOT_GROUP_NAME"] == "my-root"

    def test_root_group_description_setter(self, monkeypatch):
        config = Config()
        config.ROOT_GROUP_DESCRIPTION = "my-desc"
        assert os.environ["ZRB_ROOT_GROUP_DESCRIPTION"] == "my-desc"

    def test_init_scripts_setter(self, monkeypatch):
        config = Config()
        config.INIT_SCRIPTS = ["script1", "script2"]
        assert os.environ["ZRB_INIT_SCRIPTS"] == "script1:script2"

    def test_init_file_name_setter(self, monkeypatch):
        config = Config()
        config.INIT_FILE_NAME = "my_init.py"
        assert os.environ["ZRB_INIT_FILE_NAME"] == "my_init.py"

    def test_logging_level_setter_int(self, monkeypatch):
        config = Config()
        config.LOGGING_LEVEL = logging.DEBUG
        assert os.environ["ZRB_LOGGING_LEVEL"] == "DEBUG"

    def test_logging_level_setter_str(self, monkeypatch):
        config = Config()
        config.LOGGING_LEVEL = "INFO"
        assert os.environ["ZRB_LOGGING_LEVEL"] == "INFO"

    def test_load_builtin_setter_true(self, monkeypatch):
        config = Config()
        config.LOAD_BUILTIN = True
        assert os.environ["ZRB_LOAD_BUILTIN"] == "on"

    def test_load_builtin_setter_false(self, monkeypatch):
        config = Config()
        config.LOAD_BUILTIN = False
        assert os.environ["ZRB_LOAD_BUILTIN"] == "off"

    def test_warn_unrecommended_command_setter(self, monkeypatch):
        config = Config()
        config.WARN_UNRECOMMENDED_COMMAND = True
        assert os.environ["ZRB_WARN_UNRECOMMENDED_COMMAND"] == "on"

    def test_session_log_dir_setter(self, monkeypatch):
        config = Config()
        config.SESSION_LOG_DIR = "/tmp/session"
        assert os.environ["ZRB_SESSION_LOG_DIR"] == "/tmp/session"

    def test_todo_dir_setter(self, monkeypatch):
        config = Config()
        config.TODO_DIR = "/tmp/todo"
        assert os.environ["ZRB_TODO_DIR"] == "/tmp/todo"

    def test_todo_visual_filter_setter(self, monkeypatch):
        config = Config()
        config.TODO_VISUAL_FILTER = "filter"
        assert os.environ["ZRB_TODO_FILTER"] == "filter"

    def test_todo_retention_setter(self, monkeypatch):
        config = Config()
        config.TODO_RETENTION = "1w"
        assert os.environ["ZRB_TODO_RETENTION"] == "1w"

    def test_version_setter(self, monkeypatch):
        config = Config()
        config.VERSION = "1.0.0"
        assert os.environ["_ZRB_CUSTOM_VERSION"] == "1.0.0"

    def test_web_css_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_CSS_PATH = ["css1", "css2"]
        assert os.environ["ZRB_WEB_CSS_PATH"] == "css1:css2"

    def test_web_js_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_JS_PATH = ["js1", "js2"]
        assert os.environ["ZRB_WEB_JS_PATH"] == "js1:js2"

    def test_web_favicon_path_setter(self, monkeypatch):
        config = Config()
        config.WEB_FAVICON_PATH = "/favicon.ico"
        assert os.environ["ZRB_WEB_FAVICON_PATH"] == "/favicon.ico"

    def test_web_color_setter(self, monkeypatch):
        config = Config()
        config.WEB_COLOR = "red"
        assert os.environ["ZRB_WEB_COLOR"] == "red"

    def test_web_http_port_setter(self, monkeypatch):
        config = Config()
        config.WEB_HTTP_PORT = 1234
        assert os.environ["ZRB_WEB_HTTP_PORT"] == "1234"

    def test_web_guest_username_setter(self, monkeypatch):
        config = Config()
        config.WEB_GUEST_USERNAME = "guestuser"
        assert os.environ["ZRB_WEB_GUEST_USERNAME"] == "guestuser"

    def test_web_super_admin_username_setter(self, monkeypatch):
        config = Config()
        config.WEB_SUPER_ADMIN_USERNAME = "adminuser"
        assert os.environ["ZRB_WEB_SUPER_ADMIN_USERNAME"] == "adminuser"

    def test_web_super_admin_password_setter(self, monkeypatch):
        config = Config()
        config.WEB_SUPER_ADMIN_PASSWORD = "adminpass"
        assert os.environ["ZRB_WEB_SUPER_ADMIN_PASSWORD"] == "adminpass"

    def test_web_access_token_cookie_name_setter(self, monkeypatch):
        config = Config()
        config.WEB_ACCESS_TOKEN_COOKIE_NAME = "at"
        assert os.environ["ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME"] == "at"

    def test_web_refresh_token_cookie_name_setter(self, monkeypatch):
        config = Config()
        config.WEB_REFRESH_TOKEN_COOKIE_NAME = "rt"
        assert os.environ["ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME"] == "rt"

    def test_web_secret_key_setter(self, monkeypatch):
        config = Config()
        config.WEB_SECRET_KEY = "secret"
        assert os.environ["ZRB_WEB_SECRET_KEY"] == "secret"

    def test_web_auth_enabled_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_ENABLED = True
        assert os.environ["ZRB_WEB_AUTH_ENABLED"] == "on"

    def test_web_auth_access_token_expire_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = 10
        assert os.environ["ZRB_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"] == "10"

    def test_web_auth_refresh_token_expire_setter(self, monkeypatch):
        config = Config()
        config.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = 20
        assert os.environ["ZRB_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES"] == "20"

    def test_web_title_setter(self, monkeypatch):
        config = Config()
        config.WEB_TITLE = "title"
        assert os.environ["ZRB_WEB_TITLE"] == "title"

    def test_web_jargon_setter(self, monkeypatch):
        config = Config()
        config.WEB_JARGON = "jargon"
        assert os.environ["ZRB_WEB_JARGON"] == "jargon"

    def test_web_homepage_intro_setter(self, monkeypatch):
        config = Config()
        config.WEB_HOMEPAGE_INTRO = "intro"
        assert os.environ["ZRB_WEB_HOMEPAGE_INTRO"] == "intro"

    def test_ascii_art_dir_setter(self, monkeypatch):
        config = Config()
        config.ASCII_ART_DIR = "/tmp/ascii"
        assert os.environ["ZRB_ASCII_ART_DIR"] == "/tmp/ascii"

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

    def test_llm_history_dir_setter(self, monkeypatch):
        config = Config()
        config.LLM_HISTORY_DIR = "/tmp/history"
        assert os.environ["ZRB_LLM_HISTORY_DIR"] == "/tmp/history"

    def test_llm_journal_dir_setter(self, monkeypatch):
        config = Config()
        config.LLM_JOURNAL_DIR = "/tmp/journal"
        assert os.environ["ZRB_LLM_JOURNAL_DIR"] == "/tmp/journal"

    def test_llm_journal_index_file_setter(self, monkeypatch):
        config = Config()
        config.LLM_JOURNAL_INDEX_FILE = "journal.md"
        assert os.environ["ZRB_LLM_JOURNAL_INDEX_FILE"] == "journal.md"

    def test_llm_model_setter_with_value(self, monkeypatch):
        config = Config()
        config.LLM_MODEL = "model"
        assert os.environ["ZRB_LLM_MODEL"] == "model"

    def test_llm_model_setter_with_none(self, monkeypatch):
        config = Config()
        config.LLM_MODEL = "model"
        config.LLM_MODEL = None
        assert "ZRB_LLM_MODEL" not in os.environ

    def test_llm_small_model_setter_with_value(self, monkeypatch):
        config = Config()
        config.LLM_SMALL_MODEL = "small-model"
        assert os.environ["ZRB_LLM_SMALL_MODEL"] == "small-model"

    def test_llm_small_model_setter_with_none(self, monkeypatch):
        config = Config()
        config.LLM_SMALL_MODEL = "small-model"
        config.LLM_SMALL_MODEL = None
        assert "ZRB_LLM_SMALL_MODEL" not in os.environ

    def test_llm_base_url_setter_with_value(self, monkeypatch):
        config = Config()
        config.LLM_BASE_URL = "http://localhost:8080"
        assert os.environ["ZRB_LLM_BASE_URL"] == "http://localhost:8080"

    def test_llm_base_url_setter_with_none(self, monkeypatch):
        config = Config()
        config.LLM_BASE_URL = "http://localhost:8080"
        config.LLM_BASE_URL = None
        assert "ZRB_LLM_BASE_URL" not in os.environ

    def test_llm_api_key_setter_with_value(self, monkeypatch):
        config = Config()
        config.LLM_API_KEY = "key"
        assert os.environ["ZRB_LLM_API_KEY"] == "key"

    def test_llm_api_key_setter_with_none(self, monkeypatch):
        config = Config()
        config.LLM_API_KEY = "key"
        config.LLM_API_KEY = None
        assert "ZRB_LLM_API_KEY" not in os.environ

    def test_llm_max_request_per_minute_setter(self, monkeypatch):
        config = Config()
        config.LLM_MAX_REQUEST_PER_MINUTE = 100
        assert os.environ["ZRB_LLM_MAX_REQUEST_PER_MINUTE"] == "100"

    def test_llm_max_token_per_minute_setter(self, monkeypatch):
        config = Config()
        config.LLM_MAX_TOKEN_PER_MINUTE = 1000
        assert os.environ["ZRB_LLM_MAX_TOKENS_PER_MINUTE"] == "1000"

    def test_llm_max_token_per_request_setter(self, monkeypatch):
        config = Config()
        config.LLM_MAX_TOKEN_PER_REQUEST = 500
        assert os.environ["ZRB_LLM_MAX_TOKENS_PER_REQUEST"] == "500"

    def test_llm_throttle_sleep_setter(self, monkeypatch):
        config = Config()
        config.LLM_THROTTLE_SLEEP = 0.5
        assert os.environ["ZRB_LLM_THROTTLE_SLEEP"] == "0.5"

    def test_llm_history_summarization_window_setter(self, monkeypatch):
        config = Config()
        config.LLM_HISTORY_SUMMARIZATION_WINDOW = 50
        assert os.environ["ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW"] == "50"

    def test_llm_conversational_summarization_threshold_setter(self, monkeypatch):
        config = Config()
        config.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD = 10000
        assert (
            os.environ["ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD"]
            == "10000"
        )

    def test_llm_message_summarization_threshold_setter(self, monkeypatch):
        config = Config()
        config.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD = 5000
        assert os.environ["ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD"] == "5000"

    def test_llm_repo_analysis_extraction_threshold_setter(self, monkeypatch):
        config = Config()
        config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD = 20000
        assert os.environ["ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD"] == "20000"

    def test_llm_repo_analysis_summarization_threshold_setter(self, monkeypatch):
        config = Config()
        config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD = 20000
        assert (
            os.environ["ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD"] == "20000"
        )

    def test_llm_file_analysis_threshold_setter(self, monkeypatch):
        config = Config()
        config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD = 20000
        assert os.environ["ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD"] == "20000"

    def test_llm_prompt_dir_setter(self, monkeypatch):
        config = Config()
        config.LLM_PROMPT_DIR = "/tmp/prompt"
        assert os.environ["ZRB_LLM_PROMPT_DIR"] == "/tmp/prompt"

    def test_llm_base_prompt_dir_setter(self, monkeypatch):
        config = Config()
        config.LLM_BASE_PROMPT_DIR = "/tmp/base-prompt"
        assert os.environ["ZRB_LLM_BASE_PROMPT_DIR"] == "/tmp/base-prompt"

    def test_llm_plugin_dirs_setter(self, monkeypatch):
        config = Config()
        config.LLM_PLUGIN_DIRS = ["p1", "p2"]
        assert os.environ["ZRB_LLM_PLUGIN_DIRS"] == "p1:p2"

    def test_rag_embedding_api_key_setter_with_value(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_API_KEY = "rag-key"
        assert os.environ["ZRB_RAG_EMBEDDING_API_KEY"] == "rag-key"

    def test_rag_embedding_api_key_setter_with_none(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_API_KEY = "rag-key"
        config.RAG_EMBEDDING_API_KEY = None
        assert "ZRB_RAG_EMBEDDING_API_KEY" not in os.environ

    def test_rag_embedding_base_url_setter_with_value(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_BASE_URL = "http://localhost:8081"
        assert os.environ["ZRB_RAG_EMBEDDING_BASE_URL"] == "http://localhost:8081"

    def test_rag_embedding_base_url_setter_with_none(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_BASE_URL = "http://localhost:8081"
        config.RAG_EMBEDDING_BASE_URL = None
        assert "ZRB_RAG_EMBEDDING_BASE_URL" not in os.environ

    def test_rag_embedding_model_setter(self, monkeypatch):
        config = Config()
        config.RAG_EMBEDDING_MODEL = "text-embedding-3-small"
        assert os.environ["ZRB_RAG_EMBEDDING_MODEL"] == "text-embedding-3-small"

    def test_rag_chunk_size_setter(self, monkeypatch):
        config = Config()
        config.RAG_CHUNK_SIZE = 2048
        assert os.environ["ZRB_RAG_CHUNK_SIZE"] == "2048"

    def test_rag_overlap_setter(self, monkeypatch):
        config = Config()
        config.RAG_OVERLAP = 256
        assert os.environ["ZRB_RAG_OVERLAP"] == "256"

    def test_rag_max_result_count_setter(self, monkeypatch):
        config = Config()
        config.RAG_MAX_RESULT_COUNT = 10
        assert os.environ["ZRB_RAG_MAX_RESULT_COUNT"] == "10"

    def test_search_internet_method_setter(self, monkeypatch):
        config = Config()
        config.SEARCH_INTERNET_METHOD = "searxng"
        assert os.environ["ZRB_SEARCH_INTERNET_METHOD"] == "searxng"

    def test_brave_api_key_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_KEY = "brave-key"
        assert os.environ["BRAVE_API_KEY"] == "brave-key"

    def test_brave_api_safe_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_SAFE = "on"
        assert os.environ["ZRB_BRAVE_API_SAFE"] == "on"

    def test_brave_api_lang_setter(self, monkeypatch):
        config = Config()
        config.BRAVE_API_LANG = "en"
        assert os.environ["ZRB_BRAVE_API_LANG"] == "en"

    def test_serpapi_key_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_KEY = "serp-key"
        assert os.environ["SERPAPI_KEY"] == "serp-key"

    def test_serpapi_safe_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_SAFE = "on"
        assert os.environ["ZRB_SERPAPI_SAFE"] == "on"

    def test_serpapi_lang_setter(self, monkeypatch):
        config = Config()
        config.SERPAPI_LANG = "en"
        assert os.environ["ZRB_SERPAPI_LANG"] == "en"

    def test_searxng_port_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_PORT = 9090
        assert os.environ["ZRB_SEARXNG_PORT"] == "9090"

    def test_searxng_base_url_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_BASE_URL = "http://searxng:8080"
        assert os.environ["ZRB_SEARXNG_BASE_URL"] == "http://searxng:8080"

    def test_searxng_safe_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_SAFE = 1
        assert os.environ["ZRB_SEARXNG_SAFE"] == "1"

    def test_searxng_lang_setter(self, monkeypatch):
        config = Config()
        config.SEARXNG_LANG = "en-US"
        assert os.environ["ZRB_SEARXNG_LANG"] == "en-US"

    def test_banner_setter(self, monkeypatch):
        config = Config()
        config.BANNER = "Custom Banner"
        assert os.environ["ZRB_BANNER"] == "Custom Banner"

    def test_llm_show_tool_call_detail_setter_true(self, monkeypatch):
        config = Config()
        config.LLM_SHOW_TOOL_CALL_DETAIL = True
        assert os.environ["ZRB_LLM_SHOW_TOOL_CALL_DETAIL"] == "on"

    def test_llm_show_tool_call_detail_setter_false(self, monkeypatch):
        config = Config()
        config.LLM_SHOW_TOOL_CALL_DETAIL = False
        assert os.environ["ZRB_LLM_SHOW_TOOL_CALL_DETAIL"] == "off"

    def test_llm_show_tool_call_result_setter_true(self, monkeypatch):
        config = Config()
        config.LLM_SHOW_TOOL_CALL_RESULT = True
        assert os.environ["ZRB_LLM_SHOW_TOOL_CALL_RESULT"] == "on"

    def test_llm_show_tool_call_result_setter_false(self, monkeypatch):
        config = Config()
        config.LLM_SHOW_TOOL_CALL_RESULT = False
        assert os.environ["ZRB_LLM_SHOW_TOOL_CALL_RESULT"] == "off"

    def test_llm_include_sections_setter_list(self, monkeypatch):
        config = Config()
        config.LLM_INCLUDE_SECTIONS = ["persona", "mandate"]
        assert os.environ["ZRB_LLM_INCLUDE_SECTIONS"] == "persona,mandate"

    def test_llm_include_sections_setter_str(self, monkeypatch):
        config = Config()
        config.LLM_INCLUDE_SECTIONS = "system_context,tool_guidance"
        assert os.environ["ZRB_LLM_INCLUDE_SECTIONS"] == "system_context,tool_guidance"

    def test_llm_search_project_setter_true(self, monkeypatch):
        config = Config()
        config.LLM_SEARCH_PROJECT = True
        assert os.environ["ZRB_LLM_SEARCH_PROJECT"] == "on"

    def test_llm_search_project_setter_false(self, monkeypatch):
        config = Config()
        config.LLM_SEARCH_PROJECT = False
        assert os.environ["ZRB_LLM_SEARCH_PROJECT"] == "off"

    def test_llm_search_home_setter_true(self, monkeypatch):
        config = Config()
        config.LLM_SEARCH_HOME = True
        assert os.environ["ZRB_LLM_SEARCH_HOME"] == "on"

    def test_llm_search_home_setter_false(self, monkeypatch):
        config = Config()
        config.LLM_SEARCH_HOME = False
        assert os.environ["ZRB_LLM_SEARCH_HOME"] == "off"

    def test_llm_config_dir_names_setter(self, monkeypatch):
        config = Config()
        config.LLM_CONFIG_DIR_NAMES = [".claude", ".zrb"]
        assert os.environ["ZRB_LLM_CONFIG_DIR_NAMES"] == ".claude:.zrb"

    def test_llm_base_search_dirs_setter(self, monkeypatch):
        config = Config()
        config.LLM_BASE_SEARCH_DIRS = ["/dir1", "/dir2"]
        assert os.environ["ZRB_LLM_BASE_SEARCH_DIRS"] == "/dir1:/dir2"

    def test_llm_extra_skill_dirs_setter(self, monkeypatch):
        config = Config()
        config.LLM_EXTRA_SKILL_DIRS = ["/skill1", "/skill2"]
        assert os.environ["ZRB_LLM_EXTRA_SKILL_DIRS"] == "/skill1:/skill2"

    def test_llm_extra_agent_dirs_setter(self, monkeypatch):
        config = Config()
        config.LLM_EXTRA_AGENT_DIRS = ["/agent1", "/agent2"]
        assert os.environ["ZRB_LLM_EXTRA_AGENT_DIRS"] == "/agent1:/agent2"

    def test_use_tiktoken_setter(self, monkeypatch):
        config = Config()
        config.USE_TIKTOKEN = True
        assert os.environ["ZRB_USE_TIKTOKEN"] == "on"

    def test_tiktoken_encoding_name_setter(self, monkeypatch):
        config = Config()
        config.TIKTOKEN_ENCODING_NAME = "cl100k_base"
        assert os.environ["ZRB_TIKTOKEN_ENCODING_NAME"] == "cl100k_base"

    def test_mcp_config_file_setter(self, monkeypatch):
        config = Config()
        config.MCP_CONFIG_FILE = "mcp.json"
        assert os.environ["ZRB_MCP_CONFIG_FILE"] == "mcp.json"

    def test_hooks_enabled_setter(self, monkeypatch):
        config = Config()
        config.HOOKS_ENABLED = True
        assert os.environ["ZRB_HOOKS_ENABLED"] == "on"

    def test_hooks_dirs_setter(self, monkeypatch):
        config = Config()
        config.HOOKS_DIRS = ["/hooks1", "/hooks2"]
        assert os.environ["ZRB_HOOKS_DIRS"] == "/hooks1:/hooks2"

    def test_hooks_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_HOOKS_TIMEOUT", raising=False)
        config = Config()
        assert config.HOOKS_TIMEOUT == 30000  # 30 seconds in milliseconds

    def test_hooks_timeout_setter(self, monkeypatch):
        monkeypatch.delenv("ZRB_HOOKS_TIMEOUT", raising=False)
        config = Config()
        config.HOOKS_TIMEOUT = 60000
        assert os.environ["ZRB_HOOKS_TIMEOUT"] == "60000"

    def test_hooks_debug_setter(self, monkeypatch):
        config = Config()
        config.HOOKS_DEBUG = True
        assert os.environ["ZRB_HOOKS_DEBUG"] == "on"

    def test_hooks_log_level_setter(self, monkeypatch):
        config = Config()
        config.HOOKS_LOG_LEVEL = "DEBUG"
        assert os.environ["ZRB_HOOKS_LOG_LEVEL"] == "DEBUG"
