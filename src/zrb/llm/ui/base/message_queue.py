"""Message queue shared by every chat UI.

Entries are mutable and `run` reads `entry.text` at execution time, so
editing a queued message is a field write. Anything still in the queue has not
started running.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.ambient_state import input_provenance
from zrb.llm.input_source import KEYBOARD_INPUT, InputProvenance
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

    `text` lets a redraw verify the span still holds the line before splicing.
    """

    start: int
    end: int
    text: str


class QueuedMessage:
    """A user message (or exec job) waiting in the queue.

    `run` must read `text` and `attachments` at execution time so edits made
    while queued are picked up.
    """

    def __init__(
        self,
        *,
        text: str,
        attachments: list["UserContent"],
        kind: str,
        run: Callable[[], Coroutine[Any, Any, None]],
        source: InputProvenance | None = None,
    ):
        self.text = text
        self.attachments = attachments
        self.kind = kind  # "message" | "exec"
        self.run = run
        self.source = source
        # For paste-burst merging; None (e.g. `/exec` jobs) never merges.
        self.submitted_at: datetime | None = None
        # Kept so an edit can rebuild the echoed line in the same style.
        self.echo_marker: str = ""
        self.echo_timestamp: str = ""
        # Keyed by target UI: a `MultiUI` echoes into every child.
        self.echo_spans: dict[Any, EchoSpan] = {}

    @property
    def is_editable(self) -> bool:
        """Whether this entry is a user message (as opposed to an `/exec` job)."""
        return self.kind == "message"


class MessageQueue(asyncio.Queue):
    """An `asyncio.Queue` of `QueuedMessage` entries with peek/remove access."""

    def __init__(self, maxsize: int = 0):
        super().__init__(maxsize)
        # Declared for the type checker; asyncio.Queue's stubs omit them.
        self._queue: deque[QueuedMessage] = deque()
        self._finished: asyncio.Event
        self._putters: deque[asyncio.Future[None]] = deque()
        self._wakeup_next: Callable[[deque[asyncio.Future[None]]], None]

    def peek_latest(self) -> "QueuedMessage | None":
        """The newest not-yet-started entry, or None."""
        return self._queue[-1] if self._queue else None

    def pending(self) -> "tuple[QueuedMessage, ...]":
        """Every not-yet-started entry, oldest first."""
        return tuple(self._queue)

    def latest_editable(self) -> "QueuedMessage | None":
        """The newest not-yet-started user message (skips `/exec` jobs)."""
        for entry in reversed(self._queue):
            if entry.is_editable:
                return entry
        return None

    def editable_before(self, entry: QueuedMessage) -> "QueuedMessage | None":
        """The user message queued before `entry`, or None (also when `entry`
        is no longer queued)."""
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

        Keeps `join()` and blocked `put()` callers working: the entry never
        reaches `task_done`, and the freed slot wakes the next producer.
        """
        self._queue.remove(entry)
        self._unfinished_tasks -= 1
        if self._unfinished_tasks == 0:
            self._finished.set()
        self._wakeup_next(self._putters)


async def _run_queued_message(
    stream_ai_response: Callable[[object, str, list], Awaitable[None]],
    llm_task: object,
    entry: QueuedMessage,
) -> None:
    token = input_provenance.set(entry.source)
    try:
        await stream_ai_response(llm_task, entry.text, entry.attachments)
    finally:
        input_provenance.reset(token)


def submit_user_message_via_queue(
    *,
    append_to_output: AppendOutputFunc,
    active_run_context: Any,
    stream_ai_response: Callable[[object, str, list], Awaitable[None]],
    queue: MessageQueue,
    attachment_sources: list[Any],
    echo_targets: Sequence[AnyUI],
    llm_task: Any,
    user_message: str,
    marker: str,
    append_markdown: Callable[[str], Any] | None = None,
    source: InputProvenance | None = KEYBOARD_INPUT,
) -> None:
    """Shared mechanics behind `BaseUI.submit_user_message` and
    `MultiUI.submit_user_message`: echo, collect attachments, then steer into a
    live run or queue a `QueuedMessage`.

    A standalone UI passes `[self]` as `attachment_sources` and `echo_targets`;
    a `MultiUI` passes its children.

    A terminal without bracketed paste submits a paste one line per Enter; a
    line arriving within `CFG.LLM_UI_PASTE_MERGE_WINDOW` of the newest queued
    entry is appended to it. Steering into a live run outranks merging.
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

    # A non-keyboard source is a distinct input channel; never combine it with
    # an adjacent keyboard burst whose provenance would otherwise win.
    previous = _merge_candidate(queue, now) if source == KEYBOARD_INPUT else None
    if previous is None:
        echo = emit_echo()
        attachments = _collect_attachments(attachment_sources)
        if source in (None, KEYBOARD_INPUT) and steer_into_live_run(
            active_run_context, user_message, attachments
        ):
            return
        entry = QueuedMessage(
            text=user_message,
            attachments=attachments,
            kind="message",
            run=lambda: _run_queued_message(stream_ai_response, llm_task, entry),
            source=source,
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
    if source in (None, KEYBOARD_INPUT) and steer_into_live_run(
        active_run_context, user_message, attachments
    ):
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
    """The newest queued entry, if it is an editable message inside the
    paste-burst window; a queued `/exec` job bounds the merge."""
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
    """Append one paste line to `entry` and reflect it on every echo target."""
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

    A target that cannot splice gets the line through its own output path,
    verbatim when the combined message is Markdown (rendering a fragment is
    meaningless).
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
    """Whether `previous` arrived within `window_ms` (non-positive disables)."""
    if previous is None or previous.submitted_at is None:
        return False
    if window_ms <= 0:
        return False
    return (now - previous.submitted_at).total_seconds() * 1000 <= window_ms


def steer_into_live_run(
    run_context: Any, text: str, attachments: "Sequence[UserContent]"
) -> bool:
    """Try to inject `text`/`attachments` into the turn `run_context` belongs to.

    Returns False when there is no live run or the enqueue failed (the run
    just finished); the caller then queues normally.
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
