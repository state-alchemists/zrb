"""Run-scoped tracking of which files' current content has been observed.

`write_file(mode="w")` blindly truncates an existing file regardless of
whether the current agent run has ever seen its current content. This module
lets it refuse instead: `record_observed` is called after any Read, Write, or
Edit that produces the file's full current content; `check_observed` compares
that record against what's on disk right before a `mode="w"` overwrite.
A target whose bytes aren't valid UTF-8 is refused outright (`check_observed`,
and `check_writable_text` for appends): Write/Edit emit UTF-8 text only, so
writing them would corrupt rather than modify — no observed state can lift
that refusal.

Keyed by `get_current_agent_run_scope()` — the session name for a top-level
conversation (stable across its turns), but a fresh per-delegation id for a
sub-agent (see that ContextVar's docstring in `agent/run/runner.py`). Not
keyed by session alone: a delegated sub-agent starts with an empty
`message_history` and hasn't seen what its parent or a sibling sub-agent
observed, so sharing one bucket per session would let it blindly overwrite a
file it never itself read. Not a raw `ContextVar` holding this dict either —
a `ContextVar` only propagates within one asyncio task's context tree, so a
value a sub-agent's task `.set()`s would never reach its parent or siblings;
keying a plain dict by the (already correctly `ContextVar`-scoped) run id
sidesteps that, mirroring `plan.py::TodoManager`'s own keyed-dict pattern for
the same class of state.

In-memory only, no disk persistence: a process restart forcing one fresh Read
before the next overwrite is the safe default, not a gap worth engineering
around. The map is an LRU capped at `MAX_OBSERVED_SCOPES` scopes: every
delegation mints a fresh scope that outlives its run, so an uncapped map would
grow one dead bucket per delegation for the process lifetime. Eviction fails
safe — the next overwrite under an evicted scope is refused with a pointer
back to `Read`, costing one extra round trip, never allowing an ungrounded
overwrite.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict, defaultdict
from typing import Callable, TypeVar

from zrb.llm.agent_state import get_current_agent_run_scope

_BucketT = TypeVar("_BucketT")

# Scopes kept in the observed-content LRU before the least-recently-used one
# is evicted (see the module docstring for why eviction is safe here).
MAX_OBSERVED_SCOPES = 256

# run_scope -> {abs_path: content_hash}, least-recently-used scope first.
_observed: OrderedDict[str, dict[str, str]] = OrderedDict()

# run_scope -> {abs file paths shown in an LS/Glob result}, for RM's lighter
# "has this path been named" bar (see `check_listed`) — a weaker guarantee
# than `_observed`'s content hash, and deliberately so: RM's risk is picking
# the wrong path, not destroying unseen content.
_listed_paths: OrderedDict[str, set[str]] = OrderedDict()

# run_scope -> {dir abs path: hash of a shallow os.listdir snapshot taken at
# record time}, for RM(recursive=True)'s directory-level bar. Independent of
# whatever LS/Glob actually displayed (which may be recursive, filtered, or
# truncated) — this is a cheap, separate snapshot purely for detecting drift
# between listing and removal, not a replay of LS's own walk.
_listed_dirs: OrderedDict[str, dict[str, str]] = OrderedDict()

# One lock per path, held for a whole Write/Edit call. Closes the
# check-then-write TOCTOU window between two concurrent writers to the same
# path (e.g. two sub-agents sharing a non-isolated worktree) — without it,
# both could pass the observed-content check before either has written, and
# the second would silently clobber the first.
# Never evicted — unlike `_observed`, eviction here would be unsafe (a lock
# dropped between two concurrent acquirers voids the mutual exclusion it
# exists for) and unnecessary (the map is bounded by the number of distinct
# paths ever written in the process's lifetime, not by delegation count).
_path_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def path_write_lock(abs_path: str) -> asyncio.Lock:
    """The per-path lock serializing Write and Edit on *abs_path*."""
    return _path_locks[abs_path]


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="surrogateescape")).hexdigest()


def _bucket(
    store: "OrderedDict[str, _BucketT]",
    scope: str,
    default_factory: Callable[[], _BucketT],
) -> _BucketT:
    """Get-or-create *scope*'s bucket in *store*, marked most-recently-used.

    Shared by every ledger in this module (`_observed`, `_listed_paths`,
    `_listed_dirs`) — one eviction rule instead of three copies of it.
    Creating a bucket counts as a use; so does every lookup under an existing
    scope — an active conversation must not be evicted out from under itself
    by chatty delegations sharing the process. Any eviction drops the
    least-recently-used scope (never the caller's: it was just moved to the
    MRU end).
    """
    bucket = store.get(scope)
    if bucket is None:
        bucket = default_factory()
        store[scope] = bucket
    else:
        store.move_to_end(scope)
    while len(store) > MAX_OBSERVED_SCOPES:
        store.popitem(last=False)
    return bucket


def _peek(store: "OrderedDict[str, _BucketT]", scope: str) -> "_BucketT | None":
    """Read-only lookup of *scope*'s bucket in *store*, marked MRU if
    present. Never creates a bucket — a check must not fabricate history."""
    bucket = store.get(scope)
    if bucket is not None:
        store.move_to_end(scope)
    return bucket


def record_observed(abs_path: str, content: str) -> None:
    """Record `content` as this agent run's current knowledge of `abs_path`.

    Call after any operation that ends up knowing the file's full current
    content: a successful Read, or a successful Write/Edit (using the
    content as it now stands on disk, not just the part that changed) —
    so an immediate follow-up Write/Edit on the same path never needs a
    fresh Read in between.
    """
    scope = get_current_agent_run_scope()
    _bucket(_observed, scope, dict)[abs_path] = _hash(content)


def record_listed(root_abs_path: str, shown_paths: list[str]) -> None:
    """Record that `root_abs_path` was the root of an LS/Glob call this
    session, and that `shown_paths` (absolute paths actually returned —
    post-truncation, so a truncated listing never over-claims) were seen to
    exist. See `check_listed` for how this backs RM.

    `root_abs_path`, and every directory between it and each shown path, are
    recorded too, not just the files themselves: LS/Glob only ever return
    *files* (`walk_files` never yields directory paths, even for a listing
    up to 3 levels deep), so a subdirectory — empty, or non-empty and only
    known via the files shown inside it — would otherwise never satisfy
    `check_listed`, even though a file's path in the listing directly implies
    every directory on the way to it was seen too.
    """
    scope = get_current_agent_run_scope()
    bucket = _bucket(_listed_paths, scope, set)
    bucket.add(root_abs_path)
    for path in shown_paths:
        bucket.add(path)
        parent = os.path.dirname(path)
        while parent.startswith(root_abs_path) and parent not in bucket:
            bucket.add(parent)
            parent = os.path.dirname(parent)
    try:
        snapshot = _hash("\n".join(sorted(os.listdir(root_abs_path))))
    except OSError:
        return
    _bucket(_listed_dirs, scope, dict)[root_abs_path] = snapshot


def _binary_refusal(abs_path: str) -> str:
    return (
        f"Error: {abs_path} is a binary file.\n"
        "[SYSTEM SUGGESTION]: Write outputs UTF-8 text only and cannot "
        "modify binary content — writing would corrupt it. Use a shell "
        "command or a tool suited to the file's format instead."
    )


def check_writable_text(abs_path: str) -> str | None:
    """Return a blocking error string if `abs_path` exists but its bytes are
    not valid UTF-8; `None` if a text Write/Edit may proceed.

    Shared by the overwrite and append paths: both emit UTF-8 only, so
    non-decodable bytes would be corrupted rather than written. Denied
    outright, regardless of observed state — even a fresh Read is no
    grounding here (a PDF's extracted text is not its bytes).
    """
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            f.read()
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        return _binary_refusal(abs_path)
    except OSError as e:
        return (
            f"Error: Could not read {abs_path}: {e}.\n"
            "[SYSTEM SUGGESTION]: Investigate the read failure before "
            "writing to the file."
        )
    return None


def check_observed(abs_path: str) -> str | None:
    """Return a blocking error string if `abs_path` wasn't observed as its
    current content in this agent run; `None` if the overwrite may proceed.

    Only meaningful for a destructive overwrite of an *existing* file — the
    caller should skip this for a new file or a non-destructive append.
    """
    # Binary refusal first, before the recorded-state check: it is the root
    # cause and holds no matter what this run has or hasn't read.
    binary_block = check_writable_text(abs_path)
    if binary_block is not None:
        return binary_block
    scope = get_current_agent_run_scope()
    bucket = _peek(_observed, scope)
    recorded = bucket.get(abs_path) if bucket is not None else None
    if recorded is None:
        return (
            f"Error: {abs_path} has not been read in this session.\n"
            "[SYSTEM SUGGESTION]: Read it first to see its current content, "
            "then retry the write."
        )
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            current = f.read()
    except Exception as e:
        return (
            f"Error: Could not verify the current content of {abs_path}: {e}.\n"
            "[SYSTEM SUGGESTION]: Investigate the read failure before "
            "overwriting the file."
        )
    if _hash(current) != recorded:
        return (
            f"Error: {abs_path} has changed since it was last read in this "
            "session.\n"
            "[SYSTEM SUGGESTION]: Read it again to see the current content, "
            "then retry the write if you still want to overwrite it."
        )
    return None


def check_listed(abs_path: str, *, recursive: bool) -> str | None:
    """Return a blocking error string if `abs_path` isn't sufficiently
    confirmed for RM; `None` if the removal may proceed.

    `recursive=False` covers a plain file or an already-empty directory
    (`os.rmdir`) — neither destroys unseen content, so the bar is only that
    the path is confirmed to be the one intended: a prior Read (`_observed`)
    or having appeared in an LS/Glob result (`_listed_paths`) both satisfy it.

    `recursive=True` covers a directory about to be recursively removed
    (`shutil.rmtree`) — satisfied only by having LS/Glob'd that exact
    directory, re-verified against a fresh `os.listdir` snapshot so a
    directory that gained or lost top-level entries since being listed is
    still caught (mirrors `check_observed`'s own staleness re-check).
    """
    scope = get_current_agent_run_scope()
    if not recursive:
        observed = _peek(_observed, scope)
        if observed is not None and abs_path in observed:
            return None
        listed = _peek(_listed_paths, scope)
        if listed is not None and abs_path in listed:
            return None
        return (
            f"Error: {abs_path} has not been read or listed in this session.\n"
            "[SYSTEM SUGGESTION]: Read it, or List/Glob its parent directory, "
            "to confirm this is the path you mean, then retry."
        )
    dirs = _peek(_listed_dirs, scope)
    recorded = dirs.get(abs_path) if dirs is not None else None
    if recorded is None:
        return (
            f"Error: {abs_path} has not been listed in this session.\n"
            "[SYSTEM SUGGESTION]: List or Glob this directory first to "
            "confirm what it contains, then retry the recursive removal."
        )
    try:
        current = _hash("\n".join(sorted(os.listdir(abs_path))))
    except OSError as e:
        return (
            f"Error: Could not verify {abs_path}'s current contents: {e}.\n"
            "[SYSTEM SUGGESTION]: Investigate before retrying the removal."
        )
    if current != recorded:
        return (
            f"Error: {abs_path}'s contents have changed since it was listed "
            "in this session.\n"
            "[SYSTEM SUGGESTION]: List it again to see what it now contains, "
            "then retry the removal if you still want to proceed."
        )
    return None


def record_seen(abs_path: str) -> None:
    """Record that `abs_path` was confirmed to exist at this location this
    run — e.g. a Move's destination — satisfying `check_listed`'s
    non-recursive bar without claiming a full LS/Glob of its parent.
    """
    scope = get_current_agent_run_scope()
    _bucket(_listed_paths, scope, set).add(abs_path)


def clear_observed() -> None:
    """Clear all recorded state. A test-isolation seam — production code
    never needs this; the LRU cap bounds the map's growth (see
    `MAX_OBSERVED_SCOPES`), and a restart clears it wholesale anyway.
    """
    _observed.clear()
    _listed_paths.clear()
    _listed_dirs.clear()
