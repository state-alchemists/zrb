"""Running the git commands behind working-directory snapshots.

Every command is bounded: by `GIT_COMMAND_TIMEOUT_SECONDS`, and by an optional
*deadline* (a `time.monotonic()` value) that cuts off a whole sequence of
commands. Every command runs without the inherited variables that would point
git at another repository, index or object database. A command run inside
`run_in_worker` stops before it starts once its caller is cancelled. Failures
raise `SnapshotError`. A command killed at its timeout may leave an index lock
behind; `SnapshotStore` runs each operation on an index file of its own, and
deletes it with its lock.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
from typing import Any, Callable, TypeVar

#: The most one git command may take, deadline or not.
GIT_COMMAND_TIMEOUT_SECONDS = 30

# Inherited variables that would point git at another repository, index or
# object database than the one each command names.
_REDIRECTING_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)

# Set in the worker thread running a snapshot operation when the coroutine
# awaiting it is cancelled; `run_git_command` stops at the next command.
_worker = threading.local()

_T = TypeVar("_T")


class SnapshotError(RuntimeError):
    """A snapshot git command failed, timed out, or was cancelled."""


def get_command_timeout(deadline: float | None) -> float:
    """Seconds the next git command may take: `GIT_COMMAND_TIMEOUT_SECONDS`,
    or less when *deadline* is nearer. Zero or below means no time is left."""
    if deadline is None:
        return GIT_COMMAND_TIMEOUT_SECONDS
    return min(GIT_COMMAND_TIMEOUT_SECONDS, deadline - time.monotonic())


def get_clean_env() -> dict[str, str]:
    """The process environment without the variables that redirect git."""
    return {k: v for k, v in os.environ.items() if k not in _REDIRECTING_ENV}


async def run_in_worker(fn: Callable[..., _T], *args: Any) -> _T:
    """Run *fn* in a worker thread; when the caller is cancelled, stop it
    before its next git command and wait for it before the cancellation
    propagates.

    Cancelling cannot stop a thread. A caller holding a lock around a snapshot
    would otherwise release it while git still runs, letting the next
    operation race the same index; a caller deleting a store on cancellation
    would delete it while git still writes to it."""
    abort = threading.Event()

    def work() -> _T:
        _worker.abort = abort
        try:
            return fn(*args)
        finally:
            _worker.abort = None

    future = asyncio.ensure_future(asyncio.to_thread(work))
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        abort.set()
        await asyncio.wait([future])
        raise


def get_git_output(
    args: list[str],
    cwd: str | None,
    deadline: float | None = None,
    stdin: str | None = None,
) -> str:
    """The stdout of `git <args>` run in *cwd*. Raises SnapshotError when it
    fails."""
    result = run_git_command(["git", *args], cwd, deadline, stdin=stdin)
    if result.returncode != 0:
        raise SnapshotError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def run_git_command(
    argv: list[str],
    cwd: str | None,
    deadline: float | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    errors: str = "surrogateescape",
    label: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run *argv* within the deadline, whatever its exit code. Output is UTF-8
    whatever the locale: `surrogateescape` keeps a non-UTF-8 file name's bytes
    intact, and re-encodes them the same way on stdin. *env* defaults to
    `get_clean_env()`."""
    return _run(
        argv,
        cwd,
        deadline,
        env,
        label,
        input=stdin,
        encoding="utf-8",
        errors=errors,
    )


def run_git_binary(
    argv: list[str],
    cwd: str | None,
    deadline: float | None = None,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    label: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """`run_git_command` for file content: bytes in and out, so no newline or
    encoding translation touches them."""
    return _run(argv, cwd, deadline, env, label, input=stdin)


def _run(
    argv: list[str],
    cwd: str | None,
    deadline: float | None,
    env: dict[str, str] | None,
    label: str | None,
    **io: Any,
) -> Any:
    label = label or " ".join(argv[:2])
    abort = getattr(_worker, "abort", None)
    if abort is not None and abort.is_set():
        raise SnapshotError(f"Snapshot cancelled before running {label}")
    timeout = get_command_timeout(deadline)
    if timeout <= 0:
        raise SnapshotError(f"No time left to run {label}")
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            env=get_clean_env() if env is None else env,
            capture_output=True,
            timeout=timeout,
            **io,
        )
    except subprocess.TimeoutExpired as e:
        raise SnapshotError(f"{label} timed out after {timeout:.3g}s") from e
    except OSError as e:
        raise SnapshotError(f"Could not run git: {e}") from e
