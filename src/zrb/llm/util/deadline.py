"""One deadline for a whole capture, however many attempts it makes, and the
capture subprocesses it bounds."""

from __future__ import annotations

import asyncio
import contextlib
import time


def create_deadline(timeout: float | None) -> float | None:
    """The `time.monotonic()` by which a capture must finish; ``None`` for a
    timeout of ``None`` or at most ``0``, which means no limit."""
    return time.monotonic() + timeout if timeout and timeout > 0 else None


def get_earlier(first: float | None, second: float | None) -> float | None:
    """The sooner of two deadlines, where ``None`` is no deadline."""
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def get_remaining(deadline: float | None) -> float | None:
    """Seconds left before *deadline*, never below zero; ``None`` for none."""
    if deadline is None:
        return None
    return max(0.0, deadline - time.monotonic())


async def communicate_within(
    proc: asyncio.subprocess.Process, timeout: float | None
) -> tuple[bytes, bytes]:
    """*proc*'s ``(stdout, stderr)``, raising `asyncio.TimeoutError` after
    *timeout* seconds. On timeout or cancellation the process is killed and
    reaped."""
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=timeout)
    finally:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
