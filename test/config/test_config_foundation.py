import logging
import os
from unittest import mock
from unittest.mock import patch

from zrb.config.config import Config
from zrb.config.helper import get_current_shell, get_env, get_log_level, is_termux


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


def _which(*present):
    """A shutil.which stub that 'finds' only the named executables."""
    return lambda candidate: f"/usr/bin/{candidate}" if candidate in present else None


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    config = Config()
    with mock.patch("shutil.which", side_effect=_which("powershell")):
        assert config.SHELL == "powershell"
        assert get_current_shell() == "powershell"


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows_prefers_pwsh(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    with mock.patch("shutil.which", side_effect=_which("pwsh", "powershell")):
        assert get_current_shell() == "pwsh"


@mock.patch("platform.system", return_value="Windows")
def test_default_shell_windows_falls_back_to_cmd(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    # Neither pwsh nor powershell present -> cmd, which always exists on Windows.
    with mock.patch("shutil.which", side_effect=_which()):
        assert get_current_shell() == "cmd"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_zsh(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    config = Config()
    with mock.patch("shutil.which", side_effect=_which("zsh", "bash", "sh")):
        assert config.SHELL == "zsh"
        assert get_current_shell() == "zsh"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_bash(mock_platform_system, monkeypatch):
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/bash")
    config = Config()
    with mock.patch("shutil.which", side_effect=_which("bash", "sh")):
        assert config.SHELL == "bash"
        assert get_current_shell() == "bash"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_alpine_falls_back_to_sh(mock_platform_system, monkeypatch):
    # Alpine: $SHELL unset and bash not installed -> must resolve to sh, not bash.
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "")
    with mock.patch("shutil.which", side_effect=_which("sh")):
        assert get_current_shell() == "sh"


@mock.patch("platform.system", return_value="Linux")
def test_default_shell_zsh_requested_but_absent(mock_platform_system, monkeypatch):
    # $SHELL says zsh but it isn't installed -> fall back to an existing shell.
    monkeypatch.delenv("ZRB_SHELL", raising=False)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    with mock.patch("shutil.which", side_effect=_which("bash", "sh")):
        assert get_current_shell() == "bash"


def test_is_termux_detects_termux_version(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    monkeypatch.delenv("PREFIX", raising=False)
    assert is_termux() is True


def test_is_termux_detects_com_termux_prefix(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert is_termux() is True


def test_is_termux_false_off_termux(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setenv("PREFIX", "/usr/local")
    assert is_termux() is False


def test_cfg_is_termux_auto_detected(monkeypatch):
    monkeypatch.delenv("ZRB_IS_TERMUX", raising=False)
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    assert Config().IS_TERMUX is True


def test_cfg_is_termux_env_override_wins(monkeypatch):
    # Auto-detection says Termux, but an explicit override forces it off.
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    monkeypatch.setenv("ZRB_IS_TERMUX", "false")
    assert Config().IS_TERMUX is False


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
    monkeypatch.setenv("ZRB_INIT_MODULES", "module1,module2")
    config = Config()
    assert config.INIT_MODULES == ["module1", "module2"]


def test_init_modules_accepts_legacy_colon(monkeypatch):
    # Colon-separated values written before the comma convention still parse.
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


@mock.patch("importlib.metadata.version", return_value="1.2.3")
def test_banner(mock_version, monkeypatch):
    monkeypatch.setenv("ZRB_BANNER", "My Banner {VERSION}")
    config = Config()
    assert config.BANNER == "My Banner 1.2.3"


def test_config_properties_access():
    from zrb.config.config import CFG

    # Access all properties to boost coverage
    # LLM properties
    # _ = CFG.LLM_PROVIDER # Removed
    _ = CFG.LLM_MODEL
    _ = CFG.LLM_BASE_URL
    _ = CFG.LLM_API_KEY
    _ = CFG.LLM_MAX_REQUEST_PER_MINUTE
    _ = CFG.LLM_MAX_TOKEN_PER_MINUTE
    _ = CFG.LLM_MAX_TOKEN_PER_REQUEST
    _ = CFG.LLM_THROTTLE_SLEEP
    _ = CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD
    _ = CFG.LLM_HISTORY_SUMMARIZATION_WINDOW
    _ = CFG.LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
    _ = CFG.LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
    _ = CFG.LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
    _ = CFG.LLM_ASSISTANT_NAME
    _ = CFG.LLM_ASSISTANT_JARGON
    _ = CFG.LLM_ASSISTANT_ASCII_ART
    _ = CFG.LLM_PLUGIN_DIRS
    _ = CFG.LLM_SMALL_MODEL
    _ = CFG.LLM_HISTORY_DIR
    _ = CFG.LLM_JOURNAL_DIR
    _ = CFG.LLM_JOURNAL_INDEX_FILE

    # RAG properties
    _ = CFG.RAG_EMBEDDING_API_KEY
    _ = CFG.RAG_EMBEDDING_BASE_URL
    _ = CFG.RAG_EMBEDDING_MODEL
    _ = CFG.RAG_CHUNK_SIZE
    _ = CFG.RAG_OVERLAP
    _ = CFG.RAG_MAX_RESULT_COUNT

    # Web properties
    _ = CFG.WEB_CSS_PATH
    _ = CFG.WEB_JS_PATH
    _ = CFG.WEB_FAVICON_PATH
    _ = CFG.WEB_COLOR
    _ = CFG.WEB_HTTP_PORT
    _ = CFG.WEB_GUEST_USERNAME
    _ = CFG.WEB_SUPER_ADMIN_USERNAME
    _ = CFG.WEB_SUPER_ADMIN_PASSWORD
    _ = CFG.WEB_ACCESS_TOKEN_COOKIE_NAME
    _ = CFG.WEB_REFRESH_TOKEN_COOKIE_NAME
    _ = CFG.WEB_SECRET_KEY
    _ = CFG.WEB_AUTH_ENABLED
    _ = CFG.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES
    _ = CFG.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES
    _ = CFG.WEB_TITLE
    _ = CFG.WEB_JARGON
    _ = CFG.WEB_HOMEPAGE_INTRO

    # Other properties
    _ = CFG.ENV_PREFIX
    _ = CFG.DEFAULT_SHELL
    _ = CFG.DEFAULT_EDITOR
    _ = CFG.DIFF_EDIT_COMMAND_TPL
    _ = CFG.INIT_MODULES
    _ = CFG.INIT_SCRIPTS
    _ = CFG.INIT_FILE_NAME
    _ = CFG.ROOT_GROUP_NAME
    _ = CFG.ROOT_GROUP_DESCRIPTION
    _ = CFG.LOGGING_LEVEL
    _ = CFG.SESSION_LOG_DIR
    _ = CFG.TODO_DIR
    _ = CFG.TODO_VISUAL_FILTER
    _ = CFG.TODO_RETENTION
    _ = CFG.VERSION
    _ = CFG.BANNER
    _ = CFG.SERPAPI_KEY

    # UI Commands
    _ = CFG.LLM_UI_COMMAND_ATTACH
    # _ = CFG.LLM_UI_COMMAND_CLEAR_HISTORY # Removed
    _ = CFG.LLM_UI_COMMAND_EXIT
    _ = CFG.LLM_UI_COMMAND_LOAD
    _ = CFG.LLM_UI_COMMAND_YOLO_TOGGLE
    _ = CFG.LLM_UI_COMMAND_REDIRECT_OUTPUT
    _ = CFG.LLM_UI_COMMAND_EXEC
    _ = CFG.LLM_UI_COMMAND_SET_MODEL
