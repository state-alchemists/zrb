import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.base.message_queue import (
    MessageQueue,
    QueuedMessage,
    steer_into_live_run,
    submit_user_message_via_queue,
)


def make_entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def test_queued_message_is_editable_for_messages_only():
    assert make_entry("hello").is_editable is True
    assert make_entry("ls", kind="exec").is_editable is False


def test_queued_message_echo_defaults():
    entry = make_entry("hello")
    assert entry.echo_marker == ""
    assert entry.echo_timestamp == ""
    assert entry.echo_span is None
    assert entry.echo_text == ""


def test_peek_latest_returns_newest():
    queue = MessageQueue()
    a = make_entry("a")
    queue.put_nowait(a)
    queue.put_nowait(make_entry("b"))
    assert queue.peek_latest() is not a


def test_peek_latest_none_when_empty():
    assert MessageQueue().peek_latest() is None


def test_latest_editable_skips_exec_jobs():
    queue = MessageQueue()
    exec_job = make_entry("ls", kind="exec")
    message = make_entry("hello")
    queue.put_nowait(exec_job)
    queue.put_nowait(message)
    assert queue.latest_editable() is message
    # Only an exec job queued — nothing editable.
    queue2 = MessageQueue()
    queue2.put_nowait(make_entry("ls", kind="exec"))
    assert queue2.latest_editable() is None


def test_latest_editable_none_when_empty():
    assert MessageQueue().latest_editable() is None


def test_editable_before_and_after():
    queue = MessageQueue()
    a, b, c = make_entry("a"), make_entry("b"), make_entry("c")
    for entry in (a, b, c):
        queue.put_nowait(entry)
    assert queue.editable_before(a) is None
    assert queue.editable_before(b) is a
    assert queue.editable_before(c) is b
    assert queue.editable_after(a) is b
    assert queue.editable_after(b) is c
    assert queue.editable_after(c) is None


def test_editable_navigation_skips_exec_jobs():
    queue = MessageQueue()
    a = make_entry("a")
    exec_job = make_entry("ls", kind="exec")
    b = make_entry("b")
    for entry in (a, exec_job, b):
        queue.put_nowait(entry)
    assert queue.editable_before(b) is a  # exec job between them is skipped
    assert queue.editable_after(a) is b


def test_editable_navigation_none_for_removed_entry():
    queue = MessageQueue()
    entry = make_entry("hello")
    queue.put_nowait(entry)
    queue.remove(entry)
    assert queue.editable_before(entry) is None
    assert queue.editable_after(entry) is None
    assert queue.latest_editable() is None


def test_contains_reflects_removal():
    queue = MessageQueue()
    entry = make_entry("hello")
    queue.put_nowait(entry)
    assert queue.contains(entry)
    queue.remove(entry)
    assert not queue.contains(entry)
    assert queue.empty()


@pytest.mark.asyncio
async def test_get_pops_the_entry_and_breaks_contains():
    queue = MessageQueue()
    entry = make_entry("hello")
    queue.put_nowait(entry)
    popped = await queue.get()
    assert popped is entry
    assert not queue.contains(entry)


def test_remove_does_not_disturb_qsize_bookkeeping():
    queue = MessageQueue()
    a = make_entry("a")
    b = make_entry("b")
    queue.put_nowait(a)
    queue.put_nowait(b)
    queue.remove(a)
    assert queue.qsize() == 1
    assert queue.peek_latest() is b


def test_remove_unknown_entry_raises():
    queue = MessageQueue()
    with pytest.raises(ValueError):
        queue.remove(make_entry("never queued"))


@pytest.mark.asyncio
async def test_remove_decrements_unfinished_tasks_so_join_resolves():
    # `put_nowait` bumped the unfinished-task counter; a removed entry never
    # reaches `task_done`, so `remove` must decrement it or `join()` hangs.
    queue = MessageQueue()
    entry = make_entry("a")
    queue.put_nowait(entry)

    queue.remove(entry)

    await asyncio.wait_for(queue.join(), timeout=1)


@pytest.mark.asyncio
async def test_remove_combined_with_task_done_resolves_join():
    # Removing one of two entries must not deadlock the other's task_done.
    queue = MessageQueue()
    a, b = make_entry("a"), make_entry("b")
    queue.put_nowait(a)
    queue.put_nowait(b)

    queue.remove(a)
    popped = await queue.get()
    queue.task_done()

    await asyncio.wait_for(queue.join(), timeout=1)
    assert popped is b


# ── steer_into_live_run (ADR-0078) ──────────────────────────────────────────


def test_steer_into_live_run_false_without_active_run():
    assert steer_into_live_run(None, "hello", []) is False


def test_steer_into_live_run_delivers_via_enqueue():
    run_context = MagicMock()
    attachments = ["image-bytes"]

    assert steer_into_live_run(run_context, "hello", attachments) is True

    run_context.enqueue.assert_called_once_with("hello", "image-bytes", priority="asap")


def test_steer_into_live_run_false_when_enqueue_raises():
    run_context = MagicMock()
    run_context.enqueue.side_effect = RuntimeError("run already finished")

    assert steer_into_live_run(run_context, "hello", []) is False


# ── submit_user_message_via_queue (shared BaseUI/MultiUI mechanics) ─────────


def _stub_stream_ai_response(llm_task, text, attachments):
    pass


def test_submit_user_message_via_queue_single_target_echoes_and_queues():
    """Standalone-UI shape: attachment_sources/echo_targets == [self]."""
    outputs = []
    tracked = []

    class Target:
        def take_pending_attachments(self):
            return ["img"]

        def _track_echo_span(self, entry, echo):
            tracked.append((entry, echo))

    target = Target()
    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=outputs.append,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[target],
        echo_targets=[target],
        llm_task=object(),
        user_message="hello",
        marker="💬",
    )

    assert len(outputs) == 1
    assert "💬" in outputs[0] and "hello" in outputs[0]
    assert queue.qsize() == 1
    entry = queue.peek_latest()
    assert entry.text == "hello"
    assert entry.attachments == ["img"]
    assert entry.echo_marker == "💬"
    assert len(tracked) == 1
    assert tracked[0][0] is entry


def test_submit_user_message_via_queue_fans_out_to_multiple_targets():
    """MultiUI shape: attachment_sources/echo_targets are the children, not
    the router's own owner."""
    tracked_by = []

    class Child:
        def __init__(self, name, attachments):
            self.name = name
            self._attachments = attachments

        def take_pending_attachments(self):
            return self._attachments

        def _track_echo_span(self, entry, echo):
            tracked_by.append(self.name)

    children = [Child("a", ["x"]), Child("b", ["y"])]
    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=children,
        echo_targets=children,
        llm_task=object(),
        user_message="hi",
        marker="💬",
    )

    entry = queue.peek_latest()
    assert entry.attachments == ["x", "y"]
    assert tracked_by == ["a", "b"]


def test_submit_user_message_via_queue_steers_into_live_run_instead_of_queuing():
    run_context = MagicMock()
    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        active_run_context=run_context,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[],
        echo_targets=[],
        llm_task=object(),
        user_message="steer me",
        marker="💬",
    )

    run_context.enqueue.assert_called_once_with("steer me", priority="asap")
    assert queue.qsize() == 0


def test_submit_user_message_via_queue_ignores_targets_without_the_hooks():
    """A target with neither `take_pending_attachments` nor `_track_echo_span`
    (e.g. a Telegram child) must not break the loop."""
    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[object()],
        echo_targets=[object()],
        llm_task=object(),
        user_message="hi",
        marker="💬",
    )

    entry = queue.peek_latest()
    assert entry.attachments == []
