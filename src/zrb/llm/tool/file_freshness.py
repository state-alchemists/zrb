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

**Freshness is a claim about the file, so it is checked against the file.** What
is recorded per path is the *fingerprint the model last saw in full*
(``st_mtime_ns`` + ``st_size``), and ``is_file_fresh`` re-stats the file and
compares. A remembered boolean would only ever describe what *these three tools*
did, and the refusal text asserts something stronger — that the file has not
changed since the last full read. Everything else that writes files goes
unrecorded otherwise: ``sed -i``, a formatter, ``git checkout``, a build step,
or a sub-agent. Each of those used to leave the bit reading ``fresh`` and the
overwrite proceeded, which is the failure mode below with a different author.
(Coarse-granularity filesystems can still hide a same-size change inside one
mtime tick; ``Edit`` therefore marks stale explicitly rather than relying on the
stat alone.)

**Not ``ContextVar``s.** ``read_file`` is synchronous, so ``create_safe_wrapper``
dispatches it through ``asyncio.to_thread``, which runs it in a *copied* context
— every ``ContextVar.set`` inside is discarded on the way out. As
``ContextVar``s these tables therefore never recorded a single ``Read``:
``mark_file_fresh`` was called, the write was thrown away, and
``refuse_stale_write`` refused *every* whole-file ``Write`` to an existing file
with "you have not read it", no matter how many times it had just been read —
with no action available that could clear it. A plain module-level dict is
visible from the worker thread and from a sub-agent's context alike, which is
what this state needs to be: it describes the shared filesystem, not one task.

**The check lives in the tools, not in a tool policy.** It was a policy first,
and across 125 benchmark cells it refused nothing: ``check_tool_policies`` is
only reached when ``effective_tool_confirmation`` resolves to a
``ToolCallHandler``, which a ``--interactive false`` run does not bind. A guard
that silently evaporates in headless mode is worse than none, because the tests
still pass. Inside ``write_file`` it runs on every host and in every mode.
"""

from __future__ import annotations

import os

# Absolute path -> the fingerprint of the content the model last saw in full,
# or None for "tracked, but its view is known to be out of date".
_file_views: dict[str, "tuple[int, int] | None"] = {}

# Absolute path -> consecutive edits with no intervening read of it and no
# shell command at all. See ``note_edit_streak``.
_edit_streaks: dict[str, int] = {}

# Absolute path -> (start, end, total, truncated) of the most recent read of it,
# complete or not. Used only to explain a refusal. A model that read lines 1-21
# of 48 and was told "Read it, then write" has already done what it was asked as
# it understands the instruction, so it re-issues the write; naming the span it
# actually read is what turns the retry into a correction.
_last_reads: dict[str, tuple[int, int, int, bool]] = {}

# Absolute path -> how many times a whole-file write to it has been refused
# without an intervening success. Re-issuing a refused write unchanged cannot
# ever succeed, and a small model does it anyway — one benchmarked cell sent the
# identical write four more times after the first refusal. Cleared as soon as a
# write is allowed through.
_write_refusals: dict[str, int] = {}


def mark_file_fresh(path: str) -> None:
    """Record that the model now holds a current full view of *path*.

    Stores the file's fingerprint as of now, so anything that changes it later
    — including a writer this module never sees — makes the view stale by
    comparison rather than by anyone remembering to say so.
    """
    _file_views[_normalize(path)] = _fingerprint(path)


def mark_file_stale(path: str) -> None:
    """Record that *path* changed underneath the model's last full view."""
    _file_views[_normalize(path)] = None


def is_file_fresh(path: str) -> bool:
    """Whether the model's full-content view of *path* is still current."""
    key = _normalize(path)
    if key not in _file_views:
        return False
    seen = _file_views[key]
    return seen is not None and seen == _fingerprint(path)


def is_file_tracked(path: str) -> bool:
    """Whether *path* has been read or written at all in this session."""
    return _normalize(path) in _file_views


