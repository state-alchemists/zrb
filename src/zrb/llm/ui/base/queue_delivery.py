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

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from zrb.llm.ui.base.message_queue import MessageQueue, steer_into_live_run

if TYPE_CHECKING:
    from zrb.llm.ui.base.message_queue import QueuedMessage


class DeliveryOutcome(str, Enum):
    """How a send-now attempt ended."""

    DELIVERED_EARLY = "delivered_early"
    FELL_BACK_TO_CANCEL = "fell_back_to_cancel"
    NOTHING_MOVED = "nothing_moved"
    WAITING_ON_DIALOG = "waiting_on_dialog"


@dataclass
class DeliveryReport:
    """What one send-now attempt did.

    `delivered` counts the messages handed to the live run; `held` counts the
    entries still waiting in the queue.
    """

    outcome: DeliveryOutcome
    delivered: int = 0
    held: int = 0


def send_queued_messages_now(
    *,
    active_run_context: object,
    queue: MessageQueue,
    is_turn_running: bool,
    is_waiting_for_answer: bool,
    cancel_turn: Callable[[], None],
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
    """
    entries = queue.pending()
    if not entries:
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)

    if is_waiting_for_answer:
        return DeliveryReport(DeliveryOutcome.WAITING_ON_DIALOG, held=queue.qsize())

    if active_run_context is not None:
        delivered = _steer_entries(queue, active_run_context, entries)
        if delivered:
            return DeliveryReport(
                DeliveryOutcome.DELIVERED_EARLY,
                delivered=delivered,
                held=queue.qsize(),
            )

    if is_turn_running:
        cancel_turn()
        return DeliveryReport(
            DeliveryOutcome.FELL_BACK_TO_CANCEL, held=queue.qsize()
        )

    return DeliveryReport(DeliveryOutcome.NOTHING_MOVED, held=queue.qsize())


def _steer_entries(
    queue: MessageQueue, run_context: object, entries: "tuple[QueuedMessage, ...]"
) -> int:
    """Steer the still-queued messages at the head of *entries*; return the count.

    An `/exec` job is not steerable (ADR-0078) and is an ordering barrier: it
    stops the drain rather than being skipped. The queue is FIFO and the
    message loop drains it head-first, so steering a message past an `/exec`
    job would run that message before a command the user queued first — and a
    follow-up like "report the command's result" most needs the command it
    refers to to have run. The snapshot is taken from the queue itself and
    nothing awaits while it is drained, so every entry is still queued when it
    is removed.
    """
    delivered = 0
    for entry in entries:
        if not entry.is_editable:
            break
        if not steer_into_live_run(run_context, entry.text, entry.attachments):
            break
        queue.remove(entry)
        delivered += 1
    return delivered


def describe_delivery(report: DeliveryReport) -> str:
    """One line saying what a send-now attempt did."""
    if report.outcome is DeliveryOutcome.DELIVERED_EARLY:
        return (
            f"sent {report.delivered} queued message(s) into this turn"
            f" ({report.held} still waiting)"
        )
    if report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL:
        return "interrupted the turn, so the queue runs next"
    if report.outcome is DeliveryOutcome.WAITING_ON_DIALOG:
        return "waiting for your answer, so the queue runs after it"
    return "nothing was queued"
