"""Probes in a delegated worktree must not run that worktree's configured programs."""

import asyncio

import pytest

from zrb.llm.capabilities.tool.delegate.runner import worktree_has_changes

_WORKTREE = "/repo/.zrb/worktree/delegate-x"


@pytest.mark.asyncio
async def test_status_probe_disables_fsmonitor_and_hooks(monkeypatch):
    """A worktree is a model-chosen directory: its `.git/config` can name a
    program git runs for us, so both settings are forced off for the probe."""
    calls = []

    class _Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_exec(*argv, **kwargs):
        calls.append((argv, kwargs))
        return _Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    assert await worktree_has_changes(_WORKTREE) is False

    argv, kwargs = calls[0]
    assert argv[0] == "git"
    assert "core.fsmonitor=false" in argv
    assert "core.hooksPath=/dev/null" in argv
    assert argv.index("-c") < argv.index("status")
    assert kwargs["cwd"] == _WORKTREE
