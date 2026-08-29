"""Tests for BaseUISystemInfo (cwd + git status tracking for the chat UI)."""

import asyncio
import os
import signal
import subprocess

import pytest

from zrb.llm.ui.base.system_info import BaseUISystemInfo, communicate_or_reap


class FakeBaseUI:
    """Composes BaseUISystemInfo the same way production `BaseUI` does."""

    def __init__(self):
        self.cwd = ""
        self.git_info = ""
        self.invalidate_count = 0
        # Test-only public handle to the part under test.
        self.system_info = BaseUISystemInfo(self)

    def invalidate_ui(self):
        self.invalidate_count += 1

    async def update_system_info(self):
        await self.system_info.update_system_info()


@pytest.fixture
def ui():
    return FakeBaseUI()


def _init_repo(tmp_path, dirty=False):
    def git(*args):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args], check=True, capture_output=True
        )

    subprocess.run(
        ["git", "init", "-q", str(tmp_path)], check=True, capture_output=True
    )
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "file.txt").write_text("hello\n")
    git("add", ".")
    git("commit", "-qm", "init")
    if dirty:
        (tmp_path / "file.txt").write_text("changed\n")


def test_get_cwd_display_abbreviates_home(ui, monkeypatch):
    home = "/home/tester"
    monkeypatch.setattr("os.getcwd", lambda: f"{home}/projects/zrb")
    monkeypatch.setattr("os.path.expanduser", lambda _: home)
    assert ui.system_info.get_cwd_display() == "~/projects/zrb"


def test_get_cwd_display_keeps_non_home_path(ui, monkeypatch):
    monkeypatch.setattr("os.getcwd", lambda: "/var/log")
    monkeypatch.setattr("os.path.expanduser", lambda _: "/home/tester")
    assert ui.system_info.get_cwd_display() == "/var/log"


@pytest.mark.asyncio
async def test_get_git_info_clean_repo(ui, tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    branch, status = await ui.system_info.get_git_info()
    assert branch in ("main", "master")
    assert status == ""


@pytest.mark.asyncio
async def test_get_git_info_dirty_repo(ui, tmp_path, monkeypatch):
    _init_repo(tmp_path, dirty=True)
    monkeypatch.chdir(tmp_path)
    branch, status = await ui.system_info.get_git_info()
    assert branch in ("main", "master")
    assert status == "*"


@pytest.mark.asyncio
async def test_get_git_info_outside_repo_returns_empty(ui, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    branch, status = await ui.system_info.get_git_info()
    assert branch == ""
    assert status == ""


@pytest.mark.asyncio
async def test_update_system_info_sets_ui_state(ui):
    await ui.update_system_info()
    assert ui.cwd == ui.system_info.get_cwd_display()
    assert isinstance(ui.git_info, str)
    assert ui.invalidate_count == 1


@pytest.mark.asyncio
async def test_update_system_info_loop_stops_on_cancellation(ui, monkeypatch):
    calls = 0

    async def explode_after_first():
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError()

    # Keep the inter-tick sleep at zero so the second call happens immediately.
    monkeypatch.setattr(
        "zrb.config.config.CFG.LLM_UI_LONG_STATUS_INTERVAL", 0, raising=False
    )
    ui.update_system_info = explode_after_first
    await asyncio.wait_for(ui.system_info.update_system_info_loop(), timeout=5)
    assert calls == 2


@pytest.mark.asyncio
async def test_update_system_info_reports_non_repo(ui, tmp_path, monkeypatch):
    """Outside a git repo the indicator says so instead of showing an empty branch."""
    monkeypatch.chdir(tmp_path)
    await ui.update_system_info()
    assert ui.git_info == "Not a git repo"
    assert ui.invalidate_count == 1


@pytest.mark.asyncio
async def test_get_git_info_swallows_spawn_failure(ui, monkeypatch):
    """A missing/unusable git binary degrades to empty info, not a crash."""

    def broken_exec(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(
        "zrb.llm.ui.base.system_info.asyncio.create_subprocess_exec", broken_exec
    )
    branch, status = await ui.system_info.get_git_info()
    assert (branch, status) == ("", "")


@pytest.mark.asyncio
async def test_update_system_info_loop_survives_transient_errors(ui, monkeypatch):
    """A failing refresh logs at debug and keeps looping until cancelled."""
    from zrb.config.config import CFG

    calls = 0

    async def flaky_update():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("transient")

    monkeypatch.setattr(CFG, "LLM_UI_LONG_STATUS_INTERVAL", 0, raising=False)
    ui.update_system_info = flaky_update

    task = asyncio.ensure_future(ui.system_info.update_system_info_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls >= 2


@pytest.mark.asyncio
async def test_communicate_or_reap_terminates_child_on_cancellation():
    proc = await asyncio.create_subprocess_exec(
        "sleep", "30", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    task = asyncio.ensure_future(communicate_or_reap(proc))
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_communicate_or_reap_kills_child_when_terminate_fails():
    """If terminate fails during cancellation unwind, the child is still killed
    (and a failing kill is tolerated) so nothing is left running."""
    proc = await asyncio.create_subprocess_exec(
        "sleep", "30", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    real_terminate = proc.terminate

    def flaky_terminate():
        real_terminate()
        raise BaseException("terminate raced shutdown")  # noqa: B036

    def flaky_kill():
        # Really kill the child (so the reap below succeeds) but still raise,
        # as a kill racing an already-dead process would.
        os.kill(proc.pid, signal.SIGKILL)
        raise ProcessLookupError("already gone")

    proc.terminate = flaky_terminate
    proc.kill = flaky_kill
    task = asyncio.ensure_future(communicate_or_reap(proc))
    await asyncio.sleep(0.1)
    task.cancel()
    # The kill-fallback failure must not swallow the cancellation.
    with pytest.raises(asyncio.CancelledError):
        await task
