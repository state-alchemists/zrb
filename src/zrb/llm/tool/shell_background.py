"""Background shell command execution.

``Shell`` with ``background=True`` starts a command in the background
and returns a handle immediately (the registry below does the launching).
``MonitorProcess(handle)`` polls the status, shows captured stdout/stderr
incrementally, optionally waits up to N seconds for exit, and optionally kills
the process.

The registry is process- and event-loop-scoped — results do not persist
across restarts.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from zrb.config.config import CFG
from zrb.llm.permission import Capability, tag
from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy
from zrb.util.cmd.command import resolve_shell, terminate_process
from zrb.util.string.name import get_random_name


@dataclass
class _BackgroundProcess:
    process: asyncio.subprocess.Process
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    description: str = ""
    returncode: int | None = None
    tasks: list[asyncio.Task] = field(default_factory=list)


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
        # Raises SandboxUnavailableError in fallback="deny" mode — surfaced by
        # the tool as an explanatory error.
        argv, sandbox_note = build_sandboxed_argv(
            resolved_shell,
            shell_flag,
            command,
            effective_cwd,
            get_effective_sandbox_policy(),
            skip=dangerously_skip_sandbox,
        )
        # start_new_session=True isolates the process group (setsid on POSIX,
        # ignored on Windows). stdin=DEVNULL prevents hangs on stdin reads.
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=effective_cwd,
            start_new_session=True,
        )
        bp = _BackgroundProcess(process=proc, description=description or command)
        if sandbox_note:
            bp.stderr_lines.append(f"{sandbox_note}\n")
        self._procs[handle] = bp
        # Start readers in the background and track them so cancel_all() /
        # kill() can stop them — otherwise they leak past the process exit.
        bp.tasks = [
            asyncio.ensure_future(self._read_stdout(handle, proc)),
            asyncio.ensure_future(self._read_stderr(handle, proc)),
            asyncio.ensure_future(self._wait_exit(handle, proc)),
        ]
        return handle

    async def _read_stdout(self, handle: str, proc: asyncio.subprocess.Process) -> None:
        while proc.stdout and not proc.stdout.at_eof():
            line = await proc.stdout.readline()
            if not line:
                break
            bp = self._procs.get(handle)
            if bp is not None:
                bp.stdout_lines.append(line.decode(errors="replace"))
        if proc.stdout:
            remaining = await proc.stdout.read()
            if remaining:
                bp = self._procs.get(handle)
                if bp is not None:
                    bp.stdout_lines.append(remaining.decode(errors="replace"))

    async def _read_stderr(self, handle: str, proc: asyncio.subprocess.Process) -> None:
        while proc.stderr and not proc.stderr.at_eof():
            line = await proc.stderr.readline()
            if not line:
                break
            bp = self._procs.get(handle)
            if bp is not None:
                bp.stderr_lines.append(line.decode(errors="replace"))
        if proc.stderr:
            remaining = await proc.stderr.read()
            if remaining:
                bp = self._procs.get(handle)
                if bp is not None:
                    bp.stderr_lines.append(remaining.decode(errors="replace"))

    async def _wait_exit(self, handle: str, proc: asyncio.subprocess.Process) -> None:
        rc = await proc.wait()
        bp = self._procs.get(handle)
        if bp is not None:
            bp.returncode = rc

    async def collect(self, handle: str, wait: float = 0.0) -> str:
        """Poll a handle, optionally blocking up to ``wait`` seconds for exit.

        Waits until the process has exited AND its output is fully drained, or
        the timeout elapses, then returns the synchronous ``poll``. The process
        is not killed on timeout — it keeps running.
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
            return (
                f"Unknown handle '{handle}'. "
                "[SYSTEM SUGGESTION]: start a process with Shell "
                "(background=True); a finished handle is consumed by the poll "
                "that reports its exit."
            )
        stdout = "".join(bp.stdout_lines)
        stderr = "".join(bp.stderr_lines)
        status = "running"
        if bp.returncode is not None:
            status = f"exited (code {bp.returncode})"
        lines = [
            f"Process: {bp.description}",
            f"Status: {status}",
            f"Stdout:\n{stdout.strip() or '(empty)'}",
            f"Stderr:\n{stderr.strip() or '(empty)'}",
        ]
        if bp.returncode is not None:
            if all(task.done() for task in bp.tasks):
                # Output fully drained: release the entry so finished
                # processes (and their output buffers) don't accumulate in
                # the registry for the rest of the session.
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
            return (
                f"Unknown handle '{handle}'. "
                "[SYSTEM SUGGESTION]: start a process with Shell "
                "(background=True); a finished handle is consumed by the poll "
                "that reports its exit."
            )
        if bp.process.returncode is not None:
            return (
                f"Process '{handle}' has already exited (code {bp.process.returncode})."
            )
        await terminate_process(
            bp.process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )
        _release_process(bp)
        self._procs.pop(handle, None)
        return f"Killed process '{handle}'."

    async def cancel_all(self) -> None:
        """Kill every running background process and release its transport.

        Session teardown calls this so no asyncio subprocess outlives the event
        loop. ``terminate_process`` both kills and reaps: a child left running
        when the loop closes logs "Loop <...> that handles pid N is closed"
        when it eventually exits, because its exit event can no longer be
        delivered.
        """
        for handle, bp in list(self._procs.items()):
            if bp.process.returncode is None:
                await terminate_process(
                    bp.process,
                    CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
                    print_method=CFG.LOGGER.warning,
                )
            _release_process(bp)
        self._procs.clear()


def _release_process(bp: _BackgroundProcess) -> None:
    """Cancel the detached reader/wait tasks and finalize the subprocess transport.

    A subprocess transport is only closed once the loop observes both the
    process exit and the pipe EOFs. A background process dropped before that
    (consume, kill, or cancel_all) gets its transport garbage-collected after
    the loop has closed, where CPython < 3.13's ``BaseSubprocessTransport.__del__``
    calls ``close()`` without the gh-114177 closed-loop guard and raises
    ``RuntimeError('Event loop is closed')`` — surfaced by pytest as a
    PytestUnraisableExceptionWarning. Closing explicitly here, while the loop is
    alive, makes that ``__del__`` a no-op.
    """
    for task in bp.tasks:
        if not task.done():
            task.cancel()
    bp.tasks = []
    transport = getattr(bp.process, "_transport", None)
    if transport is not None:
        transport.close()


_registry = _ShellBackgroundRegistry()


def get_shell_background_registry() -> _ShellBackgroundRegistry:
    return _registry


def create_monitor_process_tool():
    async def monitor_process(
        handle: str,
        kill: bool = False,
        wait: float = 0,
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
