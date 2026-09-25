"""An exclusive lock on a file, shared by threads and processes alike.

The lock is the operating system's — `flock` on POSIX, `msvcrt.locking` on
Windows — not a lockfile's existence, so the OS releases it when its holder
exits or is killed, and nothing is ever left behind to clean up.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import IO, Iterator

if sys.platform == "win32":  # pragma: no cover - exercised on Windows CI
    import msvcrt

    def _lock(handle: IO[bytes]) -> None:
        handle.seek(0)
        while True:
            try:
                # Retries for about ten seconds, then raises; keep waiting.
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def hold_file_lock(path: str) -> Iterator[None]:
    """Hold an exclusive lock on *path*, created if missing, waiting while
    another thread or process holds it."""
    with open(path, "ab") as handle:
        _lock(handle)
        try:
            yield
        finally:
            _unlock(handle)
