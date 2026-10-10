"""Background shell command execution.

``Shell(background=True)`` returns a handle; ``MonitorProcess(handle)`` polls,
waits on or kills it. The registry is process-scoped.
"""

from __future__ import annotations

import asyncio
import atexit
import os
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field

from zrb.cmd.command import kill_pid, resolve_shell, terminate_process
from zrb.config.config import CFG
from zrb.llm.ambient_state import get_current_chat_session_id
from zrb.llm.permission import Capability, tag
from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy
from zrb.llm.tool.stream_capture import StreamCapture
from zrb.util.string.name import get_random_name


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
    # The unique `ChatSessionManager` session_id (not the display name); ""
    # outside a web chat run.
    owner_session_id: str = ""


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
        handle = get_random_name(separator="-", add_random_digit=True)
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
            *argv,
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
        )
        if sandbox_note:
            bp.stderr_cap.feed(f"{sandbox_note}\n")
        self._procs[handle] = bp
        # Tracked so kill()/cancel_all() can stop them.
        bp.tasks = [
            asyncio.ensure_future(self._read_pipe(handle, proc.stdout, "stdout")),
            asyncio.ensure_future(self._read_pipe(handle, proc.stderr, "stderr")),
            asyncio.ensure_future(self._wait_exit(handle, proc)),
        ]
        return handle

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

    async def collect(self, handle: str, wait: float = 0.0) -> str:
        """Poll a handle, blocking up to ``wait`` seconds for exit and full drain.

        The process is not killed on timeout.
        """
        bp = self._procs.get(handle)
        if bp is not None and bp.returncode is None and wait > 0:
            capped = min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)
            await asyncio.wait(
                set(bp.tasks),
                timeout=capped,
                return_when=asyncio.ALL_COMPLETED,
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
                # Fully drained: release the entry.
                lines.append("The handle has been consumed — the process has finished.")
                _release_process(bp)
                self._procs.pop(handle, None)
            else:
                lines.append(
                    "The process has finished; output is still being "
                    "collected — poll once more for the final output."
                )
        return "\n".join(lines)

    async def kill(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return _unknown_handle_message(handle)
        if bp.process.returncode is not None:
            return (
                f"Process '{handle}' has already exited (code {bp.process.returncode})."
            )
        await _stop_process(bp)
        self._procs.pop(handle, None)
        return f"Killed process '{handle}'."

    async def cancel_all(self) -> None:
        """Kill and reap every background process, so none outlives the event loop."""
        for bp in list(self._procs.values()):
            await _stop_process(bp)
        self._procs.clear()

    async def cancel_for_session(self, session_id: str) -> None:
        """Kill every background process owned by *session_id*.

        *session_id* is `ChatSessionManager`'s unique key, not a display name.
        """
        for handle, bp in list(self._procs.items()):
            if bp.owner_session_id != session_id:
                continue
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
    bp.stdout_cap.close()
    bp.stderr_cap.close()
    transport = getattr(bp.process, "_transport", None)
    if transport is not None:
        transport.close()


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
