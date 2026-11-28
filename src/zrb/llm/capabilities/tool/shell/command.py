import asyncio
import os
import platform
import shlex
import tempfile
import time
from collections.abc import Callable
from typing import Annotated, Protocol, TypeVar, cast

from pydantic import Field

from zrb.cmd.command import (
    close_transport,
    create_yielding_argv,
    resolve_shell,
    terminate_process,
    wait_for_exit_and_drain,
)
from zrb.config.config import CFG
from zrb.llm.capabilities.permission import Capability, tag
from zrb.llm.capabilities.sandbox import get_effective_sandbox_policy
from zrb.llm.capabilities.sandbox.os_sandbox import (
    SandboxUnavailableError,
    format_sandbox_denied_message,
    has_private_pid_namespace,
)
from zrb.llm.capabilities.tool.purpose import Purpose, requires_purpose
from zrb.llm.capabilities.tool.shell.capture import StreamCapture
from zrb.llm.contracts.shared.agent_state import get_current_ui
from zrb.llm.contracts.shared.shell_cut import get_run_shell_cut_signal
from zrb.util.cli.ansi import strip_ansi

#: Whatever a cancellable task resolves to; `_stop` only cancels and awaits it.
T = TypeVar("T")

# Minimum seconds between live shell-output repaints.
_LIVE_UPDATE_INTERVAL = 0.5

# Share of a failed stream's retained text given back to its beginning: a
# failing command announces its cause first and only summarizes it last.
_HEAD_SHARE_OF_FAILED_OUTPUT = 0.4


