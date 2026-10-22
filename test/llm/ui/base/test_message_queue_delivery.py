"""What a checkpoint may take out of the queue: the grace and the edit hold.

`MessageQueue.deliverable` is the queue's own answer, read by the run loop's
checkpoint call — not by the explicit send (`Ctrl+G`), which takes everything.
"""

from zrb.llm.ui.base.message_queue import MessageQueue, QueuedMessage


def _entry(text):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def test_deliverable_takes_an_old_entry_and_leaves_a_young_one():
    queue = MessageQueue()
    old = _entry("old")
    old.queued_at = 100.0
    young = _entry("young")
    young.queued_at = 109.5
    queue.put_nowait(old)
    queue.put_nowait(young)

    assert queue.deliverable(110.0) == (old,)


def test_deliverable_leaves_the_entry_being_edited_and_keeps_the_rest():
    """A held entry is skipped, not treated as a barrier: the messages behind it
    still reach the turn, and the edited one rejoins when Enter resubmits it."""
    queue = MessageQueue()
    edited = _entry("edited")
    edited.queued_at = 100.0
    edited.is_being_edited = True
    behind = _entry("behind")
    behind.queued_at = 100.0
    queue.put_nowait(edited)
    queue.put_nowait(behind)

    assert queue.deliverable(110.0) == (behind,)


def test_deliverable_holds_a_paste_that_is_still_arriving():
    """A merged paste line refreshes the entry's clock, so a burst the terminal
    delivers one line per Enter is not delivered halfway through."""
    queue = MessageQueue()
    entry = _entry("first line")
    entry.queued_at = 100.0
    entry.submitted_at = None
    queue.put_nowait(entry)

    assert queue.deliverable(100.5) == ()

    entry.queued_at = 100.4
    assert queue.deliverable(100.5) == ()
    assert queue.deliverable(101.5) == (entry,)