def record_read(path: str, start: int, end: int, total: int, truncated: bool) -> None:
    """Record a ``Read``: the span it covered, and what that span grants.

    Only a complete, untruncated read gives the model a current view of the
    whole file, which is what a later whole-file ``Write`` is checked against. A
    20-line window into a 400-line file does not. The span is kept either way so
    a refusal can say which one this was.

    Any read of the file also breaks a blind-edit streak — the model has now
    looked at what its edits produced.
    """
    _last_reads[_normalize(path)] = (start, end, total, truncated)
    if start <= 1 and end >= total and not truncated:
        mark_file_fresh(path)
    clear_edit_streak(path)


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
    streak = _edit_streaks.get(key, 0) + 1
    _edit_streaks[key] = streak
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
    _edit_streaks.pop(_normalize(path), None)


def clear_all_edit_streaks() -> None:
    """Reset every streak. A shell command is evidence for the whole workspace."""
    _edit_streaks.clear()


def refuse_stale_write(path: str) -> str | None:
    """Refuse a whole-file overwrite the model cannot have seen the target of.

    Returns the refusal text, or ``None`` when the write should proceed. Only
    an **existing** file is gated — creating one has nothing to be stale about,
    and ``Edit`` is never gated because ``old_text`` already fails loudly when
    the model's memory has drifted.
    """
    abs_path = _normalize(path)
    if not os.path.isfile(abs_path) or is_file_fresh(path):
        _write_refusals.pop(abs_path, None)
        return None
    attempts = _write_refusals.get(abs_path, 0) + 1
    _write_refusals[abs_path] = attempts
    return (
        f"Refused: {_diagnose_stale_write(path, abs_path)} "
        f"[SYSTEM SUGGESTION]: {_stale_write_remedy(path, attempts)}"
    )


def _diagnose_stale_write(path: str, abs_path: str) -> str:
    """Say which of the three reasons this is, in the file's own terms.

    The partial-read case is the one that mattered in practice. A model that had
    read lines 1-21 of 48 was told only "`Read` it, confirm it says what you
    think it says, then write" — which it had done, as far as it could tell, so
    it re-issued the same write and got the same sentence back four more times.
    Reporting the span it actually read is the difference between a correction
    and another guess.
    """
    seen = _last_reads.get(abs_path)
    if seen is not None:
        start, end, total, truncated = seen
        if truncated:
            return (
                f"your last read of {path} was truncated, so it does not cover "
                "the whole file, and a whole-file write replaces all of it."
            )
        if start > 1 or end < total:
            return (
                f"your last read of {path} covered lines {start}-{end} of "
                f"{total}. A whole-file write replaces all {total}, so a "
                "partial read cannot stand behind one."
            )
    if is_file_tracked(path):
        return (
            f"{path} has changed since you last read it in full, so "
            "overwriting it now would discard whatever that change did."
        )
    return f"{path} already exists and you have not read it."


def _stale_write_remedy(path: str, attempts: int) -> str:
    """Name the two ways out, and stop pretending a retry is one of them.

    Both rungs name `Read` with no range explicitly. "`Read` it" is ambiguous
    once ranged reads exist, and the ambiguity is exactly what the loop fed on.
    """
    if attempts > 1:
        return (
            f"This is refusal {attempts} for the same write. Re-issuing it "
            "unchanged will keep returning this — the refusal is about what you "
            "have read, not about the content you are sending. Do one of "
            f"exactly two things: call `Read` on {path} with no start_line or "
            "end_line, which reads it whole, and then write; or change the "
            "region with `Edit`, which needs no full read at all."
        )
    return (
        f"Call `Read` on {path} with no start_line or end_line — the default "
        "reads the whole file — then write. If you meant to change only part of "
        "it, use `Edit` instead: it needs no full read. If you are recovering "
        "from a failed edit, the current content is the thing you are recovering "
        "from, so read it rather than reconstructing it from memory."
    )


def reset_file_freshness() -> None:
    """Drop all tracking. For tests and for starting a fresh session."""
    _file_views.clear()
    _edit_streaks.clear()
    _last_reads.clear()
    _write_refusals.clear()


def _fingerprint(path: str) -> "tuple[int, int] | None":
    """Cheap identity of a file's current content: modification time and size.

    ``None`` when the file cannot be stat'd, which never compares equal to a
    recorded fingerprint — a path that has gone missing is not one the model
    holds a current view of.
    """
    try:
        stat = os.stat(_normalize(path))
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _normalize(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))
