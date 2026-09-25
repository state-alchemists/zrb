import asyncio
import codecs
import os
import re
import signal
import sys
from collections import deque
from collections.abc import Callable
from typing import Any, TextIO

import psutil

from zrb.cmd.cmd_result import CmdResult
from zrb.config.config import CFG
from zrb.config.helper import get_shell_name, get_windows_posix_shell


def check_unrecommended_commands(cmd_script: str) -> dict[str, str]:
    """Violating commands/patterns found in *cmd_script*, mapped to why each
    is unrecommended (non-POSIX, platform-inconsistent, or unsafe)."""
    banned_commands = {
        "column": "Command isn't included in Ubuntu packages and is not POSIX compliant",
        "eval": "Avoid eval as it can accidentally execute arbitrary strings",
        "realpath": "Not available by default on OSX",
        "source": "Not POSIX compliant; use '.' instead",
        "which": "Command in not POSIX compliant, use command -v",
    }
    banned_substrings = {
        "<(": "Process substitution isn't POSIX compliant and causes trouble",
    }
    banned_commands_regex = {
        r"grep.* -y": "grep -y does not work on Alpine; use grep -i",
        r"grep.* -P": "grep -P is not valid on OSX",
        r'readlink.+-.*f.+["$]': "readlink -f behaves differently on OSX",
        r"sort.*-V": "sort -V is not supported everywhere",
        r"sort.*--sort-versions": "sort --sort-version is not supported everywhere",
        r"(?:^|[|;&]\s*)ls\s": "Avoid using ls; use shell globs or find instead",
        # Plain `echo` is portable; only these two forms differ across shells.
        r"(?<![\w-])echo\s+-[neE]": (
            "echo -n/-e is not portable (dash and zsh differ); use printf instead"
        ),
        r"(?<![\w-])echo\s[^|;&]*\\": (
            "dash and zsh interpret backslash escapes in echo, bash does not; "
            "use printf instead"
        ),
    }
    violations = {}
    for cmd, reason in banned_commands.items():
        if re.search(rf"(?<![\w-]){re.escape(cmd)}(?![\w-])", cmd_script):
            violations[cmd] = reason
    for frag, reason in banned_substrings.items():
        if frag in cmd_script:
            violations[frag] = reason
    for pattern, reason in banned_commands_regex.items():
        if re.search(pattern, cmd_script):
            violations[pattern] = reason
    return violations


def resolve_shell(shell: str = "") -> tuple[str, str]:
    """Resolve a shell name into a ``(shell, flag)`` pair.

    An empty ``shell`` falls back to ``CFG.SHELL`` — the user's configured shell
    (``ZRB_SHELL`` / ``CFG.DEFAULT_SHELL``), or the detected current shell
    (``get_current_shell()``, which only ever returns a shell that exists).

    The flag is the "run this string" switch for the interpreter (``-c`` for
    POSIX shells, ``-Command`` for PowerShell, ``/c`` for cmd, ``-e``/``-r`` for
    runtimes).

    On Windows a bare ``bash``/``sh`` resolves to the absolute path of a real
    POSIX shell rather than being handed to the PATH lookup, which finds
    ``System32\\bash.exe`` -- the WSL launcher, not a shell. See
    ``get_windows_posix_shell``. Every other name is returned as given.

    Args:
        shell (str): The shell/interpreter to use. Empty uses ``CFG.SHELL``.

    Returns:
        tuple[str, str]: The resolved shell and its command flag.
    """
    shell = shell or CFG.SHELL
    flag = get_shell_flag(shell)
    # Only a bare name needs resolving to a path.
    if shell.lower() in ("bash", "sh"):
        shell = get_windows_posix_shell() or shell
    return shell, flag


_SHELL_FLAGS = {
    "node": "-e",
    "ruby": "-e",
    "php": "-r",
    "pwsh": "-Command",
    "powershell": "-Command",
    "cmd": "/c",
}


def get_shell_flag(shell: str) -> str:
    """The "run this string" flag for *shell*, looked up by shell name so an
    absolute path such as `C:\\...\\pwsh.exe` still gets `-Command`; `-c`
    for anything unlisted."""
    return _SHELL_FLAGS.get(get_shell_name(shell), "-c")


def _process_tree_pids(pid: int) -> list[int]:
    """Snapshot a process and its descendants' PIDs (best effort)."""
    try:
        parent = psutil.Process(pid)
        return [pid] + [child.pid for child in parent.children(recursive=True)]
    except psutil.NoSuchProcess:
        return [pid]