@requires_purpose
async def run_shell_command(
    command: Annotated[str, Field(description="Non-interactive command.")],
    purpose: Purpose = "",
    cwd: Annotated[str, Field(description="Working directory.")] = "",
    timeout: Annotated[
        int,
        Field(
            description=(
                "SECONDS, not milliseconds. Outrunning it moves the command to "
                "the background (not killed), reported with a handle."
            )
        ),
    ] = 120,
    max_chars: Annotated[
        int, Field(description="-1 uses the configured output limit.")
    ] = -1,
    shell: Annotated[
        str,
        Field(
            description=(
                "bash/zsh/sh (POSIX), pwsh/cmd (Windows), node/ruby/php "
                "(runtime); empty is the user's default."
            )
        ),
    ] = "",
    dangerously_skip_sandbox: Annotated[
        bool,
        Field(description="True exits the OS sandbox and requires user approval."),
    ] = False,
    background: Annotated[
        bool,
        Field(
            description=(
                "True for long-running processes (server, watcher): returns a handle at once; "
                "check with MonitorProcess."
            )
        ),
    ] = False,
    description: Annotated[
        str, Field(description="Label for a background process; default the command.")
    ] = "",
) -> str:
    """
    Executes a non-interactive command in a shell. Returns truncated stdout/stderr.

    Say why you are calling it: fill ``purpose`` with the reason, in plain
    words ("Getting the biggest file in the directory") — a user listening to
    zrb hears that instead of "Running a command.".

    Use this to RUN things — builds, tests, linters, git, package managers,
    scripts. Not to touch files: Read/Write/Edit for contents, Grep/Glob/LS to
    search and list, RM/MV to remove and move. ``cat``, ``find``, ``sed -i`` and
    shell redirects are the wrong tool — the file tools carry diagnostics
    and path validation a shell command bypasses.

    Call Shell, not Bash; pass ``shell="bash"`` for bash.

    Several commands already known to run in order belong in one call: ``&&``
    in bash/zsh/sh and cmd, a ``;`` sequence in PowerShell 5 (which has no
    ``&&``), one small script for node/ruby/php. Never chain a step that needs
    this one's output; each extra call re-sends the conversation.

    stdin is closed — pass ``-y``, ``--yes``, or ``CI=true`` for prompts.
    Output is truncated: a successful command keeps its tail, a failed one
    keeps its beginning and its end. Full output is saved to a temp file whose
    path is reported — Grep/Read it.

    A command that outruns its ``timeout`` is not killed: it moves to the
    background and the result carries a handle, so the work it already did is
    not lost and no second copy has to be started. A command that begins with
    ``sleep`` is the exception — a delay is the work, so it is still killed.
    While the Linux sandbox gives a command its own PID namespace, background
    shells are refused, a timed-out command is killed instead, and its
    namespace-local PIDs are not reported as background PIDs (they are not
    host PIDs). Run it in the foreground, or set the OS shell sandbox to off
    to use those features.

    Prefer the bounded form: ``git diff --stat`` before ``git diff``,
    ``--name-only`` before full contents, ``head``/``wc -l`` before a raw dump.
    An unscoped command can emit hundreds of megabytes and be killed by its own
    timeout. Prefer one call to several, too: ``git fetch && git rebase
    origin/main`` costs one round where two calls cost two.
    """
    if background:
        return await _start_background_shell(
            command, cwd, description, shell, dangerously_skip_sandbox
        )
    if max_chars < 0:
        max_chars = CFG.LLM_MAX_OUTPUT_CHARS
    cwd = cwd or os.getcwd()
    resolved_shell, shell_flag = resolve_shell(shell)
    private_pid_namespace = has_private_pid_namespace(
        get_effective_sandbox_policy(), skip=dangerously_skip_sandbox
    )
    use_pid_tracking = _can_track_pids(shell_flag, private_pid_namespace)

    wrapper_command, temp_pid_file = _prepare_command(command, use_pid_tracking)

    try:
        argv, sandbox_note = _build_sandboxed_shell_argv(
            resolved_shell,
            shell_flag,
            wrapper_command,
            dangerously_skip_sandbox,
        )
    except SandboxUnavailableError as e:
        _cleanup_temp_file(temp_pid_file)
        return (
            f"{format_sandbox_denied_message(e)} Use the in-process file tools "
            "instead, or ask the user to adjust the sandbox configuration."
        )

    process = None
    # A command inside bwrap's PID namespace cannot outlive the sandbox, and
    # its PIDs are namespace-local, so it is killed at the timeout instead of
    # being adopted by the background registry.
    allow_adopt = not private_pid_namespace
    # Set when a timeout moved the command to the background instead of
    # killing it; the pipe then belongs to the registry, not to this call.
    handle: "str | None" = None
    try:
        process = await start_process(argv, cwd)
        if process.stdout is None or process.stderr is None:
            raise RuntimeError(
                "the shell process started without the pipes its output is read from"
            )

        ui = get_current_ui()
        live_ui = _live_shell_ui(ui)
        stdout_cap, stderr_cap = _build_stream_captures(max_chars, live_ui is not None)
        output_key = f"shell-{id(stdout_cap)}"
        on_chunk = (
            _make_live_shell_output_pusher(live_ui, output_key, stdout_cap, stderr_cap)
            if live_ui is not None
            else None
        )

        moved = ""
        drain_notices: list[str] = []
        try:
            moved, handle = await _wait_for_exit_or_adopt(
                process,
                command,
                stdout_cap,
                stderr_cap,
                on_chunk,
                timeout,
                drain_notices,
                allow_adopt=allow_adopt,
            )
        finally:
            if live_ui is not None:
                _finish_shell_output(live_ui, output_key, stdout_cap, stderr_cap)

        bg_pids = _collect_background_pids(temp_pid_file, process.pid)

        result = _format_output(
            command,
            cwd,
            stdout_cap,
            stderr_cap,
            process.returncode,
            bg_pids,
            moved,
            timeout,
            drain_notices[0] if drain_notices else None,
            handle,
            background_available=allow_adopt,
        )
        return _present_result(result, sandbox_note, handle, timeout, moved)

    except asyncio.CancelledError:
        # Kill + reap while the loop is alive, else the orphan logs "Loop ...
        # that handles pid N is closed" on exit. BaseException: a re-cancel
        # landing on the reap must not skip the kill.
        _cleanup_temp_file(temp_pid_file)
        try:
            await _kill_if_still_running(process)
        except BaseException:
            CFG.LOGGER.debug("Shell cleanup on cancel failed", exc_info=True)
        raise
    except Exception as e:
        _cleanup_temp_file(temp_pid_file)
        await _kill_if_still_running(process)
        return (
            f"Error executing command: {e}. "
            "[SYSTEM SUGGESTION]: Check the command syntax and that any "
            "referenced files or programs exist, then retry."
        )
    finally:
        # An adopted process's pipes belong to the background registry now;
        # closing them here would kill the output the caller can still poll.
        if handle is None:
            _close_transport_if_started(process)


