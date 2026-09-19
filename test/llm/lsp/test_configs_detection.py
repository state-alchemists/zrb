"""Which LSP servers detection finds, and where it looks for them.

``detect()`` resolves a configured command against ``$PATH`` in two steps: a
listing per directory, then ``shutil.which`` on whatever survives. These
tests pin what each step may rule out, since anything the first step drops
never reaches the second to be resolved.
"""

import os

import pytest

from zrb.llm.lsp.configs import (
    LSPServerConfig,
    LSPServerConfigRegistry,
    detect_available_lsp_servers,
    get_lsp_config_for_file,
)


def normcased(detected: dict[str, str]) -> dict[str, str]:
    """Detection results keyed as :func:`lsp_on_path` reports them.

    ``shutil.which`` appends the extension with ``PATHEXT``'s casing rather
    than the file's, so a Windows path comes back spelled differently.
    """
    return {name: os.path.normcase(path) for name, path in detected.items()}


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
    assert normcased(registry.detect()) == {"pyright": installed["pyright-langserver"]}
    assert probe_counter() > baseline


def test_detect_result_is_not_shared_mutable_state(lsp_on_path):
    """Callers get a copy — mutating the result must not poison the cache."""
    lsp_on_path()
    registry = LSPServerConfigRegistry()
    registry.detect()["injected"] = "/nope"
    assert "injected" not in registry.detect()


def test_an_empty_path_entry_means_the_working_directory(
    lsp_on_path, monkeypatch, tmp_path
):
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


def test_a_path_qualified_command_bypasses_the_path_prefilter(tmp_path, monkeypatch):
    """A command naming its own directory resolves against that directory, so no
    ``$PATH`` listing can vouch for it -- and the registry documents custom
    servers, which is where an absolute path shows up."""
    elsewhere = tmp_path / "opt"
    elsewhere.mkdir()
    suffix = ".bat" if os.name == "nt" else ""
    executable = elsewhere / f"custom-lsp{suffix}"
    executable.write_text("")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    registry = LSPServerConfigRegistry()
    registry.register(
        "custom",
        LSPServerConfig(
            name="custom",
            command=[str(executable)],
            language_ids=["custom"],
            file_extensions=[".cst"],
        ),
    )

    assert normcased(registry.detect()) == {"custom": os.path.normcase(str(executable))}


@pytest.mark.parametrize("through", ["confstr", "defpath"])
def test_an_unset_path_falls_back_the_way_which_does(lsp_on_path, monkeypatch, through):
    """No ``$PATH`` is not "nowhere": ``shutil.which`` falls back to ``CS_PATH``
    or ``os.defpath``, so a server in ``/usr/bin`` still resolves. A prefilter
    that read a missing ``$PATH`` as the working directory would hide it.

    Either default alone has to be enough. ``shutil.which`` reads ``CS_PATH``
    first and ``os.defpath`` only where that is unavailable, while its
    documentation names ``os.defpath`` alone -- so honouring one of them is a
    false negative on any system where they differ.

    The fallbacks are steered rather than mocked out, because ``which`` reads
    them from the same ``os`` module this does, which keeps prefilter and
    resolver looking at one world.
    """
    installed = lsp_on_path("custom-lsp")
    fallback = os.path.dirname(installed["custom-lsp"])

    def confstr(name):
        if through == "confstr":
            return fallback
        raise ValueError("CS_PATH is not available here")

    monkeypatch.delenv("PATH")
    monkeypatch.setattr(os, "confstr", confstr, raising=False)
    monkeypatch.setattr(os, "defpath", fallback if through == "defpath" else "")

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

    assert normcased(registry.detect()) == {"custom": installed["custom-lsp"]}


@pytest.mark.parametrize(
    "refusal",
    [
        PermissionError(13, "Permission denied"),
        OSError(5, "Input/output error"),
    ],
)
def test_a_directory_that_cannot_be_listed_is_not_a_negative(
    lsp_on_path, monkeypatch, refusal
):
    """A directory can be searchable without being readable.

    ``which`` stats the one name it wants and resolves it; a listing is refused
    outright. Reading that refusal as "nothing here" hides an installed server,
    so the prefilter drops out instead and lets every name through.
    """
    installed = lsp_on_path("custom-lsp")

    def refuse(path):
        raise refusal

    monkeypatch.setattr("zrb.llm.lsp.configs.os.listdir", refuse)
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

    assert normcased(registry.detect()) == {"custom": installed["custom-lsp"]}


def test_a_missing_path_directory_does_not_disable_the_prefilter(
    lsp_on_path, monkeypatch, tmp_path, which_counter
):
    """``$PATH`` routinely names directories that are not there.

    ``which`` stats a name under one and fails just as a listing does, so it is
    a real negative. Reading it as "could not be read" instead would hand every
    configured server to the resolver -- the O(servers x $PATH) cost this exists
    to remove.
    """
    installed = lsp_on_path("custom-lsp")
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join(
            [str(tmp_path / "gone"), os.path.dirname(installed["custom-lsp"])]
        ),
    )
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

    assert normcased(registry.detect()) == {"custom": installed["custom-lsp"]}
    assert which_counter() == 1


class TestLSPServerConfigRegistryDetection:
    """Detection through a registry carrying user-registered servers."""

    def setup_method(self):
        self.registry = LSPServerConfigRegistry()

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
