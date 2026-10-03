"""The shell tool under a sandbox policy: refusals, and what may be written."""

import os
import shutil

import pytest

from zrb.llm.sandbox import SandboxPolicy
from zrb.llm.sandbox.os_sandbox import SandboxUnavailableError
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool.shell import run_shell_command


@pytest.mark.asyncio
async def test_run_shell_command_background_sandbox_refused(monkeypatch):
    # When the background registry refuses on sandbox policy, the tool relays a
    # sandbox-policy refusal instead of a handle.
    class _RefusingRegistry:
        async def start(self, *args, **kwargs):
            raise SandboxUnavailableError("no sandbox here")

    monkeypatch.setattr(
        "zrb.llm.tool.shell_background.get_shell_background_registry",
        lambda: _RefusingRegistry(),
    )
    res = await run_shell_command("sleep 1", background=True)
    assert "refused by sandbox policy" in res
    assert "no sandbox here" in res
    assert "Handle:" not in res


@pytest.mark.asyncio
async def test_run_shell_command_foreground_sandbox_deny(monkeypatch):
    # A deny-mode sandbox raises while building the argv; the tool relays the
    # refusal and still cleans up the temp PID file (even if removal fails).
    def _deny(*args, **kwargs):
        raise SandboxUnavailableError("deny mode")

    def _boom(*args, **kwargs):
        raise OSError("cannot remove")

    monkeypatch.setattr("zrb.llm.sandbox.build_sandboxed_argv", _deny)
    monkeypatch.setattr(shell_mod.os, "remove", _boom)
    res = await run_shell_command("echo hi")
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_run_shell_command_cwd_does_not_widen_the_sandbox(monkeypatch, tmp_path):
    # The model chooses `cwd`. With automatic writable roots it must not become
    # one, or `cwd="/"` makes the whole filesystem writable inside bwrap.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        shell_mod,
        "get_effective_sandbox_policy",
        lambda: SandboxPolicy(enabled=True),
    )
    monkeypatch.setattr("platform.system", lambda: "Linux")
    real_which = shutil.which
    monkeypatch.setattr(
        "shutil.which",
        lambda name, *a, **k: "/usr/bin/bwrap" if name == "bwrap" else real_which(name),
    )
    spawned: list[list[str]] = []

    async def _capture(argv, cwd):
        spawned.append(argv)
        raise OSError("not spawning in a test")

    monkeypatch.setattr(shell_mod, "start_process", _capture)
    await run_shell_command("touch /etc/owned", cwd="/")

    argv = spawned[0]
    binds = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--bind"]
    assert "/" not in binds
    assert os.path.realpath(tmp_path) in binds
