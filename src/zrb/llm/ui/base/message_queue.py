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
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from zrb.config.config import CFG
from zrb.llm.ui.base.user_echo import (
    AppendOutputFunc,
    echo_user_message,
    should_render_user_markdown,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


class QueuedMessage:
    """A user message (or exec job) waiting in the queue.

    `run` is the async job that processes this entry; it must read `text` and
    `attachments` at execution time rather than capturing them, so an edit made
    while the entry is queued is picked up when the turn runs. It is a
    coroutine function rather than any awaitable, because the consumer hands
    it to `asyncio.create_task`, which accepts nothing else.
    """

    def __init__(
        self,
        *,
        text: str,
        attachments: list["UserContent"],
        kind: str,
        run: Callable[[], Coroutine[Any, Any, None]],
    ):
        self.text = text
        self.attachments = attachments
        self.kind = kind  # "message" | "exec"
        self.run = run
        # When submission reached the queue, so a paste whose lines arrived as
        # separate Enter keystrokes can be coalesced back into one message.
        # None for entries that never passed through `submit_user_message_via_queue`
        # (e.g. `/exec` jobs) — they never merge.
        self.submitted_at: datetime | None = None
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
    append_to_output: AppendOutputFunc,
    active_run_context: Any,
    stream_ai_response: Callable[[Any, str, list], Any],
    queue: MessageQueue,
    attachment_sources: list[Any],
    echo_targets: list[Any],
    llm_task: Any,
    user_message: str,
    marker: str,
    append_markdown: Callable[[str], Any] | None = None,
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

    A rendered echo is header + rendered body rather than one verbatim chunk,
    so it claims no echo span: editing the queued message still works but
    cannot rewrite the echoed line in place.

    A paste whose lines arrived as separate Enter keystrokes (a terminal that
    never wrapped them in a bracketed-paste marker) submits one line per
    `put_nowait` within a few milliseconds. When the newest still-queued,
    still-editable message was submitted within `CFG.LLM_UI_PASTE_MERGE_MS`
    of this one, the new line is appended to it instead of becoming its own
    turn — the model receives the pasted block as one message.

    The merge is bounded by a queued `/exec` job: only the newest queue entry
    itself (never an older editable message reached past an `/exec` in
    between) may absorb the new line. A merged line is reflected per target —
    one that can splice its echo redraws it in place; one that cannot (a
    bufferless UI, or a rendered first echo with no tracked span) gets an
    ordinary echo of the line through its own output path, never a broadcast
    that duplicates a child that already redrew. And when the merged text
    turns Markdown, neither path applies: splicing would show literal
    Markdown, so the combined message goes through the rendering echo path
    exactly as a single submission of it would.
    """
    now = datetime.now()
    timestamp = now.strftime("%H:%M")

    def emit_echo() -> str:
        return echo_user_message(
            append_to_output,
            append_markdown,
            header=f"\n{marker} {timestamp} >> ",
            body=user_message.strip(),
        )

    attachments: list[Any] = []
    for source in attachment_sources:
        take: Callable[[], list[Any]] | None = getattr(
            source, "take_pending_attachments", None
        )
        if callable(take):
            attachments.extend(take())

    if steer_into_live_run(active_run_context, user_message, attachments):
        # A live-run submission never reaches the queue, so the shared echo
        # below would not run for it — render it here or the user's line
        # disappears from the UI while the model still receives it.
        emit_echo()
        return

    previous = queue.latest_editable()
    if (
        previous is not None
        and queue.peek_latest() is previous
        and _is_paste_burst(previous, now, CFG.LLM_UI_PASTE_MERGE_MS)
    ):
        combined = f"{previous.text.strip()}\n{user_message.strip()}"
        previous.text = combined
        previous.attachments += attachments
        previous.submitted_at = now
        if append_markdown is not None and should_render_user_markdown(combined):
            echo_user_message(
                append_to_output,
                append_markdown,
                header=f"\n{marker} {timestamp} >> ",
                body=combined,
            )
        else:
            for target in echo_targets:
                redraw = getattr(target, "_redraw_echo", None)
                if callable(redraw) and redraw(previous):
                    continue
                _emit_echo_to(target, f"\n{marker} {timestamp} >> ", user_message)
        return

    echo = emit_echo()

    entry = QueuedMessage(
        text=user_message,
        attachments=attachments,
        kind="message",
        run=lambda: stream_ai_response(llm_task, entry.text, entry.attachments),
    )
    entry.echo_marker = marker
    entry.echo_timestamp = timestamp
    entry.submitted_at = now
    if echo:
        for target in echo_targets:
            track = getattr(target, "_track_echo_span", None)
            if callable(track):
                track(entry, echo)
    queue.put_nowait(entry)


def _emit_echo_to(target: Any, header: str, body: str) -> None:
    """Write an ordinary user echo into one target's own output path.

    Used for a merged paste line on a target whose `_redraw_echo` could not
    splice the line into its existing echo, so the line reaches exactly that UI
    rather than being broadcast to every target — a child that already redrew
    in place must not get a duplicate.
    """
    append = getattr(target, "append_to_output", None)
    if not callable(append):
        return
    markdown = getattr(target, "append_markdown", None)
    echo_user_message(
        append,
        markdown if callable(markdown) else None,
        header=header,
        body=body,
    )


def _is_paste_burst(
    previous: "QueuedMessage | None", now: datetime, window_ms: int
) -> bool:
    """Whether `previous` — the newest still-queued user message — arrived so
    recently that it can only be a paste whose lines the terminal split into
    Enter keystrokes, never a human re-submission (typing another message
    takes orders of magnitude longer).

    The window rolls forward: each merge refreshes `submitted_at`, so a long
    paste's tail stays in the same burst while a pause between two deliberate
    messages exceeds the window naturally. Only an entry that is still queued
    and editable can merge; an `/exec` job and an already-started turn are
    both absent from `latest_editable`. A non-positive `window_ms` disables
    the merge.
    """
    if previous is None or previous.submitted_at is None:
        return False
    if window_ms <= 0:
        return False
    return (now - previous.submitted_at).total_seconds() * 1000 <= window_ms


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
