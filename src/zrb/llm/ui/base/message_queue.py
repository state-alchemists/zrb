"""Message queue shared by every chat UI.

The queue holds `QueuedMessage` entries — each user message (or `/exec` job)
waiting for its turn. Entries are mutable: the `run` job reads `entry.text`
lazily at execution time, so *editing a queued message is just a field write on
the entry* and removing one is a `remove(entry)` call. Neither needs to touch
the consumer loop.

`MessageQueue` subclasses `asyncio.Queue` so the existing consumers keep their
`get` / `put_nowait` / `task_done` / `join` semantics (the HTTP chat UI awaits
`join()`), and adds the peek / ordering / removal operations the up-arrow
editing of still-queued messages needs. Because the consumer is the only
`get()` caller and pops entries, anything still in the queue is by definition
not yet running — the added operations can only ever touch not-yet-started
messages.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import UserContent


class QueuedMessage:
    """A user message (or exec job) waiting in the queue.

    `run` is the async job that processes this entry; it must read `text` and
    `attachments` at execution time rather than capturing them, so an edit made
    while the entry is queued is picked up when the turn runs.
    """

    def __init__(
        self,
        *,
        text: str,
        attachments: list["UserContent"],
        kind: str,
        run: Callable[[], Awaitable[None]],
    ):
        self.text = text
        self.attachments = attachments
        self.kind = kind  # "message" | "exec"
        self.run = run
        # Marker ("💬"/"⏳") and timestamp of the echoed line, kept so an edit
        # can rebuild the line in the same style instead of re-deriving state.
        self.echo_marker: str = ""
        self.echo_timestamp: str = ""
        # [start, end) span of the echoed `💬 ...` line in the default UI's
        # output buffer, recorded by `_track_echo_span`. None when the echo did
        # not land verbatim (e.g. confirmation buffering) or on UIs that cannot
        # redraw in place.
        self.echo_span: tuple[int, int] | None = None

    @property
    def is_editable(self) -> bool:
        """Whether this entry is a user message (as opposed to an `/exec` job)."""
        return self.kind == "message"


class MessageQueue(asyncio.Queue):
    """A FIFO of `QueuedMessage` entries with edit/remove access.

    Inherits `get` / `put_nowait` / `task_done` / `join` / `qsize` / `empty`
    from `asyncio.Queue`; the added operations peek and remove entries without
    disturbing that bookkeeping.
    """

    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize)
        # Re-declare the private storage deque so the peek/remove operations
        # below type-check against the entry type (asyncio.Queue's own stubs do
        # not expose `_queue`).
        self._queue: deque[QueuedMessage] = deque()
        # `_finished` is likewise absent from the stubs; declare the attribute
        # `super().__init__` already created so `remove()` can signal `join()`.
        self._finished: asyncio.Event

    def peek_latest(self) -> "QueuedMessage | None":
        """The newest not-yet-started entry, or None."""
        return self._queue[-1] if self._queue else None

    def latest_editable(self) -> "QueuedMessage | None":
        """The newest not-yet-started user message (skips `/exec` jobs)."""
        for entry in reversed(self._queue):
            if entry.is_editable:
                return entry
        return None

    def editable_before(self, entry: QueuedMessage) -> "QueuedMessage | None":
        """The user message queued before `entry` (older), or None.

        Returns None when `entry` is no longer queued (its turn started) — the
        same "already submitted" boundary the editing UI needs.
        """
        items = list(self._queue)
        try:
            index = items.index(entry)
        except ValueError:
            return None
        for older in reversed(items[:index]):
            if older.is_editable:
                return older
        return None

    def editable_after(self, entry: QueuedMessage) -> "QueuedMessage | None":
        """The user message queued after `entry` (newer), or None."""
        items = list(self._queue)
        try:
            index = items.index(entry)
        except ValueError:
            return None
        for newer in items[index + 1 :]:
            if newer.is_editable:
                return newer
        return None

    def contains(self, entry: QueuedMessage) -> bool:
        """Whether `entry` is still queued (not yet consumed by `get()`)."""
        return entry in self._queue

    def remove(self, entry: QueuedMessage) -> None:
        """Remove `entry` from the queue without running it.

        Identity-based: the consumer already popped any running entry, so a
        message whose turn started is not reachable here. The unfinished-task
        counter is decremented alongside the removal — `put_nowait` bumped it
        and the entry will never reach `task_done` — so a `join()` still
        resolves instead of waiting forever for the removed entry.
        """
        self._queue.remove(entry)
        self._unfinished_tasks -= 1
        if self._unfinished_tasks == 0:
            self._finished.set()
