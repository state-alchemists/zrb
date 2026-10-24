"""Ctrl+G also tells the run's shell to step aside.

Delivering the message alone is not enough: the model reads it at the next
model request, and that request comes after the tool call that is holding the
turn. The cut is what turns "the message arrived" into "the message is read
now".
"""

from zrb.llm.shell_cut import ShellCutSignal
from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.ui.base.queue_delivery import (
    DeliveryOutcome,
    send_queued_messages_now,
)


class _RunContext:
    """Stands in for pydantic-ai's `RunContext`: it only needs `enqueue`."""

    def __init__(self):
        self.enqueued = []

    def enqueue(self, text, *attachments, priority=""):
        self.enqueued.append((text, priority))


def _entry(text):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def _send(queue, run_context, *, is_waiting=False, may_interrupt=True, move_shell=None):
    signal = ShellCutSignal()
    report = send_queued_messages_now(
        active_run_context=run_context,
        queue=queue,
        is_turn_running=True,
        is_waiting_for_answer=is_waiting,
        cancel_turn=lambda: None,
        may_interrupt=may_interrupt,
        cut_signal=signal,
        move_shell=move_shell,
    )
    return report, signal


def test_a_caller_can_move_the_shell_without_asking_to_interrupt():
    """The two are separate policies: a command steps aside and keeps running,
    while interrupting the turn is the user's call alone."""
    queue = MessageQueue()
    queue.put_nowait(_entry("look at this"))

    report, signal = _send(queue, _RunContext(), may_interrupt=False, move_shell=True)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert signal.generation == 1


def test_a_caller_can_interrupt_without_moving_the_shell():
    """`may_interrupt` still lets the fallback cancel a turn whose delivery
    failed; `move_shell=False` keeps the running command where it is."""
    queue = MessageQueue()
    queue.put_nowait(_entry("next turn"))

    report, signal = _send(queue, _RunContext(), may_interrupt=True, move_shell=False)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert signal.generation == 0


def test_delivering_now_cuts_the_shell_in_the_way():
    queue = MessageQueue()
    queue.put_nowait(_entry("look at this"))

    report, signal = _send(queue, _RunContext())

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert signal.generation == 1


def test_speech_does_not_move_anything_aside():
    """A hands-free utterance is not a request for the turn to hurry up."""
    queue = MessageQueue()
    queue.put_nowait(_entry("spoken"))

    report, signal = _send(queue, _RunContext(), may_interrupt=False)

    assert signal.generation == 0


def test_nothing_to_deliver_cuts_nothing():
    report, signal = _send(MessageQueue(), _RunContext())

    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert signal.generation == 0


def test_a_dialog_outranks_the_cut():
    """The turn is suspended on a question; no shell is holding anything."""
    queue = MessageQueue()
    queue.put_nowait(_entry("answer"))

    report, signal = _send(queue, _RunContext(), is_waiting=True)

    assert report.outcome is DeliveryOutcome.WAITING_ON_DIALOG
    assert signal.generation == 0


def test_no_live_run_cuts_nothing():
    queue = MessageQueue()
    queue.put_nowait(_entry("next turn"))

    report, signal = _send(queue, None)

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert signal.generation == 0
