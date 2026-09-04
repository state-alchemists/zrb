import os

import pytest

from zrb.config.config import Config


class TestLLMConfigSetters:
    """Test Config property setters by verifying they write to os.environ."""

    _original_env: dict[str, str] = {}

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

    def test_llm_model_setter_with_none_raises(self, monkeypatch):
        config = Config()
        config.LLM_MODEL = "model"
        with pytest.raises(ValueError):
            config.LLM_MODEL = None

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

    def test_enable_tiktoken_setter(self, monkeypatch):
        # Renamed from USE_TIKTOKEN (ADR-0026).
        config = Config()
        config.ENABLE_TIKTOKEN = True
        assert os.environ["ZRB_ENABLE_TIKTOKEN"] == "on"

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
