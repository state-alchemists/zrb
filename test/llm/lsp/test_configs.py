from unittest.mock import patch

import pytest

from zrb.llm.lsp.configs import (
    LSPServerConfig,
    LSPServerConfigRegistry,
    detect_available_lsp_servers,
    detect_language_from_file,
    get_lsp_config_for_file,
    lsp_server_configs,
)


@pytest.fixture(autouse=True)
def _cleanup_global_registry():
    """Clear any user-registered entries from the global singleton.

    Tests in other modules (e.g. ``test_lsp_manager.py``) may call
    ``register_lsp_server`` on the shared singleton. Clearing before
    each test here keeps delegation tests deterministic.
    """
    lsp_server_configs.clear()


def test_matches_file():
    config = LSPServerConfig(
        name="test_server",
        command=["test_server"],
        language_ids=["testlang"],
        file_extensions=[".test", ".tst"],
    )
    assert config.matches_file("myfile.test") is True
    assert config.matches_file("myfile.tst") is True
    assert config.matches_file("myfile.txt") is False
    assert config.matches_file("no_extension") is False


@patch("shutil.which")
def test_detect_available_lsp_servers(mock_which):
    def which_side_effect(cmd):
        # pyright's LSP server binary is `pyright-langserver`, not `pyright`
        # (the latter is the CLI type-checker). Detection keys off command[0].
        if cmd == "pyright-langserver":
            return "/usr/bin/pyright-langserver"
        if cmd == "pylsp":
            return "/usr/bin/pylsp"
        return None

    mock_which.side_effect = which_side_effect

    available = detect_available_lsp_servers()

    assert "pyright" in available
    assert available["pyright"] == "/usr/bin/pyright-langserver"
    assert "pylsp" in available
    assert available["pylsp"] == "/usr/bin/pylsp"
    assert "jedi" not in available
    assert "gopls" not in available


@patch("shutil.which")
def test_get_lsp_config_for_file(mock_which):
    def which_side_effect(cmd):
        if cmd == "pyright-langserver":
            return "/usr/bin/pyright-langserver"
        if cmd == "gopls":
            return "/usr/bin/gopls"
        return None

    mock_which.side_effect = which_side_effect

    # Test file matches pyright
    config = get_lsp_config_for_file("script.py")
    assert config is not None
    assert config.name == "pyright"

    # Test file matches gopls
    config = get_lsp_config_for_file("main.go")
    assert config is not None
    assert config.name == "gopls"

    # Test file doesn't match any available server
    config = get_lsp_config_for_file("style.css")
    assert config is None


@patch("shutil.which")
def test_get_lsp_config_for_file_with_preferred(mock_which):
    def which_side_effect(cmd):
        if cmd == "pyright-langserver":
            return "/usr/bin/pyright-langserver"
        if cmd == "pylsp":
            return "/usr/bin/pylsp"
        return None

    mock_which.side_effect = which_side_effect

    # preferred server 'pylsp' should be chosen over 'pyright'
    config = get_lsp_config_for_file("script.py", preferred_servers=["pylsp"])
    assert config is not None
    assert config.name == "pylsp"

    # preferred server 'not_exist' is not available, should fallback to available ones
    config = get_lsp_config_for_file("script.py", preferred_servers=["not_exist"])
    assert config is not None
    assert config.name == "pyright" or config.name == "pylsp"


def test_detect_language_from_file():
    assert detect_language_from_file("script.py") == "python"
    assert detect_language_from_file("main.go") == "go"
    assert detect_language_from_file("index.ts") == "typescript"
    assert detect_language_from_file("unknown.ext") is None
    assert detect_language_from_file("no_extension") is None


# ── LSPServerConfigRegistry tests -------------------------------------------


