"""An exclusive lock on a file, shared by threads and processes alike.

The lock is the operating system's — `flock` on POSIX, `msvcrt.locking` on
Windows — not a lockfile's existence, so the OS releases it when its holder
exits or is killed, and nothing is ever left behind to clean up.
"""

from __future__ import annotations

import errno
import sys
import time
from contextlib import contextmanager
from typing import IO, Iterator

# How often a waiter tries again while another holds the lock. Each try
# (`_has_taken_lock`) takes the lock if it is free, and says whether it did.
_POLL_SECONDS = 0.05

if sys.platform == "win32":  # pragma: no cover - exercised on Windows CI
    import msvcrt

    def _has_taken_lock(handle: IO[bytes]) -> bool:
        # Locking past the end of a file is allowed, so an empty one will do.
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as e:
            if e.errno == errno.EACCES:  # held by another handle
                return False
            raise
        return True

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _has_taken_lock(handle: IO[bytes]) -> bool:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:  # held by another open file
            return False
        return True

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)


class FileLockTimeout(TimeoutError):
    """Another thread or process held the lock past the wait allowed."""


@contextmanager
def hold_file_lock(path: str, timeout: float | None = None) -> Iterator[None]:
    """Hold an exclusive lock on *path*, created if missing, waiting while
    another thread or process holds it — at most *timeout* seconds, then
    `FileLockTimeout`. An error other than the lock being held is raised
    at once rather than waited out."""
    with open(path, "ab") as handle:
        give_up = None if timeout is None else time.monotonic() + timeout
        while not _has_taken_lock(handle):
            if give_up is not None and time.monotonic() >= give_up:
                raise FileLockTimeout(f"{path} is still locked after {timeout}s")
            time.sleep(_POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(handle)
