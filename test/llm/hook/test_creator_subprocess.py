'Command-hook subprocess lifecycle tests.'

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


posix_shell_only = pytest.mark.skipif(
    os.name != "posix",
    reason="drives a POSIX shell script; cmd.exe does not share the syntax",
)

_PROCESS_STOP_TIMEOUT_SECONDS = 1.0
_PROCESS_STOP_POLL_SECONDS = 0.05
_SENTINEL_TIMEOUT_SECONDS = 5.0
_SENTINEL_POLL_SECONDS = 0.05


def _background_sleep_command(pid_path: str, *, exit_immediately: bool = False) -> str:
    'Start a long-lived child that records its own pid before sleeping.'
    script = (
        "from pathlib import Path; import os, time; "
        f"Path({pid_path!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} &"
    return f"{command} disown; exit 0" if exit_immediately else f"{command} wait"


def _started_chatter_command(ready_path: str) -> str:
    'Start a child that writes before signaling readiness.'
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.stdout.write('chatter\\n'); sys.stdout.flush()\n"
        f"Path({ready_path!r}).touch()\n"
        "while True:\n"
        "    sys.stdout.write('chatter\\n')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.001)\n"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} &"


def _process_is_live(pid: int) -> bool:
    'Whether *pid* exists and is not a zombie awaiting reaping.'
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
    )
    return result.returncode == 0 and not result.stdout.lstrip().startswith("Z")


async def _assert_recorded_process_stops(pid_path: str) -> None:
    'A killed child must not remain runnable after the hook returns.'
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
    'A Popen stand-in with a slow wait.'

    returncode = None
    stdin = stdout = stderr = None

    def __init__(self, on_kill=None):
        self._on_kill = on_kill

    def poll(self):
        return None

    def wait(self):

        time.sleep(0.3)
        return 0

    def communicate(self, input=None):

        self.wait()
        return None, None

    def kill(self):
        if self._on_kill is not None:
            self._on_kill()


@pytest.mark.asyncio
async def test_command_hook_timeout_returns_clean_result():
    'A timed-out hook is killed, reaped, and reported cleanly.'
    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.1)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")
    assert "can't be awaited" not in (result.output or "")


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_timeout_kills_grandchildren_not_just_the_shell():
    'A timed-out hook must leave no surviving descendants.'

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


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_returns_when_the_child_exits_not_at_pipe_eof():
    'A hook that backgrounds work and exits succeeds at once, keeping output.'
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

        assert result.modifications.get("additionalContext") == "ok"





        for _ in range(int(_SENTINEL_TIMEOUT_SECONDS / _SENTINEL_POLL_SECONDS)):
            if os.path.exists(sentinel):
                break
            await asyncio.sleep(_SENTINEL_POLL_SECONDS)
        assert os.path.exists(sentinel), "background work was killed off"


@posix_shell_only
@pytest.mark.asyncio
async def test_command_hook_timeout_kills_descendants_of_a_shell_that_already_exited():
    'The group kill must reach descendants when the shell is already gone.'
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
    'If the timed-out process is already gone (ProcessLookupError on kill),'

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
    'Cancelling the awaiting task kills the subprocess and re-raises.'
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
    'If the subprocess is already gone when cancellation fires, the'

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
    'An unexpected error while spawning the subprocess is caught and returned'
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
