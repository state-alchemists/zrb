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
from dataclasses import dataclass, field

from zrb.config.config import CFG
from zrb.llm.permission import Capability, tag
from zrb.util.cmd.command import kill_pid, resolve_shell, terminate_process
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
        # lazy: leaf module; policy re-resolved per call (ContextVar / CFG).
        from zrb.llm.sandbox import build_sandboxed_argv, get_effective_sandbox_policy

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
        # Drain remaining buffer
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

    def poll(self, handle: str) -> str:
        bp = self._procs.get(handle)
        if bp is None:
            return (
                f"Unknown handle '{handle}'. "
                "[SYSTEM SUGGESTION]: use ShellBackground to start a process; "
                "a finished handle is consumed by the poll that reports its exit."
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
                _cancel_tasks(bp)
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
            return f"Unknown handle '{handle}'."
        if bp.process.returncode is not None:
            return (
                f"Process '{handle}' has already exited (code {bp.process.returncode})."
            )
        await terminate_process(
            bp.process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )
        _cancel_tasks(bp)
        self._procs.pop(handle, None)
        return f"Killed process '{handle}'."

    def cancel_all(self) -> None:
        for handle, bp in list(self._procs.items()):
            if bp.process.returncode is None:
                kill_pid(bp.process.pid, print_method=CFG.LOGGER.warning)
            _cancel_tasks(bp)
        self._procs.clear()


def _cancel_tasks(bp: _BackgroundProcess) -> None:
    """Cancel the detached reader/wait tasks attached to a background process."""
    for task in bp.tasks:
        if not task.done():
            task.cancel()
    bp.tasks = []


_registry = _ShellBackgroundRegistry()


def get_shell_background_registry() -> _ShellBackgroundRegistry:
    return _registry


def create_shell_background_tool():
    async def shell_background(
        command: str,
        description: str = "",
        cwd: str = "",
        shell: str = "",
        dangerously_skip_sandbox: bool = False,
    ) -> str:
        """Start a shell command in the BACKGROUND and return a handle immediately.

        Poll with MonitorProcess(handle) to see incremental stdout/stderr;
        kill with MonitorProcess(handle, kill=True).

        `shell` selects the shell or interpreter (e.g. "bash", "pwsh", "node");
        empty uses the user's default shell. `dangerously_skip_sandbox` runs the
        command outside the OS-level sandbox (when one is active) and always
        requires explicit user approval.
        """
        # lazy: leaf module
        from zrb.llm.sandbox import SandboxUnavailableError

        try:
            handle = await _registry.start(
                command, cwd, description, shell, dangerously_skip_sandbox
            )
        except SandboxUnavailableError as e:
            return (
                f"Command refused by sandbox policy: {e}. "
                "[SYSTEM SUGGESTION]: this deployment requires OS-level "
                "sandboxing for shell commands (LLM_SANDBOX_FALLBACK=deny)."
            )
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