async def terminate_process(
    process: asyncio.subprocess.Process,
    grace_seconds: float,
    print_method: Callable[..., None] | None = None,
) -> None:
    """Gracefully terminate an asyncio subprocess tree, then force-kill survivors.

    The tree is snapshotted *before* signalling, because once the shell exits its
    children are reparented and can no longer be reached via the shell PID. After
    a SIGTERM-equivalent and a grace window, any snapshotted PID still alive is
    force-killed. Cross-platform via ``psutil``.

    Args:
        process (asyncio.subprocess.Process): The process to terminate.
        grace_seconds (float): How long to wait for graceful exit before forcing.
        print_method (Callable[..., None] | None): Status printer for kills.
    """
    if process.returncode is not None:
        return
    pids = _process_tree_pids(process.pid)
    terminate_pid(process.pid, print_method=print_method)
    try:
        await asyncio.wait_for(process.wait(), timeout=grace_seconds)
    except asyncio.TimeoutError:
        pass
    for pid in pids:
        if psutil.pid_exists(pid):
            kill_pid(pid, print_method=print_method)
    # Reap the child while the loop is alive; otherwise the child watcher logs
    # "Loop <...> that handles pid N is closed" at asyncio.run teardown.
    if process.returncode is None:
        try:
            await asyncio.wait_for(process.wait(), timeout=grace_seconds)
        except asyncio.TimeoutError:
            pass


def terminate_pid(pid: int, print_method: Callable[..., None] | None = None) -> None:
    """Gracefully terminate a process and its children (SIGTERM-equivalent).

    Cross-platform via ``psutil`` — unlike ``os.killpg`` this works on Windows.
    Pair with ``kill_pid`` to force-kill survivors after a grace period.

    Args:
        pid (int): The parent process ID.
        print_method (Callable[..., None] | None): Status printer. Defaults to
            the built-in ``print``.
    """
    actual_print_method = print_method if print_method is not None else print
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for proc in parent.children(recursive=True) + [parent]:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            actual_print_method(f"Failed to terminate process {proc.pid}: {e}")


