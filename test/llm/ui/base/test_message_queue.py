import asyncio

import pytest

from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage


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
