"""The shell tool under a sandbox policy: refusals, and what may be written."""

import os
import shutil

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.sandbox import SandboxPolicy
from zrb.llm.capabilities.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
)
from zrb.llm.capabilities.tool.shell import command as shell_mod
from zrb.llm.capabilities.tool.shell import run_shell_command


@pytest.mark.asyncio
async def test_run_shell_command_background_sandbox_refused(monkeypatch):
    # When the background registry refuses on sandbox policy, the tool relays a
    # sandbox-policy refusal instead of a handle.
    class _RefusingRegistry:
        async def start(self, *args, **kwargs):
            raise SandboxUnavailableError("no sandbox here")

    monkeypatch.setattr(
        "zrb.llm.capabilities.tool.shell.background.get_shell_background_registry",
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

    monkeypatch.setattr("zrb.llm.capabilities.sandbox.build_sandboxed_argv", _deny)
    monkeypatch.setattr(shell_mod.os, "remove", _boom)
    res = await run_shell_command("echo hi")
    assert "refused by sandbox policy" in res
    assert "deny mode" in res


@pytest.mark.asyncio
async def test_foreground_refusal_is_the_shared_message_plus_the_file_tool_hint(
    monkeypatch,
):
    def _deny(*args, **kwargs):
        raise SandboxUnavailableError("deny mode")

    monkeypatch.setattr("zrb.llm.capabilities.sandbox.build_sandboxed_argv", _deny)
    res = await run_shell_command("echo hi")
    shared = format_sandbox_denied_message(SandboxUnavailableError("deny mode"))
    assert res == (
        f"{shared} Use the in-process file tools instead, or ask the user to "
        "adjust the sandbox configuration."
    )


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


@pytest.mark.asyncio
async def test_background_shell_is_refused_in_a_private_pid_namespace(monkeypatch):
    """The sandbox's processes die with it and its PIDs are not host PIDs, so a
    background handle could neither track nor kill one."""
    started = []

    class _Registry:
        async def start(self, *args, **kwargs):
            started.append((args, kwargs))
            return "a-handle"

    monkeypatch.setattr(
        "zrb.llm.capabilities.tool.shell.background.get_shell_background_registry",
        lambda: _Registry(),
    )
    monkeypatch.setattr(
        shell_mod, "has_private_pid_namespace", lambda policy, skip=False: True
    )

    result = await run_shell_command("sleep 1", background=True)

    assert "PID namespace" in result
    assert "foreground" in result
    assert f"{CFG.ENV_PREFIX}_LLM_SANDBOX_OS_SHELL=off" in result
    assert "Handle:" not in result
    assert started == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell syntax")
@pytest.mark.asyncio
async def test_private_pid_namespace_hides_background_pids(monkeypatch):
    """A namespace-local PID is not a host PID, so reporting it would let the
    model signal an unrelated process."""
    monkeypatch.setattr(
        shell_mod, "has_private_pid_namespace", lambda policy, skip=False: True
    )

    result = await run_shell_command("sleep 1 & echo started")

    assert "started" in result
    assert "Background PIDs: (none)" in result