async def _start_background_shell(
    command: str,
    cwd: str,
    description: str,
    shell: str,
    dangerously_skip_sandbox: bool,
) -> str:
    """Hand the command to the background registry and report its handle."""
    if has_private_pid_namespace(
        get_effective_sandbox_policy(), skip=dangerously_skip_sandbox
    ):
        return _background_pid_namespace_refusal()
    # lazy: zrb internal — keeps the background registry off the hot
    # path most Shell calls take (foreground, non-backgrounded).
    from zrb.llm.capabilities.tool.shell.background import get_shell_background_registry

    try:
        handle = await get_shell_background_registry().start(
            command, cwd, description, shell, dangerously_skip_sandbox
        )
    except SandboxUnavailableError as e:
        return format_sandbox_denied_message(e)
    return (
        f"Started background process. Handle: {handle}. "
        "Call MonitorProcess with this handle to check status."
    )


def _background_pid_namespace_refusal() -> str:
    """Model-facing refusal for a background shell inside a PID namespace."""
    return (
        "Command refused: background shells are unavailable while the Linux "
        "sandbox gives each command its own PID namespace. The sandbox's "
        "processes die when it exits, and the PIDs inside it are not host "
        "PIDs, so a handle could not track or kill them. Run the command in "
        "the foreground, or set "
        f"{CFG.ENV_PREFIX}_LLM_SANDBOX_OS_SHELL=off to disable the OS sandbox "
        "for shell commands. [SYSTEM SUGGESTION]: call Shell with "
        "background=False."
    )


class _LiveShellUI(Protocol):
    """A UI that shows a command's output as one live, expandable line.

    Neither method is on `AnyUI`: a headless or minimal UI omits them, which is
    why the shell tool narrows to this protocol at the call instead of requiring
    every UI to carry them.
    """

    def update_shell_output(self, key: str, text: str) -> None: ...

    def finish_shell_output(self, key: str, summary: str, full_text: str) -> None: ...


def _live_shell_ui(ui: object) -> "_LiveShellUI | None":
    """*ui* as a live shell renderer, or None when it cannot render one."""
    if ui is None:
        return None
    if not callable(getattr(ui, "update_shell_output", None)):
        return None
    if not callable(getattr(ui, "finish_shell_output", None)):
        return None
    return cast("_LiveShellUI", ui)


def _build_stream_captures(
    max_chars: int, supports_live_collapse: bool
) -> tuple[StreamCapture, StreamCapture]:
    """A stdout/stderr capture pair; no console echo when the UI shows a live line.

    Capped only by the command's own timeout, so the full-output dump these
    captures feed is the whole stream. The cap belongs to a background process,
    which has no deadline; an adopted foreground capture keeps this one, and the
    time it may then run in the background bounds it instead.
    """
    echo_cap = CFG.LLM_MAX_CONSOLE_OUTPUT_CHARS
    return (
        StreamCapture(
            max_chars,
            echo_cap,
            print_live=not supports_live_collapse,
            cap_spill=False,
        ),
        StreamCapture(
            max_chars,
            echo_cap,
            print_live=not supports_live_collapse,
            cap_spill=False,
        ),
    )


def _close_transport_if_started(process: "asyncio.subprocess.Process | None") -> None:
    """Close *process*'s pipes. A timeout cancels the drain before it does, and
    left open they warn at GC once the loop is gone."""
    if process is not None:
        close_transport(process)


async def _kill_if_still_running(process: "asyncio.subprocess.Process | None") -> None:
    """Terminate *process* if it's still running."""
    if process is not None and process.returncode is None:
        await terminate_process(
            process,
            CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
            print_method=CFG.LOGGER.warning,
        )


def _combined_echo(stdout_cap: StreamCapture, stderr_cap: StreamCapture) -> str:
    """The command's echo so far, stdout then stderr as separate sections
    (their interleaving is not tracked)."""
    sections = []
    if stdout_cap.echoed_text:
        sections.append(stdout_cap.echoed_text)
    if stderr_cap.echoed_text:
        sections.append(f"[stderr]\n{stderr_cap.echoed_text}")
    return "\n".join(sections)


def _format_live_shell_output(text: str) -> str:
    """Two-space indent per line, with a leading newline."""
    return "\n  " + text.replace("\n", "\n  ")


def _make_live_shell_output_pusher(
    ui: "_LiveShellUI",
    key: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
) -> "Callable[[], None]":
    """Build a callback pushing the combined echo to `key`'s live line,
    throttled to `_LIVE_UPDATE_INTERVAL` (each update is an O(buffer) splice).
    Skipped updates lose nothing: `_finish_shell_output` uses the full echo.
    UI errors are swallowed.
    """
    last_update = 0.0

    def _push() -> None:
        nonlocal last_update
        now = time.monotonic()
        if now - last_update < _LIVE_UPDATE_INTERVAL:
            return
        last_update = now
        try:
            ui.update_shell_output(
                key,
                _format_live_shell_output(_combined_echo(stdout_cap, stderr_cap)),
            )
        except Exception as e:  # noqa: BLE001
            CFG.LOGGER.debug(f"Live shell output push failed: {e}")

    return _push