class TestLSPServerConfigRegistry:
    """Test the user-extensible registry."""

    def setup_method(self):
        self.registry = LSPServerConfigRegistry()

    def test_get_returns_builtin(self):
        config = self.registry.get("pyright")
        assert config is not None
        assert config.name == "pyright"

    def test_get_returns_none_for_unknown(self):
        assert self.registry.get("nonexistent-lsp") is None

    def test_register_overrides_builtin(self):
        override = LSPServerConfig(
            name="pyright-override",
            command=["custom-pyright"],
            language_ids=["python"],
            file_extensions=[".py"],
        )
        self.registry.register("pyright", override)
        config = self.registry.get("pyright")
        assert config is not None
        assert config.name == "pyright-override"
        assert config.command == ["custom-pyright"]

    def test_register_adds_new_server(self):
        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["mylang"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lang-lsp", custom)
        config = self.registry.get("my-lang-lsp")
        assert config is not None
        assert config.name == "my-lang-lsp"

    def test_all_includes_builtin_and_overrides(self):
        custom = LSPServerConfig(
            name="custom-lsp",
            command=["custom"],
            language_ids=["cust"],
            file_extensions=[".cust"],
        )
        self.registry.register("custom-lsp", custom)
        all_configs = self.registry.all()
        assert "pyright" in all_configs  # built-in
        assert "custom-lsp" in all_configs  # user-registered
        assert all_configs["custom-lsp"].name == "custom-lsp"

    def test_override_appears_in_all_list(self):
        override = LSPServerConfig(
            name="patched-pyright",
            command=["patched-pyright"],
            language_ids=["python"],
            file_extensions=[".py"],
        )
        self.registry.register("pyright", override)
        all_configs = self.registry.all()
        assert all_configs["pyright"].command == ["patched-pyright"]

    def test_clear_drops_user_entries(self):
        custom = LSPServerConfig(
            name="my-lsp",
            command=["my-lsp"],
            language_ids=["my"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lsp", custom)
        self.registry.clear()
        assert self.registry.get("my-lsp") is None
        # Built-in unaffected
        assert self.registry.get("pyright") is not None

    def test_all_is_detached_copy(self):
        """Mutating the returned dict must not affect the registry."""
        result = self.registry.all()
        result.clear()
        assert self.registry.get("pyright") is not None

    @patch("shutil.which")
    def test_detect_with_user_registered(self, mock_which):
        def which_side_effect(cmd):
            if cmd == "my-lsp-server":
                return "/usr/bin/my-lsp-server"
            return None

        mock_which.side_effect = which_side_effect

        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["mylang"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lang-lsp", custom)

        available = self.registry.detect()
        assert "my-lang-lsp" in available
        assert available["my-lang-lsp"] == "/usr/bin/my-lsp-server"

    @patch("shutil.which")
    def test_get_for_file_with_user_registered(self, mock_which):
        def which_side_effect(cmd):
            if cmd == "my-lsp-server":
                return "/usr/bin/my-lsp-server"
            return None

        mock_which.side_effect = which_side_effect

        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["mylang"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lang-lsp", custom)

        config = self.registry.get_for_file("source.my")
        assert config is not None
        assert config.name == "my-lang-lsp"

        config = self.registry.get_for_file("other.py")
        assert config is None

    @patch("shutil.which")
    def test_get_for_file_preferred_with_user_override(self, mock_which):
        def which_side_effect(cmd):
            if cmd == "my-lsp-server":
                return "/usr/bin/my-lsp-server"
            if cmd == "pyright-langserver":
                return "/usr/bin/pyright-langserver"
            return None

        mock_which.side_effect = which_side_effect

        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["python"],
            file_extensions=[".py"],
        )
        self.registry.register("my-lang-lsp", custom)

        config = self.registry.get_for_file(
            "script.py", preferred_servers=["my-lang-lsp"]
        )
        assert config is not None
        assert config.name == "my-lang-lsp"

    @patch("shutil.which")
    def test_detect_language_with_user_registered(self, mock_which):
        mock_which.return_value = "/usr/bin/my-lsp-server"

        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["mylang"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lang-lsp", custom)

        lang = self.registry.detect_language("source.my")
        assert lang == "mylang"

    def test_lsp_server_configs_singleton_is_registry_instance(self):
        assert isinstance(lsp_server_configs, LSPServerConfigRegistry)
