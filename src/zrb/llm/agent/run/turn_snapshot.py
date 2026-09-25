"""The self-review gate's snapshot of the working directory at turn start.

The runner takes it before a top-level turn's first model request, and the
Stop payload carries it as `turn_start_snapshot` for the gate to diff against
(`hook/self_review.py`). It holds what `util/git/snapshot_listing.py` lists:
every repository under the working directory, nested ones and linked worktrees
included, and the loose files outside them up to a budget. A delegated
sub-agent takes none: what it changes lands in the parent's working directory
or in a worktree under it, so the parent's diff covers it.

The snapshot lives in a temporary store that `close` deletes when the turn
ends. A working directory that cannot be snapshotted at all — over the
listing's budget, or too large for git to hash within its time limit — is
reported once and not tried again for the rest of the process: every attempt
would fail the same way, the slow one after holding the turn up.
"""

from __future__ import annotations

import logging

from zrb.util.git.snapshot_command import SnapshotError, SnapshotTimeoutError
from zrb.util.git.snapshot_listing import SnapshotBudgetError
from zrb.util.git.snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)

# Working directories found impossible to snapshot, not tried again.
_cannot_snapshot: set[str] = set()


class TurnSnapshot:
    """One turn's starting point: a temporary store, its tree, and the files
    it could not read."""

    def __init__(self) -> None:
        self._store: SnapshotStore | None = None
        self._tree = ""
        self._unreadable: list[str] = []

    def take(self, workdir: str) -> None:
        """Snapshot *workdir*. Any failure leaves the turn without a snapshot
        — it is reviewed from the file tools' paths alone — and deletes the
        store, which may already hold copies of untracked files."""
        if workdir in _cannot_snapshot:
            return
        try:
            store = SnapshotStore.create_temporary(workdir)
        except OSError as e:
            logger.debug(f"Turn snapshot store for {workdir} failed: {e}")
            return
        try:
            snapshot = store.snapshot()
        except (SnapshotBudgetError, SnapshotTimeoutError) as e:
            _give_up_on(workdir, e)
            store.delete()
            return
        except (SnapshotError, OSError) as e:
            logger.debug(f"Turn snapshot of {workdir} failed: {e}")
            store.delete()
            return
        self._store = store
        self._tree = snapshot.tree
        self._unreadable = list(snapshot.unreadable)

    def payload(self) -> dict[str, str | list[str]] | None:
        """The snapshot as `{workdir, tree, store, unreadable}` for the Stop
        hook, or None when there is none."""
        if self._store is None:
            return None
        return {
            "workdir": self._store.work_tree,
            "tree": self._tree,
            "store": self._store.git_dir,
            "unreadable": self._unreadable,
        }

    def close(self) -> None:
        """Delete the snapshot's store."""
        if self._store is not None:
            self._store.delete()
            self._store = None


def _give_up_on(workdir: str, error: SnapshotError) -> None:
    _cannot_snapshot.add(workdir)
    logger.warning(
        f"Self-review reviews file-tool paths only in {workdir}: it cannot be "
        f"snapshotted ({error})."
    )