async def run_command(
    cmd: list[str],
    cwd: str | None = None,
    env_map: dict[str, str] | None = None,
    print_method: Callable[..., None] | None = None,
    register_pid_method: Callable[[int], None] | None = None,
    max_output_line: int = 1000,
    max_error_line: int = 1000,
    max_display_line: int | None = None,
    timeout: float = 3600,
    is_interactive: bool = False,
) -> tuple[CmdResult, int]:
    """Execute a command, streaming stdout/stderr live as it arrives.

    Output reads like running the command in a terminal (`\\r`-driven progress
    is shown live). `is_interactive` (off by default) skips the new session and
    shares the parent's stdin, which can race; use it only for commands that
    need user input.
    """
    actual_print_method = print_method if print_method is not None else print
    if max_display_line is None:
        max_display_line = max(max_output_line, max_error_line)
    cmd_process = await __spawn(cmd, cwd, env_map, is_interactive)
    if register_pid_method is not None:
        register_pid_method(cmd_process.pid)
    assert cmd_process.stdout is not None and cmd_process.stderr is not None
    display_lines = deque(maxlen=max_display_line if max_display_line > 0 else 0)
    streams_task = asyncio.create_task(
        __read_streams(
            cmd_process.stdout,
            cmd_process.stderr,
            actual_print_method,
            max_output_line,
            max_error_line,
            display_lines,
        )
    )
    timeout_task = (
        asyncio.create_task(asyncio.sleep(timeout)) if timeout and timeout > 0 else None
    )
    wait_task = asyncio.create_task(cmd_process.wait())
    try:
        done, _ = await asyncio.wait(
            {wait_task, timeout_task} if timeout_task else {wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if timeout_task and timeout_task in done:
            raise asyncio.TimeoutError()
        return_code = wait_task.result()
        stdout, stderr = await streams_task
        display = "\r\n".join(display_lines)
        return CmdResult(stdout, stderr, display=display), return_code
    except (KeyboardInterrupt, asyncio.CancelledError, asyncio.TimeoutError):
        await __terminate_on_cancel(cmd_process, actual_print_method)
        raise
    finally:
        await __release_process(
            cmd_process, [t for t in (timeout_task, wait_task, streams_task) if t]
        )


async def __spawn(
    cmd: list[str],
    cwd: str | None,
    env_map: dict[str, str] | None,
    is_interactive: bool,
) -> "asyncio.subprocess.Process":
    """Start the child with piped output and a terminal-shaped environment.

    NO_COLOR is deliberately NOT set: per the NO_COLOR convention any non-empty
    value (even "0") disables color, so there is no value that "explicitly
    allows" it — absence simply inherits the user's choice.
    """
    child_env = (env_map or os.environ).copy()
    child_env["TERM"] = "xterm-256color"  # A capable but standard terminal
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=os.getcwd() if cwd is None else cwd,
        env=child_env,
        start_new_session=not is_interactive,
        stdin=__get_cmd_stdin(is_interactive),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=CFG.CMD_BUFFER_LIMIT,
    )


async def __release_process(
    cmd_process: "asyncio.subprocess.Process", helper_tasks: "list[asyncio.Task]"
) -> None:
    """Cancel the helper tasks and close the transport while the loop is alive.

    Left to GC, a dangling task or the transport's `__del__` can run after the
    loop is gone and raise "Event loop is closed".
    """
    for task in helper_tasks:
        task.cancel()
    await asyncio.gather(*helper_tasks, return_exceptions=True)
    transport = getattr(cmd_process, "_transport", None)
    if transport is not None:
        transport.close()


async def __terminate_on_cancel(
    cmd_process: "asyncio.subprocess.Process", print_method: Callable[..., None]
) -> None:
    """Best-effort termination of *cmd_process* on interrupt/cancel/timeout.

    Escalates to a forceful kill if graceful termination doesn't land within
    `CFG.CMD_CLEANUP_TIMEOUT`, and swallows any secondary error so the
    original interrupt/cancel/timeout always propagates from the caller.
    """
    try:
        if hasattr(os, "killpg"):
            os.killpg(cmd_process.pid, signal.SIGINT)
        else:
            # No POSIX process groups on Windows; psutil hard-kills the tree.
            terminate_pid(cmd_process.pid, print_method=print_method)
        await asyncio.wait_for(
            cmd_process.wait(), timeout=CFG.CMD_CLEANUP_TIMEOUT / 1000
        )
    except asyncio.TimeoutError:
        print_method(
            f"Process {cmd_process.pid} did not terminate gracefully, killing."
        )
        kill_pid(cmd_process.pid, print_method=print_method)
    except Exception:
        pass


def __get_cmd_stdin(is_interactive: bool) -> int | TextIO:
    if is_interactive and sys.stdin.isatty():
        return sys.stdin
    return asyncio.subprocess.DEVNULL


async def __read_streams(
    stdout_stream: asyncio.StreamReader,
    stderr_stream: asyncio.StreamReader,
    print_method: Callable[..., None],
    max_output_line: int,
    max_error_line: int,
    display_queue: deque[Any],
) -> tuple[str, str]:
    """Read stdout and stderr from one multiplexed loop.

    One loop reacting to whichever stream has data keeps interleaved output
    close to write order; two reader tasks could each drain a buffered burst
    before yielding. Raw `read()` rather than `readline()` shows `\r`-driven
    progress live and cannot raise on a chunk over the stream's buffer limit.
    A line with no `\r`/`\n` is force-flushed past `CFG.CMD_BUFFER_LIMIT`.

    Writes to both pipes at the same instant have no recoverable order.
    """
    streams = {"stdout": stdout_stream, "stderr": stderr_stream}
    states = {
        "stdout": __StreamState(max_output_line),
        "stderr": __StreamState(max_error_line),
    }
    pending = {
        name: asyncio.ensure_future(stream.read(65536))
        for name, stream in streams.items()
    }
    try:
        while pending:
            done, _ = await asyncio.wait(
                pending.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for name in list(pending.keys()):
                if pending[name] not in done:
                    continue
                chunk = __resolve_chunk(pending.pop(name))
                if not chunk:
                    __finalize_stream(states[name], print_method, display_queue)
                    continue
                __feed_stream(states[name], chunk, print_method, display_queue)
                pending[name] = asyncio.ensure_future(streams[name].read(65536))
    finally:
        for future in pending.values():
            future.cancel()
    return (
        "\r\n".join(states["stdout"].captured),
        "\r\n".join(states["stderr"].captured),
    )


class __StreamState:
    """Decode/line-buffer state for one subprocess stream."""

    def __init__(self, max_line: int) -> None:
        self.max_line = max_line
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.buffer = ""
        self.captured: deque[str] = deque(maxlen=max_line if max_line > 0 else 0)


def __resolve_chunk(future: "asyncio.Future[bytes]") -> bytes:
    try:
        return future.result()
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except Exception:
        return b""


def __emit_line(
    state: __StreamState,
    line: str,
    print_method: Callable[..., None],
    display_queue: deque[Any],
) -> None:
    clean_part = line.rstrip()
    if not clean_part:
        return
    try:
        print_method(clean_part, end="\r\n")
    except Exception:
        print_method(clean_part)
    if state.max_line > 0:
        state.captured.append(clean_part)
        display_queue.append(clean_part)


def __feed_stream(
    state: __StreamState,
    chunk: bytes,
    print_method: Callable[..., None],
    display_queue: deque[Any],
) -> None:
    state.buffer += state.decoder.decode(chunk)
    while True:
        match = re.search(r"[\r\n]", state.buffer)
        if match is None:
            break
        __emit_line(state, state.buffer[: match.start()], print_method, display_queue)
        state.buffer = state.buffer[match.end() :]
    if len(state.buffer) > CFG.CMD_BUFFER_LIMIT:
        __emit_line(state, state.buffer, print_method, display_queue)
        state.buffer = ""


def __finalize_stream(
    state: __StreamState,
    print_method: Callable[..., None],
    display_queue: deque[Any],
) -> None:
    state.buffer += state.decoder.decode(b"", final=True)
    __emit_line(state, state.buffer, print_method, display_queue)


def kill_pid(pid: int, print_method: Callable[..., None] | None = None):
    """Kill a process and its children given the parent process ID.

    Args:
        pid (int): The process ID of the parent process.
        print_method (Callable[..., None] | None): A method to print status messages.
            Defaults to the built-in print function.
    """
    actual_print_method = print_method if print_method is not None else print
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            actual_print_method(f"Killing child process {child.pid}")
            child.kill()
        actual_print_method(f"Killing process {pid}")
        parent.kill()
    except psutil.NoSuchProcess:
        actual_print_method(f"Process with pid: {pid} already terminated")
