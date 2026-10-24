"""Delivering queued messages into the running turn on demand.

The message queue holds the turns a user submitted that the model has not
seen yet. Normally they wait for the running turn to finish; the send-now path
hands them to the live run instead, so the model reads them within this turn.

The ladder mirrors the one Claude Code drives its send-now key with: deliver
into the live run when there is one, wait when a dialog owns the input, and
fall back to interrupting the turn when there is no live run to steer into.
The dialog is checked *before* the live run: the run context stays registered
while a turn is suspended on an approval or a question, so a live run is no
proof the model is ready to read anything.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from zrb.llm.ui.base.message_queue import MessageQueue, steer_into_live_run

if TYPE_CHECKING:
    from zrb.llm.shell_cut import ShellCutSignal
    from zrb.llm.ui.base.message_queue import QueuedMessage

DELIVERED_MARKER = "⏩"
"""The echo marker of a message a send-now call handed to the live run."""


class DeliveryOutcome(str, Enum):
    """How a send-now attempt ended."""

    DELIVERED_EARLY = "delivered_early"
    DELIVERED_PARTIAL = "delivered_partial"
    FELL_BACK_TO_CANCEL = "fell_back_to_cancel"
    NOTHING_MOVED = "nothing_moved"
    WAITING_ON_DIALOG = "waiting_on_dialog"


@dataclass
class DeliveryReport:
    """What one send-now attempt did.

    `delivered_entries` are the messages handed to the live run, in queue
    order; `held` counts the entries still waiting in the queue.
    """

    outcome: DeliveryOutcome
    delivered_entries: "tuple[QueuedMessage, ...]" = ()
    held: int = 0

    @property
    def delivered(self) -> int:
        """How many messages this attempt handed to the live run."""
        return len(self.delivered_entries)


def send_queued_messages_now(
    *,
    active_run_context: object,
    queue: MessageQueue,
    is_turn_running: bool,
    is_waiting_for_answer: bool,
    cancel_turn: Callable[[], None],
    may_interrupt: bool = True,
    only_ready: bool = False,
    immediate_entry: QueuedMessage | None = None,
    cut_signal: "ShellCutSignal | None" = None,
) -> DeliveryReport:
    """Hand the queued messages to the running turn, now.

    A live run receives each queued message as an extra user turn, so the
    model reads it within the current turn (pydantic-ai delivers it at the
    next model request). Without a live run there is nothing to steer into:
    a turn that is running is interrupted so the message loop picks the queue
    up right away, and a turn waiting on the user is left alone.

    A dialog outranks the live run, and is checked first. While a tool
    approval or a question waits, the streaming handler keeps re-registering
    the run context (`agent/run/runner.py`), so a live run is present even
    though the user has not answered the prompt; delivering there would put
    the queue ahead of the answer the turn is blocked on.

    An `/exec` job at the head is an ordering barrier (see `_steer_entries`):
    when it delivers nothing, the attempt falls through to the cancel below,
    which runs the whole queue in its original order — the `/exec` job first.

    `may_interrupt=False` is for a caller that did not ask for the turn to
    stop: hands-free speech is delivered at the earliest safe model request,
    and otherwise waits for the next turn. Interrupting is the user's call
    (Esc, Ctrl+G, a stop word), not a side effect of talking.

    `only_ready=True` takes entries past their grace, leaving edits in progress
    untouched. Hands-free speech can also include `immediate_entry`, its own
    newly queued utterance, without flushing anyone else's draft. An explicit
    Ctrl+G takes everything: that is the user's decision.

    *cut_signal* is the run's own (see `zrb.llm.shell_cut`). An explicit
    send-now cuts it before steering, so a `Shell` call still holding the turn
    moves its command to the background instead of delaying the message until
    the command ends.
    """
    entries = (
        queue.deliverable(time.monotonic(), immediate_entry=immediate_entry)
        if only_ready
        else queue.pending()
    )
    if not entries:
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED, held=queue.qsize())

    if is_waiting_for_answer:
        return DeliveryReport(DeliveryOutcome.WAITING_ON_DIALOG, held=queue.qsize())

    # A running `Shell` call is the one thing that can still keep the model
    # from reading this message: the request that would carry it is assembled
    # after the tool returns, and a long command returns when it is done. Ask
    # the run's shells to step aside first. Only an explicit send-now does it:
    # `may_interrupt` is exactly "the user asked for this turn to move now".
    if may_interrupt and active_run_context is not None and cut_signal is not None:
        cut_signal.cut()

    delivered: "tuple[QueuedMessage, ...]" = ()
    stopped_with_entries_left = False
    if active_run_context is not None:
        delivered, stopped_with_entries_left = _steer_entries(
            queue, active_run_context, entries
        )

    # Every message reached the live run (or the drain stopped on the last
    # entry, which delivers everything and leaves nothing): the rest, if any,
    # are entries the drain never reached, and wait for the next turn as they
    # would have without the key.
    if delivered and not stopped_with_entries_left:
        return DeliveryReport(
            DeliveryOutcome.DELIVERED_EARLY,
            delivered_entries=delivered,
            held=queue.qsize(),
        )

    # The run ended mid-drain and left entries behind: interrupting the turn
    # lets the message loop pick the remainder up right away — the same
    # fallback the no-live-run case uses, and the one the failed enqueue is
    # itself the signal for. `FELL_BACK_TO_CANCEL` is reserved for the runs
    # where the cancel was actually asked for.
    if is_turn_running and may_interrupt:
        cancel_turn()
        return DeliveryReport(
            DeliveryOutcome.FELL_BACK_TO_CANCEL,
            delivered_entries=delivered,
            held=queue.qsize(),
        )

    # Nothing left to interrupt, but some messages did reach the turn. Say so:
    # reporting `NOTHING_MOVED` here would contradict the delivered count the
    # caller renders.
    if delivered:
        return DeliveryReport(
            DeliveryOutcome.DELIVERED_PARTIAL,
            delivered_entries=delivered,
            held=queue.qsize(),
        )

    return DeliveryReport(DeliveryOutcome.NOTHING_MOVED, held=queue.qsize())


def _steer_entries(
    queue: MessageQueue, run_context: object, entries: "tuple[QueuedMessage, ...]"
) -> "tuple[tuple[QueuedMessage, ...], bool]":
    """Steer the still-queued messages at the head of *entries*.

    Returns `(delivered_entries, stopped_with_entries_left)`: the messages
    handed to the live run, in queue order, and whether the drain stopped
    early — on a failed `enqueue` (the run finished between two calls) — *and*
    left entries behind. A failed `enqueue` on the last entry delivers
    everything and leaves nothing: that is a complete drain, not a partial one,
    so the flag stays false and the caller reports it as `DELIVERED_EARLY`.

    Each delivered entry is marked (`delivered_at`, `DELIVERED_MARKER`) here,
    where the entry leaves the queue, so the echo a caller redraws afterwards
    says what the model read rather than what was still waiting.

    An `/exec` job is not steerable (ADR-0078) and is an ordering barrier: it
    stops the drain rather than being skipped. The queue is FIFO and the
    message loop drains it head-first, so steering a message past an `/exec`
    job would run that message before a command the user queued first — and a
    follow-up like "report the command's result" most needs the command it
    refers to to have run. The snapshot is taken from the queue itself and
    nothing awaits while it is drained, so every entry is still queued when it
    is removed.
    """
    delivered: list[QueuedMessage] = []
    failed_enqueue = False
    for entry in entries:
        if not entry.is_editable:
            break
        if not steer_into_live_run(run_context, entry.text, entry.attachments):
            failed_enqueue = True
            break
        queue.remove(entry)
        entry.delivered_at = datetime.now()
        entry.echo_marker = DELIVERED_MARKER
        delivered.append(entry)
    return tuple(delivered), failed_enqueue and queue.qsize() > 0


def describe_delivery(report: DeliveryReport) -> str:
    """One line saying what a send-now attempt did."""
    if report.outcome is DeliveryOutcome.DELIVERED_EARLY:
        return (
            f"sent {report.delivered} queued message(s) into this turn"
            f" ({report.held} still waiting)"
        )
    if report.outcome is DeliveryOutcome.DELIVERED_PARTIAL:
        return (
            f"sent {report.delivered} queued message(s), then the run ended"
            f" ({report.held} still waiting)"
        )
    if report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL:
        if report.delivered:
            return (
                f"sent {report.delivered} queued message(s), then the run ended —"
                " interrupted the turn so the rest run next"
            )
        return "interrupted the turn, so the queue runs next"
    if report.outcome is DeliveryOutcome.WAITING_ON_DIALOG:
        return "waiting for your answer, so the queue runs after it"
    return "nothing was queued"
