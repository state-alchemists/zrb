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
        # Where each target UI's echo of this message landed in that target's
        # own output buffer, keyed by the UI instance that owns the buffer. A
        # `MultiUI` writes one echo into every child's buffer, so each child
        # records (and later redraws against) its own span — a shared scalar
        # would let the last child's span clobber the others', leaving the
        # rest to see a stale span and fall back to a duplicate echo. An entry
        # with no echo (an `/exec` job, a rendered markdown echo, or a
        # confirmation-buffered line) simply has no key.
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
    echo_targets: Sequence[AnyUI],
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
    turn — the model receives the pasted block as one message. Merging only
    applies on the queued-turn path: a submission while a live run is
    connected is steered into that run (`priority="asap"`) even when an
    editable message is still inside the merge window, so an older queued
    message never swallows a line (or its attachments) the run should get.
    Steering is *attempted* rather than assumed from a non-None run context —
    `steer_into_live_run` returns False when the run finished between the
    caller reading the context and the `enqueue` call, and that submission
    falls back to the queue, where it is still part of the same burst and
    merges like any other queued line.

    The model-facing text is preserved exactly: `QueuedMessage.text` is the
    raw submissions joined with a newline — leading indentation, trailing
    spaces, and intentional blank lines survive, and stripping is left to the
    echo/display paths where it is wanted.

    A line that does not merge is echoed before its attachments are collected,
    matching a plain pre-merge submit: if a `take_pending_attachments`
    implementation raises, the submission aborts but the user's line is
    already visible in the output pane rather than silently swallowed.

    The merge is bounded by a queued `/exec` job: only the newest queue entry
    itself (never an older editable message reached past an `/exec` in
    between) may absorb the new line. A merged line is reflected per target —
    one that can splice its echo redraws it in place; one that cannot (a
    bufferless UI, or a rendered first echo with no tracked span) gets an
    ordinary echo of the line through its own output path, never a broadcast
    that duplicates a child that already redrew. Each target tracks its own
    echo span on the shared entry, so one child's redraw never invalidates
    another's. A child whose redraw fails is treated like one that cannot
    redraw — the failure is logged and the other targets still get their path.
    And when the combined text turns Markdown, a target that can replace its
    echo renders the *whole* combined message in place of the plain opening
    echo, so a multi-line construct (a fenced code block, a list) reads as one
    block rather than a partial render of just the newest line; a target with
    nothing to splice gets the merged line verbatim instead. The span survives
    either way, so a later edit can still update the displayed message.
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
        # A non-merge line is echoed before attachments are collected — exactly
        # as a plain submit with no merge feature would — so a collection
        # failure surfaces with the user's line already in the output pane.
        echo = emit_echo()
        attachments = _collect_attachments(attachment_sources)
        if steer_into_live_run(active_run_context, user_message, attachments):
            # A live-run submission never reaches the queue — the echo above is
            # its only rendering.
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

    # A paste line folds into the queued entry; its only visible trace is the
    # per-target reflection, never a line echo of its own. If collecting
    # attachments fails the line would vanish entirely, so emit it here before
    # the failure propagates — the same promise as the open-line path above.
    try:
        attachments = _collect_attachments(attachment_sources)
    except Exception:
        emit_echo()
        raise
    if steer_into_live_run(active_run_context, user_message, attachments):
        # Steering outranks merging, so it is tried before the merge is
        # committed rather than gated on `active_run_context` being None: a
        # context whose run finished in the meantime fails its enqueue, and
        # that submission belongs in the queue — as part of this burst, not as
        # a turn of its own. A steered line renders like any other live-run
        # submission, which is a plain echo.
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
    if not _is_paste_burst(previous, now, CFG.LLM_UI_PASTE_MERGE_MS):
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
    # The combined message may have turned Markdown. A spliceable target
    # redraws its echo from `entry.text`, so it shows the whole merged message
    # rendered rather than a partial render of just the newest line; only the
    # fallback for a target with nothing to splice differs, which is what
    # `rendered` selects.
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

    A target that can splice redraws its echo from `entry` — the whole merged
    message, so a Markdown construct spanning several lines reads as one
    block. A target with nothing to splice falls back to its own output path:
    an ordinary echo of the line, or, when the combined message turned
    Markdown (`rendered`), the line verbatim — rendering just the new line
    would show a fragment (a lone fence, a bare `- item`) with no meaning.

    A target whose `redraw_echo` raises is treated like one that cannot
    redraw — the failure is logged and the line falls back to its echo, so one
    broken target never aborts the submission or starves the remaining ones.
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
    """Write an ordinary user echo into one target's own output path.

    Used for a merged paste line on a target whose `redraw_echo` could not
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


def _emit_echo_verbatim_to(target: Any, header: str, body: str) -> None:
    """Write one target's merged paste line verbatim — never rendered.

    The combined message became Markdown; rendering just `body` would show a
    partial construct with no meaning (a lone fence, a bare `- item`). A
    target with no spliceable echo gets the raw line so it stays visible
    without a half-rendered fragment.
    """
    append = getattr(target, "append_to_output", None)
    if not callable(append):
        return
    append(f"{header}{body}\n")


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
