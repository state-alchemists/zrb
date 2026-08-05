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

**The check lives in the tools, not in a tool policy.** It was a policy first,
and across 125 benchmark cells it refused nothing: ``check_tool_policies`` is
only reached when ``effective_tool_confirmation`` resolves to a
``ToolCallHandler``, which a ``--interactive false`` run does not bind. A guard
that silently evaporates in headless mode is worse than none, because the tests
still pass. Inside ``write_file`` it runs on every host and in every mode.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

# Maps absolute path -> is the model's full-content view of it current.
# Rebound rather than mutated so a copied context cannot leak writes back.
file_freshness: ContextVar[dict[str, bool]] = ContextVar("file_freshness", default={})

# Absolute path -> consecutive edits with no intervening read of it and no
# shell command at all. See ``note_edit_streak``.
edit_streaks: ContextVar[dict[str, int]] = ContextVar("edit_streaks", default={})


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


def note_edit_streak(path: str, threshold: int) -> str:
    """Name a file being edited over and over with nothing else happening.

    The gap this closes: one benchmarked cell spent 68 calls making 59 ``Edit``
    calls against a single file, ran no command, and produced no diagnostic —
    so neither the repeated-command counter (shell-only) nor the post-write
    escalation (diagnostic-gated) could see it. It ran out the 600s budget.

    Counts *consecutive* edits to one path, reset by any read of that path or
    any shell command. Consecutiveness is what separates this from legitimate
    breadth: a 44-site migration makes hundreds of edits, but spread across
    dozens of paths, never many in a row on one. Fires once per streak.
    """
    if threshold <= 0:
        return ""
    key = _normalize(path)
    state = edit_streaks.get()
    streak = state.get(key, 0) + 1
    edit_streaks.set({**state, key: streak})
    if streak != threshold:
        return ""
    return (
        f"\n\n[SYSTEM SUGGESTION]: That is {streak} edits in a row to this one "
        "file, with nothing read and nothing run in between. Nothing has "
        "checked whether any of them helped. Stop editing and find out: run the "
        "code or its tests, or `Read` the file back and compare it against what "
        "you intended. If you are shaping one region by trial and error, a "
        "single whole-file `Write` of the version you actually want is one step "
        "instead of ten."
    )


def clear_edit_streak(path: str) -> None:
    """Reset a path's edit streak — something other than another blind edit happened."""
    key = _normalize(path)
    state = edit_streaks.get()
    if key in state:
        edit_streaks.set({k: v for k, v in state.items() if k != key})


def clear_all_edit_streaks() -> None:
    """Reset every streak. A shell command is evidence for the whole workspace."""
    if edit_streaks.get():
        edit_streaks.set({})


def refuse_stale_write(path: str) -> str | None:
    """Refuse a whole-file overwrite the model cannot have seen the target of.

    Returns the refusal text, or ``None`` when the write should proceed. Only
    an **existing** file is gated — creating one has nothing to be stale about,
    and ``Edit`` is never gated because ``old_text`` already fails loudly when
    the model's memory has drifted.
    """
    abs_path = _normalize(path)
    if not os.path.isfile(abs_path):
        return None
    if is_file_fresh(path):
        return None
    if is_file_tracked(path):
        return (
            f"Refused: {path} has changed since you last read it in full, so "
            "overwriting it now would discard whatever that change did. "
            "[SYSTEM SUGGESTION]: `Read` it, confirm it says what you think it "
            "says, then write. If you are recovering from a failed edit, the "
            "current content is the thing you are recovering from — read it "
            "first, do not reconstruct it from memory."
        )
    return (
        f"Refused: {path} already exists and you have not read it. "
        "[SYSTEM SUGGESTION]: `Read` it first — a whole-file write replaces "
        "everything that is there, and nothing in this call says what that is. "
        "If you meant to change part of it, use `Edit` instead."
    )


def reset_file_freshness() -> None:
    """Drop all tracking. For tests and for starting a fresh session."""
    file_freshness.set({})
    edit_streaks.set({})


def _set_freshness(path: str, fresh: bool) -> None:
    current = file_freshness.get()
    file_freshness.set({**current, _normalize(path): fresh})


def _normalize(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))
