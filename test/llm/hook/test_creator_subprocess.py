"""Command hook subprocess lifecycle: spawn, drain, timeout, kill, cancel.

Drives `zrb.llm.hook.process_io` and `zrb.llm.hook.process_kill` through their
only caller, `create_command_hook`. The exit-code and environment semantics live
in `test_creator.py`.
"""

import asyncio
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

import pytest

from zrb.llm.hook.creator import create_command_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import CommandHookConfig
from zrb.llm.hook.types import HookEvent

_PROCESS_STOP_TIMEOUT_SECONDS = 1.0
_PROCESS_STOP_POLL_SECONDS = 0.05


def _background_sleep_command(pid_path: str, *, exit_immediately: bool = False) -> str:
    """Start a long-lived child that records its own pid before sleeping."""
    script = (
        "from pathlib import Path; import os, time; "
        f"Path({pid_path!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} &"
    return f"{command} disown; exit 0" if exit_immediately else f"{command} wait"


def _started_chatter_command(ready_path: str) -> str:
    """Start a pipe-writing child that signals it is scheduled before the shell exits."""
    script = (
        "from pathlib import Path; import os; "
        f"Path({ready_path!r}).touch(); os.execvp('yes', ['yes', 'chatter'])"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} &"


def _process_is_live(pid: int) -> bool:
    """Whether *pid* exists and is not a zombie awaiting reaping."""
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
    )
    return result.returncode == 0 and not result.stdout.lstrip().startswith("Z")


async def _assert_recorded_process_stops(pid_path: str) -> None:
    """A killed child must not remain runnable after the hook returns."""
    attempts = int(_PROCESS_STOP_TIMEOUT_SECONDS / _PROCESS_STOP_POLL_SECONDS)
    pid: int | None = None
    for _ in range(attempts):
        if os.path.exists(pid_path):
            with open(pid_path) as file:
                pid = int(file.read())
            if not _process_is_live(pid):
                return
        await asyncio.sleep(_PROCESS_STOP_POLL_SECONDS)
    assert pid is None or not _process_is_live(
        pid
    ), "background descendant remained alive after hook cleanup"


class _StubProc:
    """A Popen stand-in that never exits until wait() is allowed to finish.

    No pipes: the reader has nothing to drain and falls straight through to
    wait(), which is where this fake's slowness lives.
    """

    returncode = None
    stdin = stdout = stderr = None

    def __init__(self, on_kill=None):
        self._on_kill = on_kill

    def poll(self):
        return None  # still running

    def wait(self):
        # Only has to outlast the 0.05-0.1s timeout/cancel below. The thread
        # running this is not cancellable, so keep it short — every second here
        # is a second a slow-hook assertion has to wait out.
        time.sleep(0.3)
        return 0

    def kill(self):
        if self._on_kill is not None:
            self._on_kill()


@pytest.mark.asyncio
async def test_command_hook_timeout_returns_clean_result():
    """A command hook that exceeds its timeout must be killed and reaped
    cleanly, returning a timeout HookResult.

    Regression: the kill path used ``await process.wait()`` on a sync
    ``subprocess.Popen``, whose ``.wait()`` returns an int — ``await``-ing it
    raised ``TypeError: 'int' object can't be awaited``, which swallowed the
    TimeoutError and left the subprocess unreaped.
    """
    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.1)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")
    # The bug surfaced as this message via the outer exception handler.
    assert "can't be awaited" not in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_timeout_kills_grandchildren_not_just_the_shell():
    """A timed-out hook must leave no surviving descendants.

    Regression: the timeout path called ``process.kill()``, which kills only the
    shell spawned by ``shell=True``. A forked grandchild survived it and — still
    holding the inherited stdout/stderr pipes — kept the reader blocked in its
    worker thread until it exited on its own, pinning a hook-pool worker for the
    full sleep. Leaked processes plus an exhausted pool.
    """
    # The work must be done by a *subshell*, not by the parent shell: a plain
    # `sleep; touch x` cannot tell the two kills apart, because `touch` is run by
    # the parent shell and is lost either way. Record the subshell's pid before
    # the parent waits, then assert that the process is not live after cleanup.
    # This avoids treating an event-loop pause longer than the child's sleep as a
    # false process-tree leak under a heavily parallel suite.
    with tempfile.TemporaryDirectory() as tmp:
        pid_path = os.path.join(tmp, "child.pid")
        hook = create_command_hook(
            CommandHookConfig(command=_background_sleep_command(pid_path)), timeout=0.1
        )
        context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

        result = await hook(context)

        assert result.success is False
        assert "timed out" in (result.output or "")
        await _assert_recorded_process_stops(pid_path)


