"""Ambient state for the repeated-attempt policy.

A leaf module on purpose: the policy itself imports ``handler`` (and through it
the UI and task layers), so keeping the `ContextVar`s here is what lets
``zrb.contextvars`` index them without dragging that graph in — the same reason
``permission/state.py`` and ``sandbox/state.py`` sit apart from their users.
"""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar

# Command signature -> how many times it has been issued in this context.
repetition_counts: ContextVar[dict[str, int]] = ContextVar(
    "repetition_counts", default={}
)

# Signatures already nudged, so one loop yields one escalation rather than a
# nag on every subsequent call.
repetition_warned: ContextVar[frozenset[str]] = ContextVar(
    "repetition_warned", default=frozenset()
)


def bump_repetition(signature: str) -> int:
    """Record another attempt at *signature* and return the new count."""
    counts = Counter(repetition_counts.get())
    counts[signature] += 1
    repetition_counts.set(dict(counts))
    return counts[signature]


def was_repetition_warned(signature: str) -> bool:
    return signature in repetition_warned.get()


def mark_repetition_warned(signature: str) -> None:
    repetition_warned.set(repetition_warned.get() | {signature})


def reset_repetition_state() -> None:
    """Drop all counts. For tests and for starting a fresh session."""
    repetition_counts.set({})
    repetition_warned.set(frozenset())