def _finish_shell_output(
    ui: "_LiveShellUI",
    key: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
) -> None:
    """Collapse `key`'s live line into a one-line, expandable summary.

    Runs on every exit path so an aborted command never leaves its echo open.
    """
    try:
        full = _combined_echo(stdout_cap, stderr_cap)
        if not full:
            return
        char_count = len(full.strip())
        collapsed = _format_live_shell_output(f"💻 Output ({char_count} chars)")
        ui.finish_shell_output(key, collapsed, _format_live_shell_output(full))
    except Exception as e:  # noqa: BLE001
        CFG.LOGGER.debug(f"Final shell output capture failed: {e}")


def _can_track_pids(shell_flag: str, private_pid_namespace: bool) -> bool:
    """Whether the wrapper may report background PIDs for this command.

    Discovery needs POSIX process groups plus pgrep/ps, and a PID namespace's
    pids are not host pids: reporting them would let the model signal an
    unrelated process.
    """
    return (
        platform.system() != "Windows"
        and shell_flag == "-c"
        and not private_pid_namespace
    )


def _prepare_command(command: str, use_pid_tracking: bool) -> tuple[str, str | None]:
    """Wrap the command to capture background PIDs when on a POSIX shell.

    Every wrapper token gets its own line: a `;`-spliced wrapper breaks a
    command ending in a heredoc, a comment, a `;` or a newline.
    """
    # `{ }` is a syntax error, so an empty command is not wrapped.
    if not use_pid_tracking or not command.strip():
        return command, None

    fd, temp_pid_file = tempfile.mkstemp(prefix="zrb_pids_")
    os.close(fd)

    # `|| echo $$`: under macOS Seatbelt a sandboxed shell cannot exec the
    # setuid /bin/ps, but the shell is the group leader there, so $$ is the
    # PGID. $$ is written first so it can be excluded even when a wrapper
    # makes process.pid != $$.
    wrapper_command = (
        f"echo $$ > {temp_pid_file}\n"
        f"{{\n{command}\n}}\n"
        f"__code=$?\n"
        f"pgrep -g $(ps -o pgid= -p $$ 2>/dev/null || echo $$) "
        f">> {temp_pid_file} 2>/dev/null\n"
        f"exit $__code"
    )
    return wrapper_command, temp_pid_file


def _build_sandboxed_shell_argv(
    shell: str, shell_flag: str, command: str, skip: bool
) -> tuple[list[str], str | None]:
    """Wrap the shell invocation per the sandbox policy; return ``(argv, note)``.

    Raises ``SandboxUnavailableError`` in fallback="deny" mode.
    """
    # lazy: tests patch zrb.llm.capabilities.sandbox.build_sandboxed_argv; hoisting bypasses the mock
    from zrb.llm.capabilities.sandbox import build_sandboxed_argv

    policy = get_effective_sandbox_policy()
    return build_sandboxed_argv([shell, shell_flag, command], policy, skip=skip)


async def start_process(argv: list[str], cwd: str) -> asyncio.subprocess.Process:
    """Start a (possibly sandbox-wrapped) command with piped output."""
    # Its own session/process group (setsid; ignored on Windows) lets
    # `pgrep -g` and kill reach the whole tree, and survives the sandbox
    # wrappers, which exec in place. DEVNULL stdin fails a stdin read fast.
    return await asyncio.create_subprocess_exec(
        *create_yielding_argv(argv),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        cwd=cwd,
        start_new_session=True,
        # asyncio's default 64KB StreamReader limit makes readline() raise on a
        # single long line (minified JS, one-line JSON logs), losing all output.
        # 8MB line ceiling; switch to chunked read() if ever exceeded.
        limit=8 * 1024 * 1024,
    )


async def _read_stream(
    stream: asyncio.StreamReader,
    capture: StreamCapture,
    on_chunk: "Callable[[], None] | None" = None,
) -> None:
    """Read a stream line by line into *capture*, calling `on_chunk` after each line."""
    if not stream:
        return
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode(errors="replace")
        if decoded:
            stripped = strip_ansi(decoded)
            capture.echo(stripped)
            capture.feed(stripped)
            if on_chunk is not None:
                on_chunk()