@pytest.mark.asyncio
async def test_command_hook_returns_when_the_child_exits_not_at_pipe_eof():
    """A hook that backgrounds work and exits succeeds at once, keeping output.

    Regression: the reader was ``Popen.communicate``, which returns at pipe EOF.
    A disowned descendant inherits the stdout/stderr write ends, so EOF waited on
    the *descendant* rather than the hook — peon-ping's
    ``_run_sound_and_notify & disown``, the shape Claude-Code notifiers use,
    turned every firing into a false 10s timeout for a hook that had already
    succeeded in milliseconds.

    The descendant must be left running: backgrounding is the whole point of
    ``& disown``, and killing it would cut off the sound it exists to play.
    """
    with tempfile.TemporaryDirectory() as tmp:
        sentinel = os.path.join(tmp, "background-work-finished")
        hook = create_command_hook(
            CommandHookConfig(
                command=f"( sleep 1; touch {sentinel} ) & disown; echo ok; exit 0"
            ),
            timeout=10,
        )
        context = HookContext(event=HookEvent.SESSION_START, event_data={})

        started = time.monotonic()
        result = await hook(context)
        elapsed = time.monotonic() - started

        assert result.success is True
        assert (
            elapsed < 0.8
        ), f"waited on the descendant, not the child ({elapsed:.2f}s)"
        # The child's own output still arrives in full.
        assert result.modifications.get("additionalContext") == "ok"

        # Past the descendant's sleep: a successful hook's background work lives.
        await asyncio.sleep(1.3)
        assert os.path.exists(sentinel), "background work was killed off"


@pytest.mark.asyncio
async def test_command_hook_timeout_kills_descendants_of_a_shell_that_already_exited():
    """The group kill must reach descendants when the shell is already gone.

    Regression: the group was looked up with ``getpgid(pid)`` at kill time, but a
    shell that backgrounds work and exits is gone by then — the lookup raised
    ESRCH, the group kill was skipped, and the psutil fallback had no live pid to
    walk. The group is now captured at spawn, while its leader still lives.

    Forcing a genuine timeout here takes a *chatty* descendant: silence after the
    child exits is what ends the read, so a quiet descendant returns success
    instead (the test above). Both descendants share the spawned group, so one
    group kill must take out the chatter and the sentinel writer together.

    The chatter is ``yes``, not a ``sleep``-paced echo loop: the read side only
    needs *some* output inside every drain poll window (~50ms — see the
    reader's own poll-interval constant) to keep reading past the point where
    the shell itself has already exited. The shell waits for the chatter process
    to signal readiness before it exits, so a busy xdist worker cannot observe a
    quiet initial poll merely because that descendant has not been scheduled yet.
    The long-lived child records its pid, so the assertion checks its state after
    cleanup instead of depending on a delayed event loop noticing a short sleep.
    """
    with tempfile.TemporaryDirectory() as tmp:
        ready_path = os.path.join(tmp, "chatter-ready")
        pid_path = os.path.join(tmp, "child.pid")
        command = (
            f"{_started_chatter_command(ready_path)} disown; "
            f"while [ ! -f {shlex.quote(ready_path)} ]; do sleep 0.01; done; "
            f"{_background_sleep_command(pid_path, exit_immediately=True)}"
        )
        hook = create_command_hook(CommandHookConfig(command=command), timeout=0.3)
        context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

        result = await hook(context)

        assert result.success is False
        assert "timed out" in (result.output or "")
        await _assert_recorded_process_stops(pid_path)


@pytest.mark.asyncio
async def test_command_hook_timeout_process_already_gone():
    """If the timed-out process is already gone (ProcessLookupError on kill),
    the timeout path still returns cleanly."""

    def _raise_gone():
        raise ProcessLookupError()

    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.05)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch(
        "zrb.llm.hook.creator.subprocess.Popen",
        return_value=_StubProc(on_kill=_raise_gone),
    ):
        result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")


@pytest.mark.asyncio
async def test_command_hook_cancelled_kills_process():
    """Cancelling the awaiting task kills the subprocess and re-raises."""
    killed = {"done": False}

    def _mark_killed():
        killed["done"] = True

    hook = create_command_hook(CommandHookConfig(command="sleep 5"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch(
        "zrb.llm.hook.creator.subprocess.Popen",
        return_value=_StubProc(on_kill=_mark_killed),
    ):
        task = asyncio.ensure_future(hook(context))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert killed["done"] is True


@pytest.mark.asyncio
async def test_command_hook_cancelled_when_process_already_gone():
    """If the subprocess is already gone when cancellation fires, the
    ProcessLookupError on kill is swallowed and CancelledError still propagates."""

    def _raise_gone():
        raise ProcessLookupError()

    hook = create_command_hook(CommandHookConfig(command="sleep 5"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch(
        "zrb.llm.hook.creator.subprocess.Popen",
        return_value=_StubProc(on_kill=_raise_gone),
    ):
        task = asyncio.ensure_future(hook(context))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_command_hook_outer_exception_is_caught(caplog):
    """An unexpected error while spawning the subprocess is caught and returned
    as a failed HookResult."""
    hook = create_command_hook(CommandHookConfig(command="echo hi"))
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch(
        "zrb.llm.hook.creator.subprocess.Popen",
        side_effect=OSError("spawn failed"),
    ):
        with caplog.at_level(logging.ERROR, logger="zrb.llm.hook.creator"):
            result = await hook(context)

    assert result.success is False
    assert "spawn failed" in (result.output or "")
