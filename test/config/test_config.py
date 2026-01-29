import logging
import os
from unittest import mock
from unittest.mock import patch

from zrb.config.config import Config
from zrb.config.helper import get_current_shell, get_env, get_log_level


def test_logger():
    config = Config()
    assert isinstance(config.LOGGER, logging.Logger)


def test_env_prefix():
    # Default
    config = Config()
    assert config.ENV_PREFIX == "ZRB"

    # Custom
    with patch.dict(os.environ, {"_ZRB_ENV_PREFIX": "MYAPP"}):
        assert config.ENV_PREFIX == "MYAPP"


def test_getenv_single():
    config = Config()
    # No env set, returns default
    assert get_env("TEST_VAR", "default", config.ENV_PREFIX) == "default"

    # Env set
    with patch.dict(os.environ, {"ZRB_TEST_VAR": "value"}):
        assert get_env("TEST_VAR", "default", config.ENV_PREFIX) == "value"


def test_getenv_list():
    config = Config()
    # First match
    with patch.dict(os.environ, {"ZRB_VAR1": "val1", "ZRB_VAR2": "val2"}):
        assert get_env(["VAR1", "VAR2"], "default", config.ENV_PREFIX) == "val1"

    # Second match
    with patch.dict(os.environ, {"ZRB_VAR2": "val2"}):
        assert get_env(["VAR1", "VAR2"], "default", config.ENV_PREFIX) == "val2"