def _collect_background_pids(temp_pid_file: str | None, process_pid: int) -> list[int]:
    """Read background PIDs from the temp file and remove it.

    Excludes the first line (the shell's ``$$``), ``process_pid``, this
    process, and PID 1. Under the Linux sandbox the shell runs in its own PID
    namespace, where the wrapper's ``pgrep -g`` also lists bwrap's namespace
    init as PID 1; it is never a command's background child, and PID 1 on the
    host is init too.
    """
    bg_pids = []
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            with open(temp_pid_file, "r", encoding="utf-8") as f:
                pids = [int(ln.strip()) for ln in f if ln.strip().isdigit()]
            shell_pid = pids[0] if pids else -1
            for pid in pids[1:]:
                if pid not in (1, process_pid, shell_pid, os.getpid()):
                    bg_pids.append(pid)
            os.remove(temp_pid_file)
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to parse background PIDs: {e}")
    return bg_pids


def _cleanup_temp_file(temp_pid_file: str | None):
    """Safely removes the temp file if it exists."""
    if temp_pid_file and os.path.exists(temp_pid_file):
        try:
            os.remove(temp_pid_file)
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to remove temp PID file: {e}")


MOVE_TIMEOUT = "timeout"
"""The command's own timeout ran out."""

MOVE_CUT = "cut"
"""The user's send-now key needed the turn back."""


async def _wait_for_exit_or_adopt(
    process: "asyncio.subprocess.Process",
    command: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    on_chunk: "Callable[[], None] | None",
    timeout: int,
    drain_notices: list[str],
    allow_adopt: bool = True,
) -> "tuple[str, str | None]":
    """Wait for the command; report what ended the wait and its handle.

    An empty first element means the command finished on its own. Otherwise it
    is `MOVE_TIMEOUT` or `MOVE_CUT`, and either may have moved the process to
    the background (returning its handle) or left it where it is — see
    `_adopt_or_none` and `_can_adopt` for which, and why. `allow_adopt` false
    keeps the process in the foreground (a private PID namespace makes an
    adopted process untrackable), so a timeout kills it instead.
    """
    # No return_exceptions: a broken reader should abort immediately.
    if process.stdout is None or process.stderr is None:
        raise RuntimeError(
            "the shell process started without the pipes its output is read from"
        )
    readers = asyncio.gather(
        _read_stream(process.stdout, stdout_cap, on_chunk),
        _read_stream(process.stderr, stderr_cap, on_chunk),
    )
    drain = asyncio.ensure_future(
        wait_for_exit_and_drain(process, readers, reporter=drain_notices.append)
    )
    # Wait for a cut newer than this run has seen: the one that arrived before
    # this command started belongs to a tool call that has already returned.
    cut = get_run_shell_cut_signal()
    cut_wait = (
        asyncio.ensure_future(cut.wait_for_cut(cut.generation))
        if cut is not None
        else None
    )
    deadline = asyncio.get_running_loop().time() + timeout
    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            waiters = {drain} if cut_wait is None else {drain, cut_wait}
            done, _ = await asyncio.wait(
                waiters, timeout=max(remaining, 0), return_when=asyncio.FIRST_COMPLETED
            )
            if drain in done:
                drain.result()
                return "", None
            if not done:
                await _stop(drain)
                handle = await _adopt_or_none(
                    process, command, stdout_cap, stderr_cap, allow_adopt=allow_adopt
                )
                if handle is None:
                    await terminate_process(
                        process,
                        CFG.LLM_SHELL_KILL_WAIT_TIMEOUT / 1000,
                        print_method=CFG.LOGGER.warning,
                    )
                return MOVE_TIMEOUT, handle
            if not _can_adopt(command, allow_adopt=allow_adopt):
                # Nothing to step aside for: the wait is the work, or adoption
                # is off. Killing it is not what the user asked for, so keep
                # waiting — the deadline still applies. `done` holds something
                # that is not the drain, and the cut wait is the only other
                # waiter, so the cut is what ended this round: drop it and wait
                # for the next one. `_stop` takes a None cut as nothing to stop.
                await _stop(cut_wait)
                cut_wait = None
                continue
            await _stop(drain)
            handle = await _adopt_process(process, command, stdout_cap, stderr_cap)
            return MOVE_CUT, handle
    finally:
        await _stop(cut_wait)
        await _stop(drain)


