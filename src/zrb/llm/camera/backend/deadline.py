"""One deadline for a whole capture, however many attempts it makes."""

from __future__ import annotations

import time


def create_deadline(timeout: float | None) -> float | None:
    """The `time.monotonic()` by which a capture must finish; ``None`` for a
    timeout of ``0`` or ``None``, which means no limit."""
    return time.monotonic() + timeout if timeout else None


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
