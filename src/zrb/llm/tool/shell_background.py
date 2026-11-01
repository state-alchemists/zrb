"""Background shell command execution.

``Shell(background=True)`` returns a handle; ``MonitorProcess(handle)`` polls,
waits on or kills it. The registry is process-scoped.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from zrb.cmd.command import (
    close_transport,
    create_yielding_argv,
    kill_pid,
    resolve_shell,
    terminate_process,
)
from zrb.config.config import CFG
from zrb.llm.agent_state import get_current_ui
from zrb.llm.ambient_state import get_current_chat_session_id
from zrb.llm.input_source import BACKGROUND_INPUT
from zrb.llm.permission import Capability, tag
from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy
from zrb.llm.shell_cut import interrupted_notice, is_cut_while_waiting
from zrb.llm.tool.stream_capture import StreamCapture
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.llm.any_ui import AnyUI


def _new_capture() -> StreamCapture:
    # echo=0: background output is never mirrored to the console.
    return StreamCapture(CFG.LLM_MAX_OUTPUT_CHARS, 0)


@dataclass
class _BackgroundProcess:
    process: asyncio.subprocess.Process
    stdout_cap: StreamCapture = field(default_factory=_new_capture)
    stderr_cap: StreamCapture = field(default_factory=_new_capture)
    description: str = ""
    returncode: int | None = None
    tasks: list[asyncio.Task] = field(default_factory=list)
    # Set only for a process moved here after its timeout: its time in the
    # background is bounded. A process started with `background=True` has none.
    deadline: asyncio.TimerHandle | None = None
    # The unique `ChatSessionManager` session_id (not the display name); ""
    # outside a web chat run.
    owner_session_id: str = ""
    # Monotonic start, so a live-context summary can say how long it has run.
    started_at: float = field(default_factory=time.monotonic)
    # The UI of the run that started this process: where its ending is
    # reported, because the registry outlives any one turn and has no other way
    # to reach the session that is waiting on it. None for a run with no UI.
    ui: "AnyUI | None" = None
    # Set when the model, the user or a shutdown asked for the stop. A stop
    # someone asked for is not news to the session, so it is not reported.
    stop_requested: bool = False
    # How many `MonitorProcess(wait=...)` calls are blocked on this process
    # right now. They return the ending themselves, so a wake-up would repeat it.
    waiters: int = 0
    # Whether the caller wrote a description, as opposed to `description` being
    # the command line: a command line can hold a credential, so it never goes
    # into the transcript on its own.
    description_given: bool = False
    # The wake-up this process queued, kept so that consuming the handle can
    # take it back before it starts a turn about something already read.
    wake_message: str = ""
    # Whether the session has been told, so the two ways an ending is noticed
    # (the exit wait and the deadline stop) cannot both tell it.
    wake_sent: bool = False


class _ShellBackgroundRegistry:
    """Process-lifetime registry of background shell tasks keyed by handle."""

    def __init__(self) -> None:
        self._procs: dict[str, _BackgroundProcess] = {}

    async def start(
        self,
        command: str,
        cwd: str,
        description: str,
        shell: str = "",
        dangerously_skip_sandbox: bool = False,
    ) -> str:
        resolved_shell, shell_flag = resolve_shell(shell)
        effective_cwd = cwd or os.getcwd()
        # Raises SandboxUnavailableError in fallback="deny" mode.
        argv, sandbox_note = build_sandboxed_argv(
            [resolved_shell, shell_flag, command],
            get_effective_sandbox_policy(),
            skip=dangerously_skip_sandbox,
        )
        # Own process group; DEVNULL stdin prevents hangs on stdin reads.
        proc = await asyncio.create_subprocess_exec(
            *create_yielding_argv(argv),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=effective_cwd,
            start_new_session=True,
        )
        bp = _BackgroundProcess(
            process=proc,
            description=description or command,
            owner_session_id=get_current_chat_session_id(),
            ui=get_current_ui(),
            description_given=bool(description),
        )
        if sandbox_note:
            bp.stderr_cap.feed(f"{sandbox_note}\n")
        return self._register(bp)

    async def adopt(
        self,
        process: asyncio.subprocess.Process,
        command: str,
        stdout_cap: StreamCapture,
        stderr_cap: StreamCapture,
    ) -> str:
        """Take over a process its caller stopped waiting on, under a new handle.

        The pipes and the captures are the caller's, still open: whatever the
        process writes from here lands where the timeout report left off, so
        the model can pick the output up without losing what came before it.
        The caller has already cancelled its own readers, which is why this
        starts new ones rather than reusing them.

        The returned handle expires after
        ``LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS``; a caller that disables
        adoption never gets here.
        """
        bp = _BackgroundProcess(
            process=process,
            stdout_cap=stdout_cap,
            stderr_cap=stderr_cap,
            description=command,
            owner_session_id=get_current_chat_session_id(),
            ui=get_current_ui(),
        )
        handle = self._register(bp)
        self._arm_deadline(handle, bp)
        return handle

    def _register(self, bp: _BackgroundProcess) -> str:
        """Store *bp* under a new handle and start the tasks that feed and reap it.

        The tasks are tracked on *bp* so `kill` and `cancel_all` can stop them.
        """
        handle = get_random_name(separator="-", add_random_digit=True)
        self._procs[handle] = bp
        bp.tasks = [
            asyncio.ensure_future(self._read_pipe(handle, bp.process.stdout, "stdout")),
            asyncio.ensure_future(self._read_pipe(handle, bp.process.stderr, "stderr")),
            asyncio.ensure_future(self._wait_exit(handle, bp.process)),
        ]
        return handle

    def _arm_deadline(self, handle: str, bp: _BackgroundProcess) -> None:
        seconds = CFG.LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS
        if seconds <= 0:
            return
        loop = asyncio.get_running_loop()
        bp.deadline = loop.call_later(seconds, self._expire, handle)

    def _expire(self, handle: str) -> None:
        """Stop an adopted process that has used up its time in the background.

        The entry stays registered and says why, so a poll that arrives after
        the kill explains itself instead of reporting an unknown handle.
        """
        bp = self._procs.get(handle)
        if bp is None or bp.process.returncode is not None:
            return
        bp.deadline = None
        seconds = CFG.LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS
        bp.stderr_cap.feed(
            f"\n[{CFG.ROOT_GROUP_NAME}] killed after {seconds}s in the background "
            f"({CFG.ENV_PREFIX}_LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS). Start it "
            "again with background=True if it needs longer.\n"
        )
        asyncio.ensure_future(self._stop_adopted(handle))

    async def _stop_adopted(self, handle: str) -> None:
        bp = self._procs.get(handle)
        if bp is None:
            return
        await _stop_process(bp)
        # `_stop_process` cancels the wait task, so the exit code it would have
        # recorded is set here; a poll after the kill must not read "running".
        bp.returncode = bp.process.returncode
        # Nobody asked for this stop: it is the end of the time the process was
        # given, which the session should hear like any other ending.
        self._wake_session(handle, bp)

    async def _read_pipe(
        self, handle: str, stream: asyncio.StreamReader | None, name: str
    ) -> None:
        """Feed *stream* line by line into the handle's `name` capture."""
        while stream and not stream.at_eof():
            line = await stream.readline()
            if not line:
                break
            self._feed(handle, name, line)
        if stream:
            remaining = await stream.read()
            if remaining:
                self._feed(handle, name, remaining)

    def _feed(self, handle: str, name: str, data: bytes) -> None:
        bp = self._procs.get(handle)
        if bp is None:
            return
        cap = bp.stdout_cap if name == "stdout" else bp.stderr_cap
        cap.feed(data.decode(errors="replace"))

    async def _wait_exit(self, handle: str, proc: asyncio.subprocess.Process) -> None:
        rc = await proc.wait()
        bp = self._procs.get(handle)
        if bp is not None:
            bp.returncode = rc
            # The exit can be heard before the last of the output has been read.
            # `poll` calls a process finished only once every task is done, and a
            # wake-up that arrived earlier would send the model to a result that
            # still says "poll once more" with nothing to announce the rest. So
            # the session is told when the readers are done too.
            readers = [t for t in bp.tasks if t is not asyncio.current_task()]
            if readers:
                await asyncio.wait(readers)
            self._wake_session(handle, bp)

    def _wake_session(self, handle: str, bp: _BackgroundProcess) -> None:
        """Tell the session that started *bp* that it ended, once.

        The process ending is the only moment its result exists, and a session
        with nobody typing would otherwise not look until the next message. The
        message goes through the UI's own queue: a running turn reads it at its
        next model request, an idle session takes a turn of its own, and the
        UI's limit on consecutive wake-ups applies to it like any other.

        Skipped when the ending is already known to whoever would read it: the
        stop was asked for, the handle was consumed by a poll, or a
        `MonitorProcess(wait=...)` is blocked on it. It carries the handle and
        the exit code and never the output, which can hold a token and is the
        model's to read with `MonitorProcess`.
        """
        if not CFG.LLM_BACKGROUND_WAKE or bp.ui is None:
            return
        if bp.stop_requested or bp.waiters > 0 or self._procs.get(handle) is not bp:
            return
        if bp.wake_sent:
            return
        bp.wake_sent = True
        # Named only when the caller wrote the description: without one it is the
        # command line, which can carry a token, and this lands in the transcript.
        named = (
            f": {bp.description.replace(chr(10), ' ')[:80]}"
            if bp.description_given and bp.description
            else ""
        )
        message = (
            f"[Background process {handle} finished (exit {bp.returncode}){named}. "
            f"MonitorProcess(handle='{handle}') reads its output.]"
        )
        try:
            bp.ui.submit_message(message, BACKGROUND_INPUT)
            bp.wake_message = message
        except (RuntimeError, OSError) as e:
            # A UI that is closing or a loop that is gone: the exit is still in
            # the next turn's live context, so this costs the nudge, not the result.
            CFG.LOGGER.debug(f"Could not wake the session for {handle}: {e}")

    async def collect(self, handle: str, wait: float = 0.0) -> str:
        """Poll a handle, blocking up to ``wait`` seconds for exit and full drain.

        The process is not killed on timeout, and an interrupting message ends
        the wait instead of holding the turn: the call then reports itself
        interrupted, keeping the process as it is for the retry.
        """
        bp = self._procs.get(handle)
        if bp is not None and bp.returncode is None and wait > 0:
            capped = min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)
            bp.waiters += 1
            try:
                was_cut = await is_cut_while_waiting(set(bp.tasks), capped)
            finally:
                bp.waiters -= 1
            # A process that exited as the cut landed is reported, not waited
            # on: `poll` consumes the handle of a finished process.
            if was_cut and bp.returncode is None:
                return (
                    interrupted_notice(f"MonitorProcess(handle='{handle}', wait=N)")
                    + "\n\n"
                    + self.poll(handle)
                )
        return self.poll(handle)

    def poll(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return _unknown_handle_message(handle)
        stdout = bp.stdout_cap.text
        stderr = bp.stderr_cap.text
        status = "running"
        if bp.returncode is not None:
            status = f"exited (code {bp.returncode})"
        lines = [
            f"Process: {bp.description}",
            f"Status: {status}",
            f"Stdout:\n{stdout.strip() or '(empty)'}",
            f"Stderr:\n{stderr.strip() or '(empty)'}",
        ]
        truncation_note = _truncation_note(bp.stdout_cap, bp.stderr_cap)
        if truncation_note:
            lines.append(truncation_note)
        if bp.returncode is not None:
            if all(task.done() for task in bp.tasks):
                lines.append("The handle has been consumed — the process has finished.")
                self._withdraw_wake(bp)
                _release_process(bp)
                self._procs.pop(handle, None)
            else:
                lines.append(
                    "The process has finished; output is still being "
                    "collected — poll once more for the final output."
                )
        return "\n".join(lines)

    def _withdraw_wake(self, bp: _BackgroundProcess) -> None:
        """Take back the wake-up *bp* queued, if it is still waiting.

        Consuming the handle is the model reading the ending, so a wake-up still
        in the queue would start a turn about something already handled, and
        point it at a handle that no longer exists. One already delivered is
        beyond recall and is left alone.
        """
        if not bp.wake_message or bp.ui is None:
            return
        message, bp.wake_message = bp.wake_message, ""
        try:
            bp.ui.withdraw_message(message, BACKGROUND_INPUT)
        except (RuntimeError, OSError) as e:
            CFG.LOGGER.debug(f"Could not withdraw a wake-up: {e}")

    def summary(self, session_id: str | None = None) -> "list[dict[str, Any]]":
        """A read-only view of the handles this registry holds.

        Unlike `poll`, this never retires an entry: asking what is running is
        not the consumption that releases a handle. *session_id* filters to one
        owner — a live-context line must not name another chat's processes.
        """
        now = time.monotonic()
        rows: "list[dict[str, Any]]" = []
        for handle, bp in self._procs.items():
            if session_id is not None and bp.owner_session_id != session_id:
                continue
            rows.append(
                {
                    "handle": handle,
                    "description": bp.description,
                    "returncode": bp.returncode,
                    "seconds": max(now - bp.started_at, 0.0),
                }
            )
        return rows

    async def kill(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return _unknown_handle_message(handle)
        if bp.process.returncode is not None:
            return (
                f"Process '{handle}' has already exited (code {bp.process.returncode})."
            )
        bp.stop_requested = True
        await _stop_process(bp)
        self._procs.pop(handle, None)
        return f"Killed process '{handle}'."

    async def cancel_all(self) -> None:
        """Kill and reap every background process, so none outlives the event loop."""
        for bp in list(self._procs.values()):
            bp.stop_requested = True
            await _stop_process(bp)
        self._procs.clear()

    async def cancel_for_session(self, session_id: str) -> None:
        """Kill every background process owned by *session_id*.

        *session_id* is `ChatSessionManager`'s unique key, not a display name.
        """
        for handle, bp in list(self._procs.items()):
            if bp.owner_session_id != session_id:
                continue
            bp.stop_requested = True
            await _stop_process(bp)
            self._procs.pop(handle, None)

    def force_kill_all(self) -> None:
        """Synchronously SIGKILL any running background process.

        Loop-free `atexit` backstop, for when the event loop is already closed.
        Never raises.
        """
        for bp in list(self._procs.values()):
            if bp.process.returncode is not None:
                continue
            try:
                kill_pid(bp.process.pid, print_method=CFG.LOGGER.debug)
            except Exception:  # noqa: BLE001 - atexit backstop, must never raise
                pass
        self._procs.clear()


def _unknown_handle_message(handle: str) -> str:
    return (
        f"Unknown handle '{handle}'. "
        "[SYSTEM SUGGESTION]: start a process with Shell "
        "(background=True); a finished handle is consumed by the poll "
        "that reports its exit."
    )


async def _stop_process(bp: _BackgroundProcess) -> None:
    """Terminate *bp* if still running, then release it."""
    if bp.process.returncode is None:
        await terminate_process(
            bp.process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )
    _release_process(bp)


def _truncation_note(stdout_cap: StreamCapture, stderr_cap: StreamCapture) -> str:
    """A `[SYSTEM SUGGESTION]` naming each truncated stream's spill file, or `""`.

    Reuses the streams' spill files so repeated polls don't leak temp files.
    """
    if not (stdout_cap.truncated or stderr_cap.truncated):
        return ""
    parts = []
    for name, cap in (("stdout", stdout_cap), ("stderr", stderr_cap)):
        if cap.truncated:
            cap.flush()
            parts.append(
                f"{name} truncated (kept the tail, {cap.total_chars} chars "
                f"total) — full {name} saved to {cap.spill_path}"
            )
    return (
        "[SYSTEM SUGGESTION]: "
        + "; ".join(parts)
        + ". Grep it to locate a section, then Read that range."
    )


def _release_process(bp: _BackgroundProcess) -> None:
    """Cancel the reader/wait tasks and close the subprocess transport.

    Closing the transport while the loop is alive avoids CPython < 3.13's
    ``BaseSubprocessTransport.__del__`` raising "Event loop is closed"
    (gh-114177). Captures are closed but not discarded: the poll that
    triggered this may have just reported their spill paths.
    """
    for task in bp.tasks:
        if not task.done():
            task.cancel()
    bp.tasks = []
    if bp.deadline is not None:
        bp.deadline.cancel()
        bp.deadline = None
    bp.stdout_cap.close()
    bp.stderr_cap.close()
    close_transport(bp.process)


_registry = _ShellBackgroundRegistry()
atexit.register(_registry.force_kill_all)


def get_shell_background_registry() -> _ShellBackgroundRegistry:
    return _registry


def create_monitor_process_tool():
    async def monitor_process(
        handle: Annotated[
            str,
            Field(
                description="The handle returned when the process was started with background=True."
            ),
        ],
        kill: Annotated[
            bool,
            Field(description="True terminates the process instead of checking on it."),
        ] = False,
        wait: Annotated[
            float,
            Field(
                description=(
                    "Seconds to block for the process to exit before returning "
                    "(capped by LLM_BACKGROUND_WAIT_MAX); 0 (default) returns "
                    "immediately with the current status."
                )
            ),
        ] = 0,
    ) -> str:
        """Check or kill a process started with `background=True`.

        By default returns the current stdout/stderr and status. Pass `wait=N`
        to block up to N seconds (capped by LLM_BACKGROUND_WAIT_MAX), returning
        the instant the process exits; on timeout it returns the running status
        so you can call again with another `wait`, or `kill=True` to terminate.
        """
        if kill:
            return await _registry.kill(handle)
        return await _registry.collect(handle, wait)

    monitor_process.__name__ = "MonitorProcess"
    tag(monitor_process, Capability.EXECUTE)
    return monitor_process