async def _stop(task: "asyncio.Future[T] | None") -> None:
    """Cancel *task* if it is still running, and never let its outcome escape.

    A drain that ends this way is expected: its own `finally` cancels the
    readers, which is exactly what handing the pipes to the registry needs.
    """
    if task is None:
        return
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _can_adopt(command: str, allow_adopt: bool = True) -> bool:
    """Whether this command may be moved out of the foreground.

    Adoption turned off (``LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS`` is 0) leaves
    nowhere to move it, a deliberate wait (`_is_deliberate_wait`) is never
    moved, and `allow_adopt` false says the sandbox makes it untrackable.
    """
    return (
        allow_adopt
        and CFG.LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS > 0
        and not _is_deliberate_wait(command)
    )


async def _adopt_or_none(
    process: "asyncio.subprocess.Process",
    command: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    allow_adopt: bool = True,
) -> "str | None":
    """Move the process to the background, unless `_can_adopt` says no."""
    if not _can_adopt(command, allow_adopt=allow_adopt):
        return None
    return await _adopt_process(process, command, stdout_cap, stderr_cap)


async def _adopt_process(
    process: "asyncio.subprocess.Process",
    command: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
) -> str:
    """Keep a process the caller stopped waiting for, under a background handle.

    The pipes and the captures are the caller's and still open, so the output
    the process has already produced stays where the report left off.
    """
    # lazy: zrb internal — keeps the background registry off the hot
    # path most Shell calls take (foreground, non-adopted).
    from zrb.llm.capabilities.tool.shell.background import get_shell_background_registry

    return await get_shell_background_registry().adopt(
        process, command, stdout_cap, stderr_cap
    )


def _is_deliberate_wait(command: str) -> bool:
    """True for a command whose whole job is to wait: a `sleep`.

    The delay is the work, so moving it to the background would only let the
    next command run before the wait it was waiting for was over.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    return bool(tokens) and os.path.basename(tokens[0]) == "sleep"


def _moved_to_background_note(handle: str, timeout: int, reason: str) -> str:
    """Report a command that is still alive, and how to reach it."""
    call = f"MonitorProcess(handle='{handle}'"
    tail = (
        f"Call {call}) to read the output it has produced since, "
        f"{call}, wait=30) to block for it, or {call}, kill=True) to stop it. "
        "Do not run the command again: that starts a second copy. zrb kills it "
        f"after {CFG.LLM_SHELL_TIMEOUT_BACKGROUND_SECONDS}s in the background."
    )
    if reason == MOVE_CUT:
        return (
            f"Handle: {handle}\n"
            "[SYSTEM SUGGESTION]: The user sent a message that needs this turn "
            "while the command was running, so the command was moved to the "
            f"background as '{handle}' instead of holding the turn. Read the "
            "message first. It was NOT killed, and the work it has already done "
            f"is not lost. {tail}"
        )
    return (
        f"Handle: {handle}\n"
        f"[SYSTEM SUGGESTION]: The command did not finish within {timeout}s, so "
        f"it is still running in the background as '{handle}'. It was NOT "
        "killed, and the work it has already done is not lost. " + tail
    )


def _present_result(
    result: str,
    sandbox_note: "str | None",
    handle: "str | None",
    timeout: int,
    reason: str = "",
) -> str:
    """The sandbox note above the report, the background handle below it."""
    if sandbox_note:
        result = f"{sandbox_note}\n{result}"
    if handle is not None:
        result = f"{result}\n{_moved_to_background_note(handle, timeout, reason)}"
    return result


def _format_output(
    command: str,
    cwd: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    returncode: int | None,
    bg_pids: list[int],
    reason: str,
    timeout: int,
    drain_notice: str | None = None,
    handle: "str | None" = None,
    background_available: bool = True,
) -> str:
    """Formats the command execution result into a readable string.

    *reason* is what ended the wait early — ``""`` when the command finished on
    its own — and *handle* is set when the command was moved to the background
    instead of being killed. Its captures outlive this call and the entry in
    the registry keeps feeding them. *background_available* false tells the
    timeout advice not to recommend a background run the sandbox will refuse.
    """
    timed_out = reason == MOVE_TIMEOUT
    still_running = handle is not None
    exit_code_str = str(returncode) if returncode is not None else "(none)"
    failed = timed_out or (returncode is not None and returncode != 0)
    stdout_str = _display_text(stdout_cap, failed)
    stderr_str = _display_text(stderr_cap, failed)
    if still_running:
        exit_code_str = (
            "(moved to background so the turn could continue)"
            if reason == MOVE_CUT
            else f"(moved to background after {timeout}s)"
        )
    elif timed_out:
        exit_code_str = "(timed out)"
        stderr_str += f"\nError: Command timed out after {timeout} seconds."

    flooded = stdout_cap.truncated or stderr_cap.truncated
    total_chars = stdout_cap.total_chars + stderr_cap.total_chars
    note = ""
    if flooded and still_running:
        # A dump would close the spill files, and the capture's next overflow
        # would open a *new* one holding only what was written after adoption —
        # a file that claims to be the command's output while starting
        # mid-stream. The live spill is already complete and keeps growing.
        note = _live_overflow_note(stdout_cap, stderr_cap)
    elif flooded:
        dump_path = _dump_full_output(
            command, cwd, stdout_cap, stderr_cap, exit_code_str
        )
        note = _overflow_note(dump_path, failed)
    if drain_notice:
        stderr_str += f"\n{drain_notice}"
    if not still_running:
        # The captures outlive this call when the command is still running.
        stdout_cap.discard()
        stderr_cap.discard()

    suggestion = _suggest_next_step(
        command,
        stdout_str,
        stderr_str,
        timed_out and not still_running,
        timeout,
        flooded,
        total_chars,
        background_available=background_available,
    )
    return _assemble_output(
        command,
        cwd,
        stdout_str,
        stderr_str,
        exit_code_str,
        bg_pids,
        note,
        suggestion,
    )


def _display_text(capture: StreamCapture, failed: bool) -> str:
    """The stream as the model sees it: whole when it fits, else the useful end.

    A command that succeeded ends with its result, so its tail is the part
    worth keeping. A failed one announces its cause at the top — the first
    traceback line, the first compiler error — and only summarizes it at the
    bottom, so it keeps both.
    """
    if failed and capture.truncated:
        return _head_and_tail(capture)
    return capture.text


def _head_and_tail(capture: StreamCapture) -> str:
    """A failed stream's beginning and end, within the text already retained."""
    budget = len(capture.text)
    head = capture.head_text(int(budget * _HEAD_SHARE_OF_FAILED_OUTPUT))
    tail = capture.text[-(budget - len(head)) :] if budget > len(head) else ""
    elided = capture.total_chars - len(head) - len(tail)
    if elided <= 0:
        return capture.text
    return f"{head}\n… [{elided} characters elided] …\n{tail}"


