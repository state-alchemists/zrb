"""zrb's own git probes must not run a repository's configured programs."""

import os
import subprocess

from zrb.llm.capabilities.tool.git_visible import git_visible_files


def _capture_run(monkeypatch, calls, stdout=b""):
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return completed

    monkeypatch.setattr(
        "zrb.llm.capabilities.tool.git_visible.subprocess.run", fake_run
    )


def test_ls_files_probe_disables_fsmonitor_and_hooks(monkeypatch):
    """The probe reads a model-chosen directory, whose config zrb did not write.

    `core.fsmonitor` names a program git runs, and a hooks path names more; a
    repository can therefore make `git ls-files` execute code. Both are forced
    off before the subcommand, and `-C` still tells git which tree to probe.
    """
    calls = []
    _capture_run(monkeypatch, calls, stdout=b"a.py\x00sub/b.py\x00")

    assert git_visible_files("/repo") == {"a.py", os.path.join("sub", "b.py")}

    argv, _ = calls[0]
    assert argv[:3] == ["git", "-C", "/repo"]
    assert "core.fsmonitor=false" in argv
    assert "core.hooksPath=/dev/null" in argv
    assert argv.index("-c") < argv.index("ls-files")
