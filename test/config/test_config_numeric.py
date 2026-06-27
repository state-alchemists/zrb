import os

from zrb.config.config import Config


class TestTimeoutConfig:
    """Tests for timeout configuration (all values in milliseconds)."""

    def test_llm_sse_keepalive_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_SSE_KEEPALIVE_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_SSE_KEEPALIVE_TIMEOUT == 60000

    def test_llm_sse_keepalive_timeout_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_SSE_KEEPALIVE_TIMEOUT", "30000")
        config = Config()
        assert config.LLM_SSE_KEEPALIVE_TIMEOUT == 30000

    def test_llm_sse_keepalive_timeout_setter(self, monkeypatch):
        config = Config()
        config.LLM_SSE_KEEPALIVE_TIMEOUT = 45000
        assert os.environ["ZRB_LLM_SSE_KEEPALIVE_TIMEOUT"] == "45000"

    def test_web_shutdown_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_WEB_SHUTDOWN_TIMEOUT", raising=False)
        config = Config()
        assert config.WEB_SHUTDOWN_TIMEOUT == 10000

    def test_web_shutdown_timeout_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_WEB_SHUTDOWN_TIMEOUT", "5000")
        config = Config()
        assert config.WEB_SHUTDOWN_TIMEOUT == 5000

    def test_llm_request_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_REQUEST_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_REQUEST_TIMEOUT == 300000

    def test_llm_input_queue_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_INPUT_QUEUE_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_INPUT_QUEUE_TIMEOUT == 500

    def test_llm_input_queue_timeout_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_INPUT_QUEUE_TIMEOUT", "1000")
        config = Config()
        assert config.LLM_INPUT_QUEUE_TIMEOUT == 1000

    def test_llm_shell_kill_wait_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_SHELL_KILL_WAIT_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_SHELL_KILL_WAIT_TIMEOUT == 5000

    def test_llm_web_page_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_WEB_PAGE_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_WEB_PAGE_TIMEOUT == 30000

    def test_llm_web_http_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_WEB_HTTP_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_WEB_HTTP_TIMEOUT == 30000

    def test_llm_model_fetch_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_MODEL_FETCH_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_MODEL_FETCH_TIMEOUT == 5000

    def test_cmd_cleanup_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_CMD_CLEANUP_TIMEOUT", raising=False)
        config = Config()
        assert config.CMD_CLEANUP_TIMEOUT == 2000

    def test_llm_git_cmd_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_GIT_CMD_TIMEOUT", raising=False)
        config = Config()
        assert config.LLM_GIT_CMD_TIMEOUT == 1000

    def test_llm_git_cmd_timeout_setter(self, monkeypatch):
        config = Config()
        config.LLM_GIT_CMD_TIMEOUT = 2000
        assert os.environ["ZRB_LLM_GIT_CMD_TIMEOUT"] == "2000"


class TestIntervalDelayConfig:
    """Tests for interval/delay configuration (all values in milliseconds)."""

    def test_llm_ui_status_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_UI_STATUS_INTERVAL", raising=False)
        config = Config()
        assert config.LLM_UI_STATUS_INTERVAL == 1000

    def test_llm_ui_status_interval_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_UI_STATUS_INTERVAL", "2000")
        config = Config()
        assert config.LLM_UI_STATUS_INTERVAL == 2000

    def test_llm_ui_long_status_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_UI_LONG_STATUS_INTERVAL", raising=False)
        config = Config()
        assert config.LLM_UI_LONG_STATUS_INTERVAL == 60000

    def test_llm_ui_refresh_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_UI_REFRESH_INTERVAL", raising=False)
        config = Config()
        assert config.LLM_UI_REFRESH_INTERVAL == 500

    def test_llm_ui_flush_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_UI_FLUSH_INTERVAL", raising=False)
        config = Config()
        assert config.LLM_UI_FLUSH_INTERVAL == 500

    def test_scheduler_tick_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_SCHEDULER_TICK_INTERVAL", raising=False)
        config = Config()
        assert config.SCHEDULER_TICK_INTERVAL == 60000

    def test_scheduler_tick_interval_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_SCHEDULER_TICK_INTERVAL", "30000")
        config = Config()
        assert config.SCHEDULER_TICK_INTERVAL == 30000

    def test_http_check_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_HTTP_CHECK_INTERVAL", raising=False)
        config = Config()
        assert config.HTTP_CHECK_INTERVAL == 5000

    def test_tcp_check_interval_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_TCP_CHECK_INTERVAL", raising=False)
        config = Config()
        assert config.TCP_CHECK_INTERVAL == 5000

    def test_task_readiness_delay_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_TASK_READINESS_DELAY", raising=False)
        config = Config()
        assert config.TASK_READINESS_DELAY == 500

    def test_task_readiness_delay_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_TASK_READINESS_DELAY", "1000")
        config = Config()
        assert config.TASK_READINESS_DELAY == 1000

    def test_task_readiness_delay_setter(self, monkeypatch):
        config = Config()
        config.TASK_READINESS_DELAY = 250
        assert os.environ["ZRB_TASK_READINESS_DELAY"] == "250"