def _overflow_note(dump_path: str | None, failed: bool) -> str:
    """What the model is told about output that did not fit."""
    if not dump_path:
        return ""
    kept = "the beginning and the end of a failed command" if failed else "the tail"
    return (
        f"[SYSTEM SUGGESTION]: Output truncated (kept {kept}). Full "
        f"stdout/stderr saved to {dump_path} — Grep it to locate sections, "
        "then Read."
    )


def _live_overflow_note(stdout_cap: StreamCapture, stderr_cap: StreamCapture) -> str:
    """Name the spill files a command that is still running keeps writing into.

    Unlike `_overflow_note`'s dump, these files are not a snapshot: the capture
    appends to them for as long as the process lives, so they hold the output
    from the start of the command, not from the moment it was adopted.
    """
    live = []
    for name, capture in (("stdout", stdout_cap), ("stderr", stderr_cap)):
        if capture.truncated and capture.spill_path:
            capture.flush()
            live.append(f"{name} in {capture.spill_path}")
    if not live:
        return ""
    return (
        "[SYSTEM SUGGESTION]: Output truncated (kept the beginning and the "
        f"end). The complete output is still being appended to {'; '.join(live)} "
        "— the same path MonitorProcess reports. Grep it to locate a section, "
        "then Read that range."
    )


def _assemble_output(
    command: str,
    cwd: str,
    stdout_str: str,
    stderr_str: str,
    exit_code_str: str,
    bg_pids: list[int],
    overflow_note: str,
    suggestion: str,
) -> str:
    output_parts = [
        f"Command: {command}",
        f"Directory: {cwd}",
        f"Stdout:\n{stdout_str.strip() or '(empty)'}",
        f"Stderr:\n{stderr_str.strip() or '(empty)'}",
        f"Exit Code: {exit_code_str}",
        f"Background PIDs: {', '.join(map(str, bg_pids)) if bg_pids else '(none)'}",
    ]
    if overflow_note:
        output_parts.append(f"\n{overflow_note}")
    if suggestion:
        output_parts.append(f"\n{suggestion}")
    return "\n".join(output_parts)


