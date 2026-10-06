"""Pipe and thread plumbing for a command hook's subprocess."""

import asyncio
import os
import selectors
import subprocess
import threading
from typing import Any, Callable

# One selector poll; one quiet interval after the child exits ends the read.
_HOOK_DRAIN_INTERVAL = 0.05

# Bounded so a large stdin payload cannot monopolize the loop between polls.
_PIPE_WRITE_CHUNK = 32768


def read_hook_output(
    process: subprocess.Popen, stdin_payload: bytes
) -> tuple[bytes, bytes]:
    """Feed stdin and collect stdout/stderr, returning once the *child* exits.

    ``Popen.communicate`` waits for pipe EOF, which never comes when a hook
    backgrounds work (``cmd & disown``) and a descendant keeps the pipes open.
    Output written by descendants after the child exits is dropped. Pipes are
    drained throughout so a hook writing more than a pipe buffer cannot block.

    POSIX only; Windows cannot poll pipes, so it falls back to ``communicate``.
    """
    if os.name != "posix":
        return process.communicate(input=stdin_payload)

    sel = selectors.DefaultSelector()
    collected: dict[int, list[bytes]] = {}
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    pending = memoryview(stdin_payload)
    try:
        for pipe, chunks in (
            (process.stdout, stdout_chunks),
            (process.stderr, stderr_chunks),
        ):
            if pipe is not None:
                os.set_blocking(pipe.fileno(), False)
                sel.register(pipe, selectors.EVENT_READ)
                collected[pipe.fileno()] = chunks
        if process.stdin is not None:
            if pending:
                os.set_blocking(process.stdin.fileno(), False)
                sel.register(process.stdin, selectors.EVENT_WRITE)
            else:
                _close_pipe(process.stdin)

        while sel.get_map():
            events = sel.select(timeout=_HOOK_DRAIN_INTERVAL)
            for key, _ in events:
                if key.fileobj is process.stdin:
                    pending = _write_stdin(sel, process.stdin, pending)
                else:
                    _read_pipe(sel, key, collected[key.fd])
            if process.poll() is None:
                continue
            # The child is gone: leave after one poll that returned no events.
            # "No events", not "read nothing": a poll that only saw stdin
            # writable returned early and proves no quiet interval.
            if process.stdin is not None:
                _unregister(sel, process.stdin)
                _close_pipe(process.stdin)
            if not events:
                break
    finally:
        sel.close()
        for pipe in (process.stdin, process.stdout, process.stderr):
            _close_pipe(pipe)
    # Match communicate(), which ends with wait(), so returncode is set.
    if process.poll() is None:
        process.wait()
    return b"".join(stdout_chunks), b"".join(stderr_chunks)


def _read_pipe(sel: "selectors.BaseSelector", key: Any, chunks: list[bytes]) -> None:
    """Drain one ready pipe; unregister and close it at EOF."""
    try:
        data = os.read(key.fd, 32768)
    except BlockingIOError:
        return
    except OSError:
        data = b""
    if data:
        chunks.append(data)
        return
    _unregister(sel, key.fileobj)
    _close_pipe(key.fileobj)


def _write_stdin(
    sel: "selectors.BaseSelector", stdin: Any, pending: memoryview
) -> memoryview:
    """Write what fits of *pending*; close stdin once it is fully delivered."""
    try:
        written = os.write(stdin.fileno(), pending[:_PIPE_WRITE_CHUNK])
    except BlockingIOError:
        return pending
    except (OSError, ValueError):
        # Broken pipe (child gone or never read stdin) or an already-closed fd.
        _unregister(sel, stdin)
        _close_pipe(stdin)
        return memoryview(b"")
    pending = pending[written:]
    if not pending:
        _unregister(sel, stdin)
        _close_pipe(stdin)
    return pending


def _unregister(sel: "selectors.BaseSelector", fileobj: Any) -> None:
    """Drop *fileobj* from the selector, tolerating an already-dropped one."""
    try:
        sel.unregister(fileobj)
    except (KeyError, ValueError):
        pass


def _close_pipe(pipe: Any) -> None:
    """Close a pipe, swallowing any error so it cannot fail the hook run."""
    if pipe is None:
        return
    try:
        pipe.close()
    except Exception:
        pass


async def run_detached(
    func: Callable[[], Any], name: str
) -> (
    Any
):  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    """Await *func* running on a daemon thread.

    Not ``run_in_executor``: a hook pinned in a blocking read would starve the
    shared pool and, being a non-daemon worker, hang interpreter exit.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _settle(setter: Callable[[Any], None], value: Any) -> None:
        # wait_for may have cancelled the future on timeout.
        if not future.done():
            setter(value)

    def _post(setter: Callable[[Any], None], value: Any) -> None:
        try:
            loop.call_soon_threadsafe(_settle, setter, value)
        except RuntimeError:
            # Loop already closed — nobody is waiting on this result.
            pass

    def _runner() -> None:
        try:
            result = func()
        except BaseException as e:
            _post(future.set_exception, e)
        else:
            _post(future.set_result, result)

    threading.Thread(target=_runner, name=name, daemon=True).start()
    return await future
