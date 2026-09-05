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
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


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
        # The echoed line `echo_span` points at, so a redraw can verify the span
        # is still where the line landed before splicing. A terminal resize
        # re-wraps tracked markdown blocks and shifts the transcript without
        # updating this entry — the mismatch then drops the span (edit stays
        # effective, echo not rewritten) instead of corrupting the output.
        self.echo_text: str = ""

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


def submit_user_message_via_queue(
    *,
    append_to_output: Callable[[str], Any],
    active_run_context: Any,
    stream_ai_response: Callable[[Any, str, list], Any],
    queue: MessageQueue,
    attachment_sources: list[Any],
    echo_targets: list[Any],
    llm_task: Any,
    user_message: str,
    marker: str,
) -> None:
    """Shared mechanics behind `BaseUI.submit_user_message` and
    `MultiUI.submit_user_message` — echo, collect attachments, steer into a
    live run or queue a `QueuedMessage`, mirror the echo span to whichever
    targets can redraw it.

    A standalone UI passes itself as both `attachment_sources` and
    `echo_targets` (`[self]`); a `MultiUI` passes its children (it holds no
    attachments or echo buffer of its own) — `append_to_output` and
    `stream_ai_response` stay owner-called either way, since both classes
    already implement them polymorphically (`MultiUI`'s broadcasts to every
    child; a standalone UI's acts on itself alone).
    """
    timestamp = datetime.now().strftime("%H:%M")
    echo = f"\n{marker} {timestamp} >> {user_message.strip()}\n"
    append_to_output(echo)

    attachments: list[Any] = []
    for source in attachment_sources:
        take: Callable[[], list[Any]] | None = getattr(
            source, "take_pending_attachments", None
        )
        if callable(take):
            attachments.extend(take())

    if steer_into_live_run(active_run_context, user_message, attachments):
        return

    entry = QueuedMessage(
        text=user_message,
        attachments=attachments,
        kind="message",
        run=lambda: stream_ai_response(llm_task, entry.text, entry.attachments),
    )
    entry.echo_marker = marker
    entry.echo_timestamp = timestamp
    for target in echo_targets:
        track = getattr(target, "_track_echo_span", None)
        if callable(track):
            track(entry, echo)
    queue.put_nowait(entry)


def steer_into_live_run(
    run_context: Any, text: str, attachments: "Sequence[UserContent]"
) -> bool:
    """Try to inject `text`/`attachments` into the turn `run_context` belongs to.

    Returns True when delivered — the caller skips queuing entirely, since
    pydantic-ai's own drain (`RunContext.enqueue`, priority="asap") delivers it
    at the next model request, batching with any other message enqueued the
    same way in the meantime. Returns False when there is no live
    run (`run_context` is None — no turn in flight, or one is suspended on a
    pending tool approval) or the enqueue attempt itself failed (the run
    finished between the caller's check and this call); either way the
    caller's normal queue path is the correct fallback.
    """
    if run_context is None:
        return False
    try:
        run_context.enqueue(text, *attachments, priority="asap")
        return True
    except Exception:
        CFG.LOGGER.debug(
            "steer_into_live_run: enqueue failed, falling back to queue",
            exc_info=True,
        )
        return False
