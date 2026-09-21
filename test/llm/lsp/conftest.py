"""Shared stubs for the LSP config tests.

Detection reads the real filesystem twice -- one listing per ``$PATH``
entry, then ``shutil.which`` on the survivors -- so both test modules need
the same executable stubs and the same probe counters.
"""

import os
import shutil

import pytest

from zrb.llm.lsp.configs import lsp_server_configs


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


@pytest.fixture
def which_counter(monkeypatch):
    """Count the resolver calls the prefilter did not avoid.

    The listing count says how hard the prefilter worked; this says how much it
    saved, which is the only observable difference between filtering and
    passing everything through.
    """
    calls = {"n": 0}
    real_which = shutil.which

    def counting_which(cmd, *args, **kwargs):
        calls["n"] += 1
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr("zrb.llm.lsp.configs.shutil.which", counting_which)
    return lambda: calls["n"]
