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
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from zrb.config.config import CFG
from zrb.llm.ui.any_ui import AnyUI
from zrb.llm.ui.base.user_echo import (
    AppendOutputFunc,
    echo_user_message,
    should_render_user_markdown,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


@dataclass
class EchoSpan:
    """Where one UI's echo of a message landed in that UI's output buffer.

    `start`/`end` delimit the echoed line and `text` is the line itself, so a
    redraw can verify the span still holds it before splicing in place — it
    may have been shifted or re-wrapped since (e.g. a terminal resize).
    """

    start: int
    end: int
    text: str


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
        # Each target UI's echo span in its own output buffer, keyed by that
        # UI: a `MultiUI` echoes into every child, and each redraws against
        # its own span. An entry with no echo (an `/exec` job, a rendered
        # echo, a confirmation-buffered line) has no key.
        self.echo_spans: dict[Any, EchoSpan] = {}

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
        # asyncio.Queue's stubs expose neither `_queue` nor `_finished`;
        # declare them so the operations below type-check.
        self._queue: deque[QueuedMessage] = deque()
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
    echo_targets: Sequence[AnyUI],
    llm_task: Any,
    user_message: str,
    marker: str,
    append_markdown: Callable[[str], Any] | None = None,
) -> None:
    """Shared mechanics behind `BaseUI.submit_user_message` and
    `MultiUI.submit_user_message`: echo, collect attachments, then steer into a
    live run or queue a `QueuedMessage`.

    A standalone UI passes `[self]` as `attachment_sources` and `echo_targets`;
    a `MultiUI` passes its children. A rendered (Markdown) echo claims no echo
    span, so editing it cannot rewrite the line in place.

    Paste merging: a terminal without bracketed paste submits a paste one line
    per Enter within milliseconds. A line arriving within
    `CFG.LLM_UI_PASTE_MERGE_WINDOW` of the newest queued entry (see
    `_merge_candidate`) is appended to it, so the model gets one message. The
    joined text is preserved exactly; stripping is left to display paths.
    Steering into a live run outranks merging, and is attempted rather than
    assumed: a run that finished meanwhile fails its enqueue, and the line
    falls back to the queue and merges like any other.

    A line is always made visible before an attachment-collection failure
    propagates, so it is never silently swallowed.
    """
    now = datetime.now()
    timestamp = now.strftime("%H:%M")
    header = f"\n{marker} {timestamp} >> "

    def emit_echo() -> str:
        return echo_user_message(
            append_to_output,
            append_markdown,
            header=header,
            body=user_message.strip(),
        )

    previous = _merge_candidate(queue, now)
    if previous is None:
        echo = emit_echo()
        attachments = _collect_attachments(attachment_sources)
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
        entry.submitted_at = now
        if echo:
            for target in echo_targets:
                target.track_echo_span(entry, echo)
        queue.put_nowait(entry)
        return

    # A merged line's only visible trace is the per-target reflection, so
    # echo it here if collecting attachments fails.
    try:
        attachments = _collect_attachments(attachment_sources)
    except Exception:
        emit_echo()
        raise
    if steer_into_live_run(active_run_context, user_message, attachments):
        emit_echo()
        return
    _merge_into(
        previous,
        text=user_message,
        attachments=attachments,
        now=now,
        header=header,
        echo_targets=echo_targets,
        append_markdown=append_markdown,
    )


def _merge_candidate(queue: MessageQueue, now: datetime) -> "QueuedMessage | None":
    """The queued entry a submission made at `now` may fold into, or None.

    Only the newest queue entry qualifies, and only while it is an editable
    user message still inside the paste-burst window — a queued `/exec` job
    bounds the merge rather than being reached past to an older message.
    """
    previous = queue.latest_editable()
    if previous is None or queue.peek_latest() is not previous:
        return None
    if not _is_paste_burst(previous, now, CFG.LLM_UI_PASTE_MERGE_WINDOW):
        return None
    return previous


def _merge_into(
    entry: QueuedMessage,
    *,
    text: str,
    attachments: list[Any],
    now: datetime,
    header: str,
    echo_targets: Sequence[AnyUI],
    append_markdown: Callable[[str], Any] | None,
) -> None:
    """Append one paste line to `entry` and reflect it on every echo target.

    The merge window rolls forward from this line, so a long paste's tail stays
    in the same burst.
    """
    combined = f"{entry.text}\n{text}"
    entry.text = combined
    entry.attachments += attachments
    entry.submitted_at = now
    # Selects the fallback for a target that cannot splice its echo.
    rendered = append_markdown is not None and should_render_user_markdown(combined)
    for target in echo_targets:
        _reflect_merged(target, entry, header, text, rendered=rendered)


def _collect_attachments(attachment_sources: list[Any]) -> list[Any]:
    """Drain every source's pending attachments into one list."""
    attachments: list[Any] = []
    for source in attachment_sources:
        take: Callable[[], list[Any]] | None = getattr(
            source, "take_pending_attachments", None
        )
        if callable(take):
            attachments.extend(take())
    return attachments


def _reflect_merged(
    target: AnyUI, entry: QueuedMessage, header: str, body: str, *, rendered: bool
) -> None:
    """Draw a merged paste line on one target.

    A target that can splice redraws its echo from the whole merged `entry`.
    Otherwise (including when `redraw_echo` raises) the line goes to that
    target's own output path: an ordinary echo, or verbatim when the combined
    message turned Markdown (`rendered`), since rendering one line of it
    would show a meaningless fragment.
    """
    try:
        if target.redraw_echo(entry) is not None:
            return
    except Exception as e:
        CFG.LOGGER.debug(f"Child UI echo redraw failed: {e}")
    try:
        if rendered:
            _emit_echo_verbatim_to(target, header, body)
        else:
            _emit_echo_to(target, header, body)
    except Exception as e:
        CFG.LOGGER.debug(f"Child UI merged-echo fallback failed: {e}")


def _emit_echo_to(target: Any, header: str, body: str) -> None:
    """Write an ordinary user echo to this target only, never a broadcast,
    so a child that already redrew in place gets no duplicate."""
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


def _emit_echo_verbatim_to(target: Any, header: str, body: str) -> None:
    """Write one target's merged paste line verbatim, never rendered."""
    append = getattr(target, "append_to_output", None)
    if not callable(append):
        return
    append(f"{header}{body}\n")


def _is_paste_burst(
    previous: "QueuedMessage | None", now: datetime, window_ms: int
) -> bool:
    """Whether `previous` arrived so recently it can only be part of a paste
    split into Enter keystrokes, not a human re-submission.

    Each merge refreshes `submitted_at`, so the window rolls forward over a
    long paste. A non-positive `window_ms` disables merging.
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

    Returns True when delivered: pydantic-ai's `RunContext.enqueue`
    (priority="asap") hands it to the next model request, so the caller skips
    queuing. Returns False when there is no live run (none in flight, or one
    suspended on a tool approval) or the enqueue failed because the run just
    finished; the caller then queues normally.
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