def _timeout_suggestion(
    timeout: int,
    flooded: bool,
    total_chars: int,
    background_available: bool = True,
) -> str:
    """Tell a hung process apart from one drowning in its own output."""
    if not background_available:
        keep_running = (
            "If it is meant to keep running, background shells are "
            "unavailable while the Linux sandbox uses a private PID "
            "namespace; run it in the foreground or set "
            f"{CFG.ENV_PREFIX}_LLM_SANDBOX_OS_SHELL=off to enable one."
        )
    elif flooded:
        keep_running = "If it is meant to keep running, use background=True instead."
    else:
        keep_running = (
            "If it was meant to keep running (a server, watcher, or tail -f), "
            "re-run it with background=True and check it with MonitorProcess."
        )
    if flooded:
        return (
            "[SYSTEM SUGGESTION]: The command timed out after "
            f"{timeout}s having already produced {total_chars} characters — it "
            "was still writing, not waiting on input. Do not re-run it "
            "unchanged. Re-run a bounded form: scope it to a path, add a "
            "summarizing flag (`git diff --stat`, `--name-only`, `-l`), pipe "
            "through `head`/`wc -l`, or redirect to a file and Grep that. "
            f"{keep_running}"
        )
    return (
        "[SYSTEM SUGGESTION]: The command timed out and the tool terminated "
        f"it — there is nothing left to kill. {keep_running} If it was meant "
        "to finish, do not re-run it unchanged: 'ps aux | grep <name>' tells "
        "you whether anything survived the kill. If nothing did, it was "
        "genuinely too slow or blocked — scope the work to a path, add a "
        "summarizing flag, or pass a non-interactive flag like '-y' or "
        "'CI=true' before retrying. Next time, prefer the bounded form up front."
    )


def _suggest_next_step(
    command: str,
    stdout_str: str,
    stderr_str: str,
    timed_out: bool,
    timeout: int,
    flooded: bool,
    total_chars: int,
    background_available: bool = True,
) -> str:
    """Map a recognizable failure shape to the next action worth taking."""
    suggestion = ""
    combined_output = (stdout_str + stderr_str).lower()
    if timed_out:
        suggestion = _timeout_suggestion(
            timeout, flooded, total_chars, background_available=background_available
        )
    elif "lock" in combined_output and (
        "apt" in command or "brew" in command or "dpkg" in command
    ):
        suggestion = (
            "[SYSTEM SUGGESTION]: A package manager lock was detected. "
            "Another installation process might be running. "
            "Do NOT force kill it immediately. Wait a moment and check running processes."
        )
    elif "permission denied" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Permission denied. Look for a user-level "
            "fix first: install to the user's prefix, use a non-privileged "
            "port or path, or check the file's owner and group. Reaching for "
            "sudo is a last resort, and only if it is actually available."
        )
    elif "address already in use" in combined_output or "eaddrinuse" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: A port is already in use. "
            "Find the holder with 'lsof -i :<port>' or 'ss -tlnp | grep <port>' "
            "before killing or choosing a different port."
        )
    elif "command not found" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Command not found. "
            "Check that the tool is installed and on PATH. "
            "If using a virtualenv or nvm/pyenv, verify it is activated."
        )
    elif (
        "no module named" in combined_output or "modulenotfounderror" in combined_output
    ):
        suggestion = (
            "[SYSTEM SUGGESTION]: Python module not found. "
            "Verify the virtualenv is activated and run 'pip install <package>' if missing."
        )
    elif "econnrefused" in combined_output or "connection refused" in combined_output:
        suggestion = (
            "[SYSTEM SUGGESTION]: Connection refused. "
            "The target service may not be running. "
            "Check with 'ps aux | grep <service>' or 'docker ps' before retrying."
        )
    return suggestion


def _dump_full_output(
    command: str,
    cwd: str,
    stdout_cap: StreamCapture,
    stderr_cap: StreamCapture,
    exit_code_str: str,
) -> str | None:
    """Persist untruncated output to a temp file; return its path, or None on failure."""
    # not auto-deleted; the OS reaps its temp dir. Add cleanup only if it bloats.
    try:
        fd, path = tempfile.mkstemp(prefix="zrb_shell_", suffix=".log")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                f"Command: {command}\nDirectory: {cwd}\nExit Code: {exit_code_str}\n\n"
            )
            f.write("=== STDOUT ===\n")
            stdout_cap.write_full(f)
            f.write("\n\n=== STDERR ===\n")
            stderr_cap.write_full(f)
            f.write("\n")
        return path
    except Exception:
        return None


run_shell_command.__name__ = "Shell"
tag(run_shell_command, Capability.EXECUTE)
