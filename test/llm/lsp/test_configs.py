import os

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

    Cleared after as well, not just before: clearing only on the way in
    protects *these* tests from everyone else while leaking their own
    registrations -- and the ``_detected`` PATH scan they cache against a
    temporary ``$PATH`` -- into whichever unrelated test pytest-xdist runs next
    in this worker.
    """
    lsp_server_configs.clear()
    yield
    lsp_server_configs.clear()


@pytest.fixture
def lsp_on_path(tmp_path, monkeypatch):
    """Install real executable stubs on a ``$PATH`` holding only them.

    Detection probes the filesystem twice -- one listing per ``$PATH`` entry,
    then ``shutil.which`` on the survivors -- and real files are what keep both
    probes looking at the same world. Mocking only ``which`` would leave the
    listing reading the developer's actual ``$PATH``.

    Windows resolves a bare name only through ``PATHEXT``; ``.bat`` is in every
    default ``PATHEXT``, so the stub carries it there and no suffix elsewhere.
    Returned paths are ``normcase``-d, because the extension ``shutil.which``
    appends carries ``PATHEXT``'s casing rather than the file's.
    """

    def _install(*names: str) -> dict[str, str]:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        suffix = ".bat" if os.name == "nt" else ""
        installed = {}
        for name in names:
            executable = bin_dir / f"{name}{suffix}"
            executable.write_text("")
            executable.chmod(0o755)
            installed[name] = os.path.normcase(str(executable))
        monkeypatch.setenv("PATH", str(bin_dir))
        return installed

    return _install


@pytest.fixture
def probe_counter(monkeypatch):
    """Count how many ``$PATH`` directory listings detection has performed.

    The listing is the part that scales with ``$PATH``, so it is what the cache
    tests count. Counting ``shutil.which`` instead would be vacuous: a name
    absent from ``$PATH`` never reaches it.
    """
    calls = {"n": 0}
    real_listdir = os.listdir

    def counting_listdir(path):
        calls["n"] += 1
        return real_listdir(path)

    monkeypatch.setattr("zrb.llm.lsp.configs.os.listdir", counting_listdir)
    return lambda: calls["n"]


def normcased(detected: dict[str, str]) -> dict[str, str]:
    """Detection results keyed as :func:`lsp_on_path` reports them."""
    return {name: os.path.normcase(path) for name, path in detected.items()}


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


def test_detect_available_lsp_servers(lsp_on_path):
    # pyright's LSP server binary is `pyright-langserver`, not `pyright`
    # (the latter is the CLI type-checker). Detection keys off command[0].
    installed = lsp_on_path("pyright-langserver", "pylsp")

    available = detect_available_lsp_servers()

    assert normcased(available) == {
        "pyright": installed["pyright-langserver"],
        "pylsp": installed["pylsp"],
    }
    assert "jedi" not in available
    assert "gopls" not in available


def test_get_lsp_config_for_file(lsp_on_path):
    lsp_on_path("pyright-langserver", "gopls")

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


def test_get_lsp_config_for_file_with_preferred(lsp_on_path):
    lsp_on_path("pyright-langserver", "pylsp")

    # preferred server 'pylsp' should be chosen over 'pyright'
    config = get_lsp_config_for_file("script.py", preferred_servers=["pylsp"])
    assert config is not None
    assert config.name == "pylsp"

    # preferred server 'not_exist' is not available, should fallback to available ones
    config = get_lsp_config_for_file("script.py", preferred_servers=["not_exist"])
    assert config is not None
    assert config.name == "pyright" or config.name == "pylsp"


def test_detect_caches_the_path_scan(lsp_on_path, probe_counter):
    """The ``$PATH`` probe runs once, not on every call.

    ``get_for_file`` runs on every agent file edit via the post-write
    diagnostics, so an uncached probe would re-read every ``$PATH`` entry per
    edit.
    """
    lsp_on_path("pyright-langserver")
    registry = LSPServerConfigRegistry()

    registry.detect()
    after_first = probe_counter()
    registry.detect()
    registry.get_for_file("x.py")

    assert after_first > 0
    assert probe_counter() == after_first


def test_detect_cache_invalidated_by_register_and_clear(lsp_on_path, probe_counter):
    """A newly registered server must be visible immediately."""
    installed = lsp_on_path("custom-lsp")
    registry = LSPServerConfigRegistry()
    assert registry.detect() == {}
    baseline = probe_counter()

    registry.register(
        "custom",
        LSPServerConfig(
            name="custom",
            command=["custom-lsp"],
            language_ids=["custom"],
            file_extensions=[".cst"],
        ),
    )
    # Registering invalidates, so the new server resolves without a manual rescan.
    assert normcased(registry.detect()) == {"custom": installed["custom-lsp"]}
    assert probe_counter() > baseline

    after_register = probe_counter()
    registry.clear()
    assert registry.detect() == {}
    assert probe_counter() > after_register


def test_invalidate_detection_forces_a_rescan(lsp_on_path, probe_counter):
    """The documented escape hatch for the cache's staleness ceiling.

    A server installed mid-session is invisible until the probe re-runs; this is
    the only way to get it without re-registering a config.
    """
    lsp_on_path()  # empty $PATH: nothing installed yet
    registry = LSPServerConfigRegistry()
    assert registry.detect() == {}
    baseline = probe_counter()

    installed = lsp_on_path("pyright-langserver")  # installed mid-session
    assert registry.detect() == {}  # still cached, so still invisible
    assert probe_counter() == baseline

    registry.invalidate_detection()
    assert normcased(registry.detect()) == {
        "pyright": installed["pyright-langserver"]
    }
    assert probe_counter() > baseline


def test_detect_result_is_not_shared_mutable_state(lsp_on_path):
    """Callers get a copy — mutating the result must not poison the cache."""
    lsp_on_path()
    registry = LSPServerConfigRegistry()
    registry.detect()["injected"] = "/nope"
    assert "injected" not in registry.detect()


def test_an_empty_path_entry_means_the_working_directory(lsp_on_path, monkeypatch, tmp_path):
    """``shutil.which`` reads an empty ``$PATH`` entry as the working directory.

    A prefilter that skipped it would drop a server ``which`` goes on to
    resolve -- a false negative, which hides an installed server rather than
    costing a probe. (A ``$PATH`` that is entirely empty is a different case:
    ``which`` rejects it outright, so it is an empty *entry* here.)
    """
    lsp_on_path("custom-lsp")
    monkeypatch.chdir(tmp_path / "bin")
    monkeypatch.setenv("PATH", os.pathsep)
    registry = LSPServerConfigRegistry()
    registry.register(
        "custom",
        LSPServerConfig(
            name="custom",
            command=["custom-lsp"],
            language_ids=["custom"],
            file_extensions=[".cst"],
        ),
    )

    assert "custom" in registry.detect()


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

    def test_detect_with_user_registered(self, lsp_on_path):
        installed = lsp_on_path("my-lsp-server")

        custom = LSPServerConfig(
            name="my-lang-lsp",
            command=["my-lsp-server", "--stdio"],
            language_ids=["mylang"],
            file_extensions=[".my"],
        )
        self.registry.register("my-lang-lsp", custom)

        available = self.registry.detect()
        assert normcased(available) == {"my-lang-lsp": installed["my-lsp-server"]}

    def test_get_for_file_with_user_registered(self, lsp_on_path):
        lsp_on_path("my-lsp-server")

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

    def test_get_for_file_preferred_with_user_override(self, lsp_on_path):
        lsp_on_path("my-lsp-server", "pyright-langserver")

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