class TestSizeLimitConfig:
    """Tests for size/limit configuration."""

    def test_llm_max_completion_files_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_MAX_COMPLETION_FILES", raising=False)
        config = Config()
        assert config.LLM_MAX_COMPLETION_FILES == 5000

    def test_llm_max_output_chars_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_MAX_OUTPUT_CHARS", raising=False)
        config = Config()
        assert config.LLM_MAX_OUTPUT_CHARS == 100000

    def test_llm_max_output_chars_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_MAX_OUTPUT_CHARS", "50000")
        config = Config()
        assert config.LLM_MAX_OUTPUT_CHARS == 50000

    def test_llm_max_output_chars_setter(self, monkeypatch):
        monkeypatch.setenv(
            "ZRB_LLM_MAX_OUTPUT_CHARS", "100000"
        )  # registers var for teardown
        config = Config()
        config.LLM_MAX_OUTPUT_CHARS = 200000
        assert os.environ["ZRB_LLM_MAX_OUTPUT_CHARS"] == "200000"

    def test_llm_history_max_display_chars_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_HISTORY_MAX_DISPLAY_CHARS", raising=False)
        config = Config()
        assert config.LLM_HISTORY_MAX_DISPLAY_CHARS == 5000

    def test_llm_history_truncate_length_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_HISTORY_TRUNCATE_LENGTH", raising=False)
        config = Config()
        assert config.LLM_HISTORY_TRUNCATE_LENGTH == 100

    def test_llm_project_doc_max_chars_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_PROJECT_DOC_MAX_CHARS", raising=False)
        config = Config()
        assert config.LLM_PROJECT_DOC_MAX_CHARS == 8000

    def test_cmd_buffer_limit_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_CMD_BUFFER_LIMIT", raising=False)
        config = Config()
        assert config.CMD_BUFFER_LIMIT == 102400

    def test_llm_ui_max_buffer_size_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_UI_MAX_BUFFER_SIZE", raising=False)
        config = Config()
        assert config.LLM_UI_MAX_BUFFER_SIZE == 2000


class TestRetryConfig:
    """Tests for retry configuration."""

    def test_llm_max_context_retries_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_MAX_CONTEXT_RETRIES", raising=False)
        config = Config()
        assert config.LLM_MAX_CONTEXT_RETRIES == 5

    def test_llm_max_context_retries_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_MAX_CONTEXT_RETRIES", "3")
        config = Config()
        assert config.LLM_MAX_CONTEXT_RETRIES == 3

    def test_llm_max_context_retries_setter(self, monkeypatch):
        config = Config()
        config.LLM_MAX_CONTEXT_RETRIES = 10
        assert os.environ["ZRB_LLM_MAX_CONTEXT_RETRIES"] == "10"

    def test_llm_tool_max_retries_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_TOOL_MAX_RETRIES", raising=False)
        config = Config()
        assert config.LLM_TOOL_MAX_RETRIES == 3

    def test_llm_tool_max_retries_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_TOOL_MAX_RETRIES", "5")
        config = Config()
        assert config.LLM_TOOL_MAX_RETRIES == 5

    def test_llm_mcp_max_retries_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_LLM_MCP_MAX_RETRIES", raising=False)
        config = Config()
        assert config.LLM_MCP_MAX_RETRIES == 3

    def test_llm_mcp_max_retries_setter(self, monkeypatch):
        config = Config()
        config.LLM_MCP_MAX_RETRIES = 5
        assert os.environ["ZRB_LLM_MCP_MAX_RETRIES"] == "5"


class TestPaginationConfig:
    """Tests for pagination configuration."""

    def test_web_session_page_size_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_WEB_SESSION_PAGE_SIZE", raising=False)
        config = Config()
        assert config.WEB_SESSION_PAGE_SIZE == 20

    def test_web_session_page_size_env(self, monkeypatch):
        monkeypatch.setenv("ZRB_WEB_SESSION_PAGE_SIZE", "50")
        config = Config()
        assert config.WEB_SESSION_PAGE_SIZE == 50

    def test_web_api_page_size_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_WEB_API_PAGE_SIZE", raising=False)
        config = Config()
        assert config.WEB_API_PAGE_SIZE == 20

    def test_web_task_session_page_size_default(self, monkeypatch):
        monkeypatch.delenv("ZRB_WEB_TASK_SESSION_PAGE_SIZE", raising=False)
        config = Config()
        assert config.WEB_TASK_SESSION_PAGE_SIZE == 10

    def test_web_task_session_page_size_setter(self, monkeypatch):
        config = Config()
        config.WEB_TASK_SESSION_PAGE_SIZE = 25
        assert os.environ["ZRB_WEB_TASK_SESSION_PAGE_SIZE"] == "25"