def test_default_shell_env_var_set(monkeypatch):
    monkeypatch.setenv("ZRB_SHELL", "my-shell")
    config = Config()
    assert config.SHELL == "my-shell"


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    config = Config()
    assert config.SHELL == "PowerShell"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_zsh(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    config = Config()
    assert config.SHELL == "zsh"
    # Test helper directly
    assert get_current_shell() == "zsh"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_bash(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/bash")
    config = Config()
    assert config.SHELL == "bash"
    # Test helper directly
    assert get_current_shell() == "bash"


def test_default_editor(monkeypatch):
    monkeypatch.setenv("ZRB_EDITOR", "my-editor")
    config = Config()
    assert config.EDITOR == "my-editor"


def test_diff_edit_command():
    config = Config()

    # Test vscode
    with patch.dict(os.environ, {"ZRB_EDITOR": "code"}):
        assert "code --wait" in config.DIFF_EDIT_COMMAND_TPL

    # Test emacs
    with patch.dict(os.environ, {"ZRB_EDITOR": "emacs"}):
        assert "emacs --eval" in config.DIFF_EDIT_COMMAND_TPL

    # Test vim
    with patch.dict(os.environ, {"ZRB_EDITOR": "vim"}):
        assert "vim -d" in config.DIFF_EDIT_COMMAND_TPL

    # Test default (nano or unknown)
    with patch.dict(os.environ, {"ZRB_EDITOR": "nano"}):
        assert "vimdiff" in config.DIFF_EDIT_COMMAND_TPL


def test_init_modules(monkeypatch):
    monkeypatch.setenv("ZRB_INIT_MODULES", "module1:module2")
    config = Config()
    assert config.INIT_MODULES == ["module1", "module2"]


def test_init_modules_empty(monkeypatch):
    monkeypatch.setenv("ZRB_INIT_MODULES", "")
    config = Config()
    assert config.INIT_MODULES == []


def test_root_group_name(monkeypatch):
    monkeypatch.setenv("ZRB_ROOT_GROUP_NAME", "my-group")
    config = Config()
    assert config.ROOT_GROUP_NAME == "my-group"


def test_root_group_description(monkeypatch):
    monkeypatch.setenv("ZRB_ROOT_GROUP_DESCRIPTION", "My Powerhouse")
    config = Config()
    assert config.ROOT_GROUP_DESCRIPTION == "My Powerhouse"


def test_init_scripts(monkeypatch):
    monkeypatch.setenv("ZRB_INIT_SCRIPTS", "script1:script2")
    config = Config()
    assert config.INIT_SCRIPTS == ["script1", "script2"]


def test_init_scripts_empty(monkeypatch):
    monkeypatch.setenv("ZRB_INIT_SCRIPTS", "")
    config = Config()
    assert config.INIT_SCRIPTS == []


def test_init_file_name(monkeypatch):
    monkeypatch.setenv("ZRB_INIT_FILE_NAME", "my_init.py")
    config = Config()
    assert config.INIT_FILE_NAME == "my_init.py"


def test_logging_level(monkeypatch):
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "DEBUG")
    config = Config()
    assert config.LOGGING_LEVEL == logging.DEBUG


def test_logging_level_invalid(monkeypatch):
    monkeypatch.setenv("ZRB_LOGGING_LEVEL", "INVALID_LEVEL")
    config = Config()
    assert config.LOGGING_LEVEL == logging.WARNING


def test_get_log_level():
    assert get_log_level("CRITICAL") == logging.CRITICAL
    assert get_log_level("ERROR") == logging.ERROR
    assert get_log_level("WARN") == logging.WARNING
    assert get_log_level("WARNING") == logging.WARNING
    assert get_log_level("INFO") == logging.INFO
    assert get_log_level("DEBUG") == logging.DEBUG
    assert get_log_level("NOTSET") == logging.NOTSET
    assert get_log_level("INVALID") == logging.WARNING


def test_load_builtin(monkeypatch):
    monkeypatch.setenv("ZRB_LOAD_BUILTIN", "0")
    config = Config()
    assert not config.LOAD_BUILTIN


def test_warn_unrecommended_command(monkeypatch):
    monkeypatch.setenv("ZRB_WARN_UNRECOMMENDED_COMMAND", "0")
    config = Config()
    assert not config.WARN_UNRECOMMENDED_COMMAND


@mock.patch("os.path.expanduser", return_value="/home/user/.zrb/session")
def test_session_log_dir_default(mock_expanduser, monkeypatch):
    monkeypatch.delenv("ZRB_SESSION_LOG_DIR", raising=False)
    config = Config()
    assert config.SESSION_LOG_DIR == "/home/user/.zrb/session"


def test_session_log_dir_custom(monkeypatch):
    monkeypatch.setenv("ZRB_SESSION_LOG_DIR", "/tmp/zrb/session")
    config = Config()
    assert config.SESSION_LOG_DIR == "/tmp/zrb/session"


@mock.patch("os.path.expanduser", return_value="/home/user/todo")
def test_todo_dir_default(mock_expanduser, monkeypatch):
    monkeypatch.delenv("ZRB_TODO_DIR", raising=False)
    config = Config()
    assert config.TODO_DIR == "/home/user/todo"


def test_todo_dir_custom(monkeypatch):
    monkeypatch.setenv("ZRB_TODO_DIR", "/tmp/todo")
    config = Config()
    assert config.TODO_DIR == "/tmp/todo"


def test_todo_visual_filter(monkeypatch):
    monkeypatch.setenv("ZRB_TODO_FILTER", "my-filter")
    config = Config()
    assert config.TODO_VISUAL_FILTER == "my-filter"


def test_todo_retention(monkeypatch):
    monkeypatch.setenv("ZRB_TODO_RETENTION", "4w")
    config = Config()
    assert config.TODO_RETENTION == "4w"


@mock.patch("importlib.metadata.version", return_value="1.2.3")
def test_version_default(mock_version, monkeypatch):
    monkeypatch.delenv("_ZRB_CUSTOM_VERSION", raising=False)
    config = Config()
    assert config.VERSION == "1.2.3"


def test_version_custom(monkeypatch):
    monkeypatch.setenv("_ZRB_CUSTOM_VERSION", "my-version")
    config = Config()
    assert config.VERSION == "my-version"


def test_web_css_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_CSS_PATH", "path1:path2")
    config = Config()
    assert config.WEB_CSS_PATH == ["path1", "path2"]


def test_web_css_path_empty(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_CSS_PATH", "")
    config = Config()
    assert config.WEB_CSS_PATH == []


def test_web_js_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JS_PATH", "path1:path2")
    config = Config()
    assert config.WEB_JS_PATH == ["path1", "path2"]


def test_web_js_path_empty(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JS_PATH", "")
    config = Config()
    assert config.WEB_JS_PATH == []


def test_web_favicon_path(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_FAVICON_PATH", "/my-favicon.ico")
    config = Config()
    assert config.WEB_FAVICON_PATH == "/my-favicon.ico"


def test_web_color(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_COLOR", "blue")
    config = Config()
    assert config.WEB_COLOR == "blue"


def test_web_http_port(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_HTTP_PORT", "8080")
    config = Config()
    assert config.WEB_HTTP_PORT == 8080


def test_web_guest_username(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_GUEST_USERNAME", "guest")
    config = Config()
    assert config.WEB_GUEST_USERNAME == "guest"


def test_web_super_admin_username(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SUPER_ADMIN_USERNAME", "superadmin")
    config = Config()
    assert config.WEB_SUPER_ADMIN_USERNAME == "superadmin"


def test_web_super_admin_password(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SUPER_ADMIN_PASSWORD", "superpassword")
    config = Config()
    assert config.WEB_SUPER_ADMIN_PASSWORD == "superpassword"


def test_web_access_token_cookie_name(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME", "my_access_token")
    config = Config()
    assert config.WEB_ACCESS_TOKEN_COOKIE_NAME == "my_access_token"


def test_web_refresh_token_cookie_name(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME", "my_refresh_token")
    config = Config()
    assert config.WEB_REFRESH_TOKEN_COOKIE_NAME == "my_refresh_token"


def test_web_secret_key(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_SECRET", "my-secret")
    config = Config()
    assert config.WEB_SECRET_KEY == "my-secret"


def test_web_enable_auth(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_ENABLE_AUTH", "1")
    config = Config()
    assert config.WEB_ENABLE_AUTH


def test_web_auth_access_token_expire_minutes(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    config = Config()
    assert config.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES == 60


def test_web_auth_refresh_token_expire_minutes(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES", "120")
    config = Config()
    assert config.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES == 120


def test_web_title(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_TITLE", "My Zrb")
    config = Config()
    assert config.WEB_TITLE == "My Zrb"


def test_web_jargon(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_JARGON", "My Powerhouse")
    config = Config()
    assert config.WEB_JARGON == "My Powerhouse"


def test_web_homepage_intro(monkeypatch):
    monkeypatch.setenv("ZRB_WEB_HOMEPAGE_INTRO", "Hello Zrb")
    config = Config()
    assert config.WEB_HOMEPAGE_INTRO == "Hello Zrb"


def test_llm_model(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "my-model")
    config = Config()
    assert config.LLM_MODEL == "my-model"


def test_llm_model_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    config = Config()
    assert config.LLM_MODEL is None


def test_llm_base_url(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_BASE_URL", "http://localhost:8080")
    config = Config()
    assert config.LLM_BASE_URL == "http://localhost:8080"


def test_llm_api_key(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_API_KEY", "my-api-key")
    config = Config()
    assert config.LLM_API_KEY == "my-api-key"


def test_llm_api_key_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_API_KEY", raising=False)
    config = Config()
    assert config.LLM_API_KEY is None


def test_llm_max_request_per_minute(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_REQUEST_PER_MINUTE", "30")
    config = Config()
    assert config.LLM_MAX_REQUEST_PER_MINUTE == 30


def test_llm_max_request_per_minute_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MAX_REQUEST_PER_MINUTE", raising=False)
    config = Config()
    assert config.LLM_MAX_REQUEST_PER_MINUTE == 60


def test_llm_max_token_per_minute(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_MINUTE", "200000")
    config = Config()
    assert config.LLM_MAX_TOKENS_PER_MINUTE == 200000


def test_llm_max_token_per_request(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_TOKEN_PER_REQUEST", "100000")
    config = Config()
    assert config.LLM_MAX_TOKENS_PER_REQUEST == 100000


def test_llm_throttle_sleep(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_THROTTLE_SLEEP", "2.0")
    config = Config()
    assert config.LLM_THROTTLE_SLEEP == 2.0


def test_llm_history_summarization_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD", "30000")
    config = Config()
    assert config.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD == 30000


def test_llm_repo_analysis_extraction_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD == 40000


def test_llm_repo_analysis_summarization_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD == 40000


def test_llm_file_analysis_token_threshold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD", "40000")
    config = Config()
    assert config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD == 40000


def test_rag_embedding_api_key(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_API_KEY", "my-rag-api-key")
    config = Config()
    assert config.RAG_EMBEDDING_API_KEY == "my-rag-api-key"


def test_rag_embedding_base_url(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_BASE_URL", "http://localhost:8081")
    config = Config()
    assert config.RAG_EMBEDDING_BASE_URL == "http://localhost:8081"


def test_rag_embedding_model(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_EMBEDDING_MODEL", "my-embedding-model")
    config = Config()
    assert config.RAG_EMBEDDING_MODEL == "my-embedding-model"


def test_rag_chunk_size(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_CHUNK_SIZE", "2048")
    config = Config()
    assert config.RAG_CHUNK_SIZE == 2048


def test_rag_overlap(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_OVERLAP", "256")
    config = Config()
    assert config.RAG_OVERLAP == 256


def test_rag_max_result_count(monkeypatch):
    monkeypatch.setenv("ZRB_RAG_MAX_RESULT_COUNT", "10")
    config = Config()
    assert config.RAG_MAX_RESULT_COUNT == 10


def test_serpapi_key(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "my-serpapi-key")
    config = Config()
    assert config.SERPAPI_KEY == "my-serpapi-key"


@mock.patch("importlib.metadata.version", return_value="1.2.3")
def test_banner(mock_version, monkeypatch):
    monkeypatch.setenv("ZRB_BANNER", "My Banner {VERSION}")
    config = Config()
    assert config.BANNER == "My Banner 1.2.3"


def test_llm_configs_types():
    # Access all LLM properties to ensure coverage
    config = Config()
    assert config.LLM_MODEL is None or isinstance(config.LLM_MODEL, str)
    assert config.LLM_BASE_URL is None or isinstance(config.LLM_BASE_URL, str)
    assert config.LLM_API_KEY is None or isinstance(config.LLM_API_KEY, str)

    assert isinstance(config.LLM_MAX_REQUEST_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_MINUTE, int)
    assert isinstance(config.LLM_MAX_TOKENS_PER_REQUEST, int)
    assert isinstance(config.LLM_THROTTLE_SLEEP, float)

    assert isinstance(config.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD, int)
    assert isinstance(config.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD, int)

    assert config.RAG_EMBEDDING_API_KEY is None or isinstance(
        config.RAG_EMBEDDING_API_KEY, str
    )
    assert config.RAG_EMBEDDING_BASE_URL is None or isinstance(
        config.RAG_EMBEDDING_BASE_URL, str
    )
    assert isinstance(config.RAG_EMBEDDING_MODEL, str)
    assert isinstance(config.RAG_CHUNK_SIZE, int)
    assert isinstance(config.RAG_OVERLAP, int)
    assert isinstance(config.RAG_MAX_RESULT_COUNT, int)

    assert isinstance(config.SEARCH_INTERNET_METHOD, str)
    assert isinstance(config.BRAVE_API_KEY, str)
    assert isinstance(config.BRAVE_API_SAFE, str)
    assert isinstance(config.BRAVE_API_LANG, str)
    assert isinstance(config.SERPAPI_KEY, str)
    assert isinstance(config.SERPAPI_SAFE, str)
    assert isinstance(config.SERPAPI_LANG, str)

    assert isinstance(config.SEARXNG_PORT, int)
    assert isinstance(config.SEARXNG_BASE_URL, str)
    assert isinstance(config.SEARXNG_SAFE, int)
    assert isinstance(config.SEARXNG_LANG, str)

    assert isinstance(config.BANNER, str)
    assert isinstance(config.USE_TIKTOKEN, bool)
    assert isinstance(config.TIKTOKEN_ENCODING_NAME, str)
