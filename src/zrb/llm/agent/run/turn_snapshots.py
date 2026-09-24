"""The directories one turn's snapshots cover, for the self-review gate.

A turn starts by snapshotting its working directory: the whole enclosing git
repository, or the directory itself outside one. Before a tool changes files
anywhere else — `Shell` given another `cwd`, a file tool given a path in
another repository, a worktree `EnterWorktree` created (its own repository
root, gitignored by the main one) — the tool gate snapshots that repository
first, so the Stop-time diff covers it too. A directory outside every git
repository and outside the working directory is not snapshotted: nothing would
bound what it hashes.

Each covered root gets its own temporary `SnapshotStore`; `close` deletes them
all when the turn ends. Delegated sub-agents inherit the registry, so what they
change — in their own worktrees too — is in the parent's review.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any

from zrb.util.git.snapshot_store import SnapshotError, SnapshotStore, get_repo_root

logger = logging.getLogger(__name__)

# Argument keys naming a path a tool may change (the sandbox gate's write keys,
# minus ExitWorktree's `worktree_path`, which it deletes rather than edits).
_PATH_KEYS = ("path", "file_path", "file", "filename", "src", "dst")
_CHANGING_CAPABILITIES = ("edit", "execute", "unknown")


@dataclass(frozen=True)
class _Covered:
    work_tree: str
    store: SnapshotStore
    tree: str


class TurnSnapshots:
    """The roots one turn has snapshotted, and their turn-start trees."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._covered: list[_Covered] = []
        self._roots: dict[str, str | None] = {}
        self._closed = False

    def cover_workdir(self, workdir: str) -> None:
        """Snapshot the turn's working directory — its whole repository, or
        the directory itself outside git."""
        self._add(os.path.realpath(self._root_of(workdir) or workdir))

    def cover_tool_call(self, capability: Any, args: dict[str, Any]) -> None:
        """Before a tool that may change files runs, snapshot each repository
        its arguments point into that this turn has not covered yet."""
        if str(getattr(capability, "value", capability)) not in _CHANGING_CAPABILITIES:
            return
        paths = [args.get(key) for key in (*_PATH_KEYS, "cwd")]
        for path in paths:
            if isinstance(path, str) and path:
                self._cover_path(path)

    def payload(self) -> list[dict[str, str]]:
        """Each covered root as `{workdir, tree, store}`, for the Stop hook."""
        with self._lock:
            return [
                {"workdir": c.work_tree, "tree": c.tree, "store": c.store.git_dir}
                for c in self._covered
            ]

    def close(self) -> None:
        """Delete every store. A snapshot still running in a worker thread
        deletes its own store when it finishes."""
        with self._lock:
            self._closed = True
            covered, self._covered = self._covered, []
        for c in covered:
            c.store.delete()

    def _cover_path(self, path: str) -> None:
        directory = _existing_directory(path)
        if directory is None:
            return
        root = self._root_of(directory)
        if root is None:
            return  # outside git: only the working directory is snapshotted
        root = os.path.realpath(root)
        with self._lock:
            if any(c.work_tree == root for c in self._covered):
                return
        self._add(root)

    def _add(self, work_tree: str) -> None:
        """Snapshot *work_tree* into a new store and register it. Any failure
        — a git error, or an `OSError` setting the store up — only leaves the
        root uncovered: the turn runs on unreviewed there, and the store,
        which may already hold copies of untracked files, is deleted."""
        try:
            store = SnapshotStore.create_temporary(work_tree)
        except OSError as e:
            logger.debug(f"Turn snapshot store for {work_tree} failed: {e}")
            return
        try:
            tree, _ = store.snapshot()
        except (SnapshotError, OSError) as e:
            logger.debug(f"Turn snapshot of {work_tree} failed: {e}")
            store.delete()
            return
        with self._lock:
            duplicate = any(c.work_tree == work_tree for c in self._covered)
            if not self._closed and not duplicate:
                self._covered.append(_Covered(work_tree, store, tree))
                return
        store.delete()

    def _root_of(self, directory: str) -> str | None:
        if directory not in self._roots:
            self._roots[directory] = get_repo_root(directory)
        return self._roots[directory]


def _existing_directory(path: str) -> str | None:
    """The nearest existing directory at or above *path* (which a tool may be
    about to create), resolved the way the file tools resolve it."""
    current = os.path.abspath(os.path.expanduser(path))
    while not os.path.isdir(current):
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return current
