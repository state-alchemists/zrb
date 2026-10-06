"""Run-scoped tracking of which files' current content has been observed.

Lets Write/Edit/RM refuse to overwrite or remove what the current agent run
has not seen. Keyed by `get_current_agent_run_scope()` (per session, fresh per
delegation) in plain dicts, since a `ContextVar` value would not propagate
back from a sub-agent's task. In-memory, LRU-capped at `MAX_OBSERVED_SCOPES`;
eviction fails safe (the next overwrite asks for a fresh Read).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict, defaultdict
from typing import Callable, TypeVar

from zrb.llm.agent_state import get_current_agent_run_scope

_BucketT = TypeVar("_BucketT")

MAX_OBSERVED_SCOPES = 256

# run_scope -> {abs_path: content_hash}, least-recently-used scope first.
_observed: OrderedDict[str, dict[str, str]] = OrderedDict()

# run_scope -> {abs paths shown in an LS/Glob result}, for `check_listed`.
_listed_paths: OrderedDict[str, set[str]] = OrderedDict()

# run_scope -> {dir abs path: hash of a shallow os.listdir}, for RM(recursive=True).
_listed_dirs: OrderedDict[str, dict[str, str]] = OrderedDict()

# Held for a whole Write/Edit call to close the check-then-write race. Never
# evicted: that would void the exclusion.
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
    """Get-or-create *scope*'s bucket, mark it MRU, and evict past the cap."""
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
    """Look up *scope*'s bucket without creating one, marking it MRU if present."""
    bucket = store.get(scope)
    if bucket is not None:
        store.move_to_end(scope)
    return bucket


def record_observed(abs_path: str, content: str) -> None:
    """Record `content` as this run's knowledge of `abs_path`'s full current content."""
    scope = get_current_agent_run_scope()
    _bucket(_observed, scope, dict)[abs_path] = _hash(content)


def record_listed(root_abs_path: str, shown_paths: list[str]) -> None:
    """Record an LS/Glob of `root_abs_path` that showed `shown_paths` (post-truncation).

    Directories between the root and each shown file are recorded too, since
    LS/Glob return only files.
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
    """A blocking error if `abs_path` exists but is not valid UTF-8, else `None`."""
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
    """A blocking error unless this run observed `abs_path`'s current content.

    For overwriting an existing file; binary files are refused first.
    """
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
    """A blocking error unless `abs_path` is confirmed for RM, else `None`.

    Non-recursive: a prior Read or LS/Glob appearance suffices. Recursive:
    the directory itself must have been listed, and unchanged since.
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
    """Record that `abs_path` (e.g. a Move's destination) was seen, for `check_listed`."""
    scope = get_current_agent_run_scope()
    _bucket(_listed_paths, scope, set).add(abs_path)


def clear_observed() -> None:
    """Clear all recorded state (test-isolation seam)."""
    _observed.clear()
    _listed_paths.clear()
    _listed_dirs.clear()
