"""The send-now ladder: what a "send the queued messages now" attempt does.

The public entry point is `send_queued_messages_now`; the run context it
steers into is the boundary the helper's effect crosses.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.ui.base.queue_delivery import (
    DELIVERED_MARKER,
    DeliveryOutcome,
    DeliveryReport,
    describe_delivery,
    send_queued_messages_now,
)
from zrb.llm.ui.base.ui import BaseUI


def _entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def _send(queue, run_context=None, *, is_turn_running=False, is_waiting=False):
    """Run the ladder; return the report and the cancel calls it made."""
    cancelled = []
    report = send_queued_messages_now(
        active_run_context=run_context,
        queue=queue,
        is_turn_running=is_turn_running,
        is_waiting_for_answer=is_waiting,
        cancel_turn=lambda: cancelled.append(True),
    )
    return report, cancelled


def test_an_empty_queue_moves_nothing():
    report, cancelled = _send(MessageQueue())

    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert report.delivered == 0
    assert cancelled == []


def test_a_live_run_receives_the_queued_messages():
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()

    report, cancelled = _send(queue, run_context)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert report.delivered == 2
    assert cancelled == []
    assert [call.args[0] for call in run_context.enqueue.call_args_list] == [
        "first",
        "second",
    ]
    assert all(
        call.kwargs["priority"] == "asap" for call in run_context.enqueue.call_args_list
    )


def test_a_delivered_message_leaves_the_queue():
    queue = MessageQueue()
    entry = _entry("hello")
    queue.put_nowait(entry)

    report, _ = _send(queue, MagicMock())

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert queue.pending() == ()
    assert queue.qsize() == 0


def test_an_exec_job_is_not_steerable_and_stays_queued():
    queue = MessageQueue()
    exec_job = _entry("ls", kind="exec")
    queue.put_nowait(exec_job)
    run_context = MagicMock()

    report, _ = _send(queue, run_context)

    assert run_context.enqueue.call_count == 0
    assert queue.pending() == (exec_job,)
    assert report.held == 1


def test_an_exec_job_is_an_ordering_barrier():
    # A later message must not jump an earlier shell command: the queue is
    # FIFO, and "report the command's result" needs the command to have run.
    queue = MessageQueue()
    exec_job = _entry("ls", kind="exec")
    message = _entry("report the command's result")
    queue.put_nowait(exec_job)
    queue.put_nowait(message)
    run_context = MagicMock()

    report, cancelled = _send(queue, run_context, is_turn_running=True)

    assert run_context.enqueue.call_count == 0
    assert queue.pending() == (exec_job, message)
    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert cancelled == [True]


def test_messages_before_an_exec_job_are_delivered_and_it_stops_the_drain():
    queue = MessageQueue()
    first = _entry("first")
    exec_job = _entry("ls", kind="exec")
    later = _entry("later")
    for entry in (first, exec_job, later):
        queue.put_nowait(entry)
    run_context = MagicMock()

    report, _ = _send(queue, run_context)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert report.delivered == 1
    assert [call.args[0] for call in run_context.enqueue.call_args_list] == ["first"]
    assert queue.pending() == (exec_job, later)


def test_a_dialog_outranks_a_live_run():
    # The streaming handler keeps re-registering the run context while a turn
    # is suspended on an approval or a question, so a live run is present even
    # though the user has not answered. Delivering there would put the queue
    # ahead of the answer the turn is blocked on.
    queue = MessageQueue()
    queue.put_nowait(_entry("hello"))
    run_context = MagicMock()

    report, cancelled = _send(queue, run_context, is_waiting=True, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.WAITING_ON_DIALOG
    assert run_context.enqueue.call_count == 0
    assert len(queue.pending()) == 1
    assert report.held == 1
    assert cancelled == []


def test_a_dialog_holding_the_input_waits():
    queue = MessageQueue()
    queue.put_nowait(_entry("hello"))

    report, cancelled = _send(queue, is_waiting=True, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.WAITING_ON_DIALOG
    assert report.held == 1
    assert cancelled == []


def test_a_running_turn_without_a_live_run_is_interrupted():
    queue = MessageQueue()
    queue.put_nowait(_entry("hello"))

    report, cancelled = _send(queue, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert report.held == 1
    assert cancelled == [True]


def test_nothing_running_moves_nothing():
    queue = MessageQueue()
    queue.put_nowait(_entry("hello"))

    report, cancelled = _send(queue)

    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert report.held == 1
    assert cancelled == []


def test_a_run_that_ends_mid_flush_stops_the_flush():
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()
    run_context.enqueue.side_effect = RuntimeError("run finished")

    report, _ = _send(queue, run_context)

    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert run_context.enqueue.call_count == 1
    assert len(queue.pending()) == 2


def test_a_partial_flush_that_hits_a_finished_run_interrupts_the_turn():
    # The first enqueue wins; the second fails because the run ended in between
    # — exactly the race the fallback exists for. Reporting DELIVERED_EARLY here
    # would claim success while the second message never reached the turn.
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()
    run_context.enqueue.side_effect = [None, RuntimeError("run finished")]

    report, cancelled = _send(queue, run_context, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert report.delivered == 1
    assert cancelled == [True]
    assert [entry.text for entry in queue.pending()] == ["second"]


def test_a_full_flush_that_ends_the_run_does_not_interrupt():
    # Every queued message was handed over, so the run ending on the last one
    # is not a partial drain — there is nothing left for a cancel to free.
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()

    report, cancelled = _send(queue, run_context, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert report.delivered == 2
    assert cancelled == []


def test_a_failed_enqueue_on_the_only_entry_reports_nothing_moved():
    # A one-entry queue whose enqueue fails delivers nothing and leaves the
    # entry, so it is not a delivered drain at all — the queue is untouched.
    queue = MessageQueue()
    queue.put_nowait(_entry("only"))
    run_context = MagicMock()
    run_context.enqueue.side_effect = RuntimeError("run finished")

    report, cancelled = _send(queue, run_context, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert report.delivered == 0
    assert cancelled == [True]
    assert [entry.text for entry in queue.pending()] == ["only"]


def test_a_full_drain_that_does_not_touch_the_run_context_is_not_partial():
    # Every entry is steerable and succeeded, so the run context being dropped
    # after the drain cannot turn a complete delivery into a partial one.
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()

    report, cancelled = _send(queue, run_context)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert report.delivered == 2
    assert report.held == 0
    assert cancelled == []
    assert queue.pending() == ()


def test_a_partial_flush_with_no_running_turn_reports_the_partial_delivery():
    # Nothing to interrupt, so the delivered part stands and the rest waits —
    # and the report says so rather than "nothing was queued".
    queue = MessageQueue()
    queue.put_nowait(_entry("first"))
    queue.put_nowait(_entry("second"))
    run_context = MagicMock()
    run_context.enqueue.side_effect = [None, RuntimeError("run finished")]

    report, cancelled = _send(queue, run_context)

    assert report.outcome is DeliveryOutcome.DELIVERED_PARTIAL
    assert report.delivered == 1
    assert report.held == 1
    assert cancelled == []
    assert [entry.text for entry in queue.pending()] == ["second"]


def test_an_exec_job_alone_falls_back_to_interrupting_the_turn():
    # Nothing steerable is queued, so the turn is interrupted and the exec job
    # runs as its own turn next.
    queue = MessageQueue()
    queue.put_nowait(_entry("ls", kind="exec"))

    report, cancelled = _send(queue, is_turn_running=True)

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    assert cancelled == [True]


def test_a_delivered_entry_is_marked_before_it_leaves_the_queue():
    queue = MessageQueue()
    entry = _entry("hello")
    queue.put_nowait(entry)

    report, _ = _send(queue, MagicMock())

    assert report.delivered_entries == (entry,)
    assert entry.delivered_at is not None
    assert entry.echo_marker == DELIVERED_MARKER
    assert queue.qsize() == 0


def test_describe_delivery_says_what_happened():
    assert "sent 2 queued message(s)" in describe_delivery(
        DeliveryReport(
            DeliveryOutcome.DELIVERED_EARLY,
            delivered_entries=(_entry("one"), _entry("two")),
            held=1,
        )
    )
    assert "interrupted the turn" in describe_delivery(
        DeliveryReport(DeliveryOutcome.FELL_BACK_TO_CANCEL, held=1)
    )
    # A partial drain that fell back to a cancel names both halves, so the line
    # is not read as a plain interrupt.
    partial_cancel = describe_delivery(
        DeliveryReport(
            DeliveryOutcome.FELL_BACK_TO_CANCEL,
            delivered_entries=(_entry("one"),),
            held=1,
        )
    )
    assert "sent 1 queued message(s)" in partial_cancel
    assert "interrupted the turn" in partial_cancel
    # A partial drain with no turn left to cancel still says what was sent —
    # never "nothing was queued".
    partial = describe_delivery(
        DeliveryReport(
            DeliveryOutcome.DELIVERED_PARTIAL,
            delivered_entries=(_entry("one"),),
            held=1,
        )
    )
    assert "sent 1 queued message(s)" in partial
    assert "still waiting" in partial
    assert "nothing was queued" not in partial
    assert "waiting for your answer" in describe_delivery(
        DeliveryReport(DeliveryOutcome.WAITING_ON_DIALOG, held=1)
    )
    assert describe_delivery(DeliveryReport(DeliveryOutcome.NOTHING_MOVED)) == (
        "nothing was queued"
    )


class _ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return ""


def _make_ui():
    ctx = Context(SharedContext(), "test", 0, "")
    llm_task = MagicMock(hook_manager=None, active_hook_manager=None)
    return _ConcreteUI(ctx=ctx, llm_task=llm_task, history_manager=MagicMock())


def test_the_ui_delivers_its_queue_into_the_live_run():
    ui = _make_ui()
    run_context = MagicMock()
    ui.active_run_context = run_context
    ui.effective_message_queue.put_nowait(_entry("hello"))

    report = ui.send_queued_messages_now()

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    assert run_context.enqueue.call_count == 1


def test_the_ui_redraws_the_echo_of_a_delivered_message():
    """The panel row goes away with the queue entry; the transcript line stays
    and changes marker, so what the model read is still on screen."""
    ui = _make_ui()
    redrawn = []
    ui.redraw_echo = lambda entry: redrawn.append(entry) or "⏩ echo"
    ui.active_run_context = MagicMock()
    entry = _entry("hello")
    ui.effective_message_queue.put_nowait(entry)

    ui.send_queued_messages_now()

    assert redrawn == [entry]
    assert entry.echo_marker == DELIVERED_MARKER


def test_a_child_ui_lets_its_multi_ui_parent_deliver():
    ui = _make_ui()
    parent = MagicMock()
    parent.send_queued_messages_now.return_value = DeliveryReport(
        DeliveryOutcome.DELIVERED_EARLY, delivered_entries=(_entry("hello"),)
    )
    ui.multi_ui_parent = parent
    ui.effective_message_queue.put_nowait(_entry("hello"))

    report = ui.send_queued_messages_now()

    parent.send_queued_messages_now.assert_called_once_with()
    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY


@pytest.mark.asyncio
async def test_a_ui_without_a_live_run_interrupts_the_running_turn():
    ui = _make_ui()
    turn = asyncio.create_task(asyncio.Event().wait())
    ui.running_llm_task = turn
    ui.effective_message_queue.put_nowait(_entry("hello"))

    report = ui.send_queued_messages_now()

    assert report.outcome is DeliveryOutcome.FELL_BACK_TO_CANCEL
    with pytest.raises(asyncio.CancelledError):
        await turn
