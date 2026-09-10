"""Pipe and thread plumbing for a command hook's subprocess.

Everything here exists to run one hook subprocess to completion without leaking
a thread, a pipe, or a descendant's output. `zrb.llm.hook.creator` is the only
caller; the kill side of the same problem lives in the sibling
`zrb.llm.hook.process_kill`.
"""

import asyncio
import os
import selectors
import subprocess
import threading
from typing import Any, Callable

# How long read_hook_output blocks in one selector poll. Also the extra latency
# it costs a hook whose descendants hold the pipes open past the child's exit:
# one quiet interval is what proves nothing more is coming.
_HOOK_DRAIN_INTERVAL = 0.05

# Bounded so a large stdin payload cannot monopolize the loop between polls.
_PIPE_WRITE_CHUNK = 32768


def read_hook_output(
    process: subprocess.Popen, stdin_payload: bytes
) -> tuple[bytes, bytes]:
    """Feed stdin and collect stdout/stderr, returning once the *child* exits.

    ``Popen.communicate`` returns at pipe **EOF**, which is not the same event.
    A hook that backgrounds work and returns immediately — ``cmd & disown``, the
    shape Claude-Code notifiers use — leaves a descendant holding the inherited
    write ends, so EOF never comes: a hook that *succeeded* in milliseconds gets
    reported as a timeout, every single firing. The child's own exit is the
    event that actually decides the hook, and everything the child wrote is in
    the pipe buffer by the time it exits, so nothing of its output is lost.

    Output a *descendant* writes after the parent exits is dropped. That output
    could never have been used: the hook's result is already decided.

    Draining runs throughout rather than only after exit. A hook writing more
    than one pipe buffer (~64 KiB) blocks in ``write`` until someone reads, so
    "wait, then read" would deadlock exactly the hooks with the most to say.

    POSIX only. The Windows selector cannot poll pipes and its fds have no
    non-blocking mode, so Windows keeps ``communicate`` — where a leaked
    descendant is instead handled by the psutil child walk in
    ``zrb.llm.hook.process_kill.kill_process_tree``.
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
            # The child is gone: stop feeding it, and leave as soon as a full
            # poll interval turns up nothing at all. Whatever still holds these
            # pipes open is a descendant that outlived it.
            #
            # The exit test is "this poll returned nothing", not "this poll read
            # nothing". A poll that only saw stdin *writable* returned early —
            # stdin is writable from the moment the child is spawned — so it
            # proves nothing about a quiet interval, and a fast child's buffered
            # output would be closed unread.
            if process.stdin is not None:
                _unregister(sel, process.stdin)
                _close_pipe(process.stdin)
            if not events:
                break
    finally:
        sel.close()
        for pipe in (process.stdin, process.stdout, process.stderr):
            _close_pipe(pipe)
    # communicate() ends with wait(); match it, so returncode is always set for
    # the caller. Only reachable via EOF-before-exit, where the child is already
    # on its way out — and the caller's wait_for still bounds it.
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
    """Close a pipe, tolerating one already closed, never opened, or erroring.

    Runs on a detached reader thread whose exception becomes the hook's own
    result (see test_read_hook_output_survives_a_pipe_that_fails_to_close) —
    a close() failure here must never turn an otherwise-fine hook run into an
    error, so this stays a broad backstop rather than a narrowed OSError catch.
    """
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

    Deliberately **not** ``loop.run_in_executor(None, ...)``. A hook whose
    descendants outlive the kill keeps ``communicate()`` blocked in whatever
    thread runs it — an uncancellable block, since neither ``wait_for`` nor
    Ctrl+C can interrupt a thread mid-syscall. On the default executor that
    costs twice:

    1. The pinned thread is one of a pool the whole of zrb shares, so enough
       timed-out hooks starve unrelated ``run_in_executor``/``to_thread`` work.
    2. ``ThreadPoolExecutor`` workers are non-daemon and joined at interpreter
       exit by ``concurrent.futures.thread._python_exit``, so a single pinned
       hook thread hangs shutdown until its descendants happen to exit —
       surfacing as a ``KeyboardInterrupt`` traceback out of ``t.join()`` when
       the user hits Ctrl+C again to escape it.

    A daemon thread is exempt from both: private to this call, and not joined
    by ``threading._shutdown``. An abandoned one dies with the process.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _settle(setter: Callable[[Any], None], value: Any) -> None:
        # The awaiting side may already be gone: wait_for cancels the future on
        # timeout, and setting a result on a cancelled future raises.
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
