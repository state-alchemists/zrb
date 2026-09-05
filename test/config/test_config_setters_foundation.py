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

    def test_enable_builtin_tasks_setter_true(self, monkeypatch):
        # Renamed from LOAD_BUILTIN (ADR-0026) — clean break, old name is
        # no longer read.
        config = Config()
        config.ENABLE_BUILTIN_TASKS = True
        assert os.environ["ZRB_ENABLE_BUILTIN_TASKS"] == "on"

    def test_enable_builtin_tasks_setter_false(self, monkeypatch):
        config = Config()
        config.ENABLE_BUILTIN_TASKS = False
        assert os.environ["ZRB_ENABLE_BUILTIN_TASKS"] == "off"

    def test_show_unrecommended_command_warning_setter(self, monkeypatch):
        # Renamed from WARN_UNRECOMMENDED_COMMAND (ADR-0026).
        config = Config()
        config.SHOW_UNRECOMMENDED_COMMAND_WARNING = True
        assert os.environ["ZRB_SHOW_UNRECOMMENDED_COMMAND_WARNING"] == "on"

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

    def test_ascii_art_dir_setter(self, monkeypatch):
        config = Config()
        config.ASCII_ART_DIR = "/tmp/ascii"
        assert os.environ["ZRB_ASCII_ART_DIR"] == "/tmp/ascii"

    def test_banner_setter(self, monkeypatch):
        config = Config()
        config.BANNER = "Custom Banner"
        assert os.environ["ZRB_BANNER"] == "Custom Banner"
