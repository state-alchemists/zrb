"""Snapshot git commands: bounded by a deadline, isolated from the caller's
git environment, and cancellable."""

import asyncio
import subprocess
import threading
import time

import pytest

from zrb.util.git.snapshot_command import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    SnapshotError,
    get_clean_env,
    get_command_timeout,
    run_git_command,
    run_in_worker,
)


def test_command_timeout_is_capped_and_shrinks_toward_the_deadline():
    assert get_command_timeout(None) == GIT_COMMAND_TIMEOUT_SECONDS
    assert get_command_timeout(time.monotonic() + 3600) == GIT_COMMAND_TIMEOUT_SECONDS
    assert 0 < get_command_timeout(time.monotonic() + 5) <= 5
    assert get_command_timeout(time.monotonic() - 1) <= 0


def test_a_command_past_its_timeout_is_reported_by_its_label(monkeypatch):
    def run(argv, *args, **kwargs):
        raise subprocess.TimeoutExpired(argv, GIT_COMMAND_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(SnapshotError, match=r"^git update-index timed out after 30s$"):
        run_git_command(["git", "-c", "x=y"], None, label="git update-index")


def test_a_passed_deadline_runs_no_command(tmp_path):
    with pytest.raises(SnapshotError, match="^No time left to run git status$"):
        run_git_command(["git", "status"], str(tmp_path), time.monotonic() - 1)


def test_redirecting_git_variables_are_not_inherited(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/elsewhere")
    monkeypatch.setenv("GIT_INDEX_FILE", "/elsewhere/index")
    monkeypatch.setenv("HOME", "/home/kept")

    env = get_clean_env()

    assert "GIT_DIR" not in env and "GIT_INDEX_FILE" not in env
    assert env["HOME"] == "/home/kept"


@pytest.mark.asyncio
async def test_a_cancelled_worker_stops_before_its_next_command_and_is_awaited(
    tmp_path,
):
    started, release = threading.Event(), threading.Event()
    ran: list[str] = []

    def work():
        started.set()
        release.wait(5)
        try:
            run_git_command(["git", "--version"], str(tmp_path))
            ran.append("git")
        except SnapshotError as e:
            ran.append(str(e))

    task = asyncio.ensure_future(run_in_worker(work))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0.05)
    still_waiting = not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert still_waiting
    assert ran == ["Snapshot cancelled before running git --version"]
