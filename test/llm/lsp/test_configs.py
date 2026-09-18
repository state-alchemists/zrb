from zrb.llm.lsp.configs import (
    LSPServerConfig,
    LSPServerConfigRegistry,
    detect_language_from_file,
    lsp_server_configs,
)


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


def test_detect_language_from_file():
    assert detect_language_from_file("script.py") == "python"
    assert detect_language_from_file("main.go") == "go"
    assert detect_language_from_file("index.ts") == "typescript"
    assert detect_language_from_file("unknown.ext") is None
    assert detect_language_from_file("no_extension") is None


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

    def test_detect_language_with_user_registered(self, lsp_on_path):
        lsp_on_path("my-lsp-server")

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
