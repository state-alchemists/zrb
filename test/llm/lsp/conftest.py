'Shared executable stubs and probe counters for the LSP config tests.'

import os
import shutil

import pytest

from zrb.llm.lsp.configs import lsp_server_configs


@pytest.fixture(autouse=True)
def _cleanup_global_registry():
    'Clear the shared registry (and its cached PATH scan) before and after each test.'
    lsp_server_configs.clear()
    yield
    lsp_server_configs.clear()


@pytest.fixture
def lsp_on_path(tmp_path, monkeypatch):
    'Install real executable stubs on a ``$PATH`` holding only them.'

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
    'Count the ``$PATH`` directory listings detection has performed.'
    calls = {"n": 0}
    real_listdir = os.listdir

    def counting_listdir(path):
        calls["n"] += 1
        return real_listdir(path)

    monkeypatch.setattr("zrb.llm.lsp.configs.os.listdir", counting_listdir)
    return lambda: calls["n"]


@pytest.fixture
def which_counter(monkeypatch):
    'Count the ``shutil.which`` calls the prefilter did not avoid.'
    calls = {"n": 0}
    real_which = shutil.which

    def counting_which(cmd, *args, **kwargs):
        calls["n"] += 1
        return real_which(cmd, *args, **kwargs)

    monkeypatch.setattr("zrb.llm.lsp.configs.shutil.which", counting_which)
    return lambda: calls["n"]
