"""Background shell command execution.

``ShellBackground`` starts a command in the background and returns a handle
immediately. ``MonitorProcess(handle)`` polls the status, shows captured
stdout/stderr incrementally, and optionally kills the process.

The registry is process- and event-loop-scoped — results do not persist
across restarts.
"""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass, field

from zrb.config.config import CFG
from zrb.llm.permission import Capability, tag
from zrb.util.string.name import get_random_name


@dataclass
class _BackgroundProcess:
    process: asyncio.subprocess.Process
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    description: str = ""
    returncode: int | None = None


class _ShellBackgroundRegistry:
    """Process-lifetime registry of background shell tasks keyed by handle."""

    def __init__(self) -> None:
        self._procs: dict[str, _BackgroundProcess] = {}

    async def start(
        self, command: str, cwd: str, description: str
    ) -> str:
        handle = get_random_name(separator="-", add_random_digit=True)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
            preexec_fn=os.setsid,
        )
        bp = _BackgroundProcess(
            process=proc, description=description or command
        )
        self._procs[handle] = bp
        # Start readers in the background.
        asyncio.ensure_future(self._read_stdout(handle, proc))
        asyncio.ensure_future(self._read_stderr(handle, proc))
        asyncio.ensure_future(self._wait_exit(handle, proc))
        return handle

    async def _read_stdout(
        self, handle: str, proc: asyncio.subprocess.Process
    ) -> None:
        while proc.stdout and not proc.stdout.at_eof():
            line = await proc.stdout.readline()
            if not line:
                break
            bp = self._procs.get(handle)
            if bp is not None:
                bp.stdout_lines.append(line.decode(errors="replace"))
        # Drain remaining buffer
        if proc.stdout:
            remaining = await proc.stdout.read()
            if remaining:
                bp = self._procs.get(handle)
                if bp is not None:
                    bp.stdout_lines.append(remaining.decode(errors="replace"))

    async def _read_stderr(
        self, handle: str, proc: asyncio.subprocess.Process
    ) -> None:
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

    async def _wait_exit(
        self, handle: str, proc: asyncio.subprocess.Process
    ) -> None:
        rc = await proc.wait()
        bp = self._procs.get(handle)
        if bp is not None:
            bp.returncode = rc

    def poll(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return (
                f"Unknown handle '{handle}'. "
                "[SYSTEM SUGGESTION]: use ShellBackground to start a process."
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
            lines.append(
                "The handle has been consumed — the process has finished."
            )
        return "\n".join(lines)

    async def kill(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return f"Unknown handle '{handle}'."
        if bp.process.returncode is not None:
            return f"Process '{handle}' has already exited (code {bp.process.returncode})."
        try:
            os.killpg(os.getpgid(bp.process.pid), signal.SIGTERM)
            await asyncio.wait_for(
                bp.process.wait(),
                timeout=CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            )
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                os.killpg(os.getpgid(bp.process.pid), signal.SIGKILL)
            except Exception:
                pass
        self._procs.pop(handle, None)
        return f"Killed process '{handle}'."

    def cancel_all(self) -> None:
        for handle, bp in list(self._procs.items()):
            if bp.process.returncode is None:
                try:
                    os.killpg(os.getpgid(bp.process.pid), signal.SIGKILL)
                except Exception:
                    pass
        self._procs.clear()


_registry = _ShellBackgroundRegistry()


def get_shell_background_registry() -> _ShellBackgroundRegistry:
    return _registry


def create_shell_background_tool():
    async def shell_background(
        command: str,
        description: str = "",
        cwd: str = "",
    ) -> str:
        """Start a shell command in the BACKGROUND and return a handle immediately.

        Use for long-running processes (dev servers, watchers, builds). Poll
        with MonitorProcess(handle) to see incremental stdout/stderr. Kill
        with MonitorProcess(handle, kill=True).

        For short commands whose output you need now, use Shell instead.
        """
        handle = await _registry.start(command, cwd, description)
        return (
            f"Started background process. Handle: {handle}. "
            "Call MonitorProcess with this handle to check status."
        )

    shell_background.__name__ = "ShellBackground"
    tag(shell_background, Capability.EXECUTE)
    return shell_background


def create_monitor_process_tool():
    async def monitor_process(
        handle: str,
        kill: bool = False,
    ) -> str:
        """Check or kill a background process started by ShellBackground.

        By default returns the current stdout/stderr and status.
        Pass kill=True to terminate the process.
        """
        if kill:
            return await _registry.kill(handle)
        return _registry.poll(handle)

    monitor_process.__name__ = "MonitorProcess"
    tag(monitor_process, Capability.EXECUTE)
    return monitor_process
