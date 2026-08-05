"""Tracks whether the model's picture of a file is current.

A whole-file ``Write`` carries no evidence about what it is replacing. ``Edit``
has ``old_text``, which fails loudly when the model's memory has drifted;
``Write`` will happily overwrite a file the model last saw several steps ago.

That gap produced a real regression: a benchmarked trial read ``worker.py``,
edited it, received a ``[DIAGNOSTIC]`` reporting three errors, and answered by
rewriting the whole file from memory — flipping the worker's empty-queue exit
from ``return`` to ``continue`` and shipping an infinite loop. It had read the
file, so a plain read-before-write check would have waved it through. What was
missing was not *a* read but a **current** one.

Three transitions, tracked per absolute path:

* ``Read``  → **fresh**. The model has just seen the whole of what is there.
* ``Write`` → **fresh**. The model authored every byte, so its memory is the file.
* ``Edit``  → **stale**. The file no longer matches any full view the model
  holds; the delta is real but its picture of the surrounding content is not
  guaranteed.

Untracked paths are simply unknown — a ``Write`` that creates a new file has
nothing to be stale about.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

# Maps absolute path -> is the model's full-content view of it current.
# Rebound rather than mutated so a copied context cannot leak writes back.
file_freshness: ContextVar[dict[str, bool]] = ContextVar("file_freshness", default={})


def mark_file_fresh(path: str) -> None:
    """Record that the model now holds a current full view of *path*."""
    _set_freshness(path, True)


def mark_file_stale(path: str) -> None:
    """Record that *path* changed underneath the model's last full view."""
    _set_freshness(path, False)


def is_file_fresh(path: str) -> bool:
    """Whether the model's full-content view of *path* is current."""
    return file_freshness.get().get(_normalize(path), False)


def is_file_tracked(path: str) -> bool:
    """Whether *path* has been read or written at all in this context."""
    return _normalize(path) in file_freshness.get()


def reset_file_freshness() -> None:
    """Drop all tracking. For tests and for starting a fresh session."""
    file_freshness.set({})


def _set_freshness(path: str, fresh: bool) -> None:
    current = file_freshness.get()
    file_freshness.set({**current, _normalize(path): fresh})


def _normalize(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))
