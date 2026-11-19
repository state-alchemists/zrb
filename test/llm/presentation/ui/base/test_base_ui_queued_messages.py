"""What `BaseUI` does with a message once it is in the queue.

A submitted message is echoed as queued while a turn is in flight, and the
submit path never reaches into the live run — Ctrl+G is what hands the queue
over. `submit_message_now` is the one door that does hand a message across, and
speech is what comes through it; with nothing to steer into, the words become
the next turn instead. From there an entry can be edited in place or deleted,
refused once its turn has started. Under a `MultiUI` all of it happens against
the parent's queue, and each child's own echo is redrawn or removed, because one
entry is shared but the output buffers are not.
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.contracts.shared.input_source import DICTATION_INPUT, KEYBOARD_INPUT
from zrb.llm.presentation.ui.base.message_queue import MessageQueue, QueuedMessage
from zrb.llm.presentation.ui.base.queue_delivery import DeliveryOutcome

from .base_ui_support import ConcreteUI


def make_entry(text):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind="message", run=run)


def test_submit_user_message_marks_queued_while_thinking(base_ui, monkeypatch):
    """A message typed while a turn is in flight is echoed as queued, not sent."""
    # Disable paste-burst merging so the two submits stay separate.
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 0, raising=False)
    outputs: list[str] = []
    with patch.object(base_ui, "append_to_output", side_effect=outputs.append):
        base_ui.submit_user_message(base_ui.llm_task, "later")
        assert base_ui.queued_message_count == 1
        assert "💬" in outputs[0]

        # Flip the flag the way _stream_ai_response does.
        base_ui.is_thinking = True
        base_ui.submit_user_message(base_ui.llm_task, "even later")

    assert base_ui.queued_message_count == 2
    assert "⏳" in outputs[1]
    assert "even later" in outputs[1]


def test_submit_user_message_queues_even_with_a_live_run_context(base_ui):
    """A message sent while a turn is live is queued, so Up Arrow can recall it.

    Ctrl+G is what hands the queue to the live run; the submit path no longer
    reaches into it (ADR-0078 as rewritten).
    """
    base_ui.active_run_context = MagicMock()
    with patch.object(base_ui, "append_to_output"):
        base_ui.submit_user_message(base_ui.llm_task, "edit me")

    base_ui.active_run_context.enqueue.assert_not_called()
    assert base_ui.queued_message_count == 1


def test_submit_user_message_falls_back_to_queue_without_active_run_context(
    base_ui,
):
    """No live turn (the default) keeps the existing queue behavior."""
    assert base_ui.active_run_context is None
    with patch.object(base_ui, "append_to_output"):
        base_ui.submit_user_message(base_ui.llm_task, "later")

    assert base_ui.queued_message_count == 1


def test_submit_user_message_falls_back_to_queue_when_enqueue_raises(base_ui):
    """A run that finished between the check and the call must not lose the
    message -- it falls back to the queue instead of being dropped."""
    live_run = MagicMock()
    live_run.enqueue.side_effect = RuntimeError("run already finished")
    base_ui.active_run_context = live_run
    with patch.object(base_ui, "append_to_output"):
        base_ui.submit_user_message(base_ui.llm_task, "steer me")

    assert base_ui.queued_message_count == 1


def test_submit_message_uses_own_llm_task(base_ui):
    """Public `submit_message` (no llm_task argument) forwards to the queue
    path with the UI's own task — the seam sub-agent continuation code uses
    to hand the main agent a synthesized report."""
    with patch.object(base_ui, "submit_user_message") as mock_submit:
        base_ui.submit_message("report text")
    mock_submit.assert_called_once_with(base_ui.llm_task, "report text", KEYBOARD_INPUT)


def test_submit_message_now_queues_the_message_and_sends_it_into_the_live_run(
    base_ui,
):
    """Voice skips its own grace, without interrupting or flushing drafts."""
    live_run = MagicMock()
    base_ui.active_run_context = live_run
    with patch.object(base_ui, "append_to_output"):
        report = base_ui.submit_message_now("spoken", DICTATION_INPUT)

    assert report.outcome is DeliveryOutcome.DELIVERED_EARLY
    live_run.enqueue.assert_called_once_with("spoken", priority="asap")
    assert base_ui.queued_message_count == 0


def test_speech_leaves_an_edited_message_queued(base_ui):
    edited = make_entry("draft")
    edited.is_being_edited = True
    base_ui.message_queue.put_nowait(edited)
    run = MagicMock()
    base_ui.active_run_context = run

    with patch.object(base_ui, "append_to_output"):
        report = base_ui.submit_message_now(
            "spoken", DICTATION_INPUT, may_interrupt=False
        )

    assert [entry.text for entry in report.delivered_entries] == ["spoken"]
    assert base_ui.message_queue.pending() == (edited,)
    run.enqueue.assert_called_once_with("spoken", priority="asap")


def test_submit_message_now_leaves_the_message_queued_when_no_turn_runs(base_ui):
    """With nothing to steer into, the words still become the next turn."""
    with patch.object(base_ui, "append_to_output"):
        report = base_ui.submit_message_now("spoken")

    assert report.outcome is DeliveryOutcome.NOTHING_MOVED
    assert base_ui.queued_message_count == 1


@pytest.mark.asyncio
async def test_edit_queued_message_replaces_text_in_place(base_ui):
    """A still-queued message's text can be replaced without resubmitting."""
    entry = make_entry("original")
    base_ui.message_queue.put_nowait(entry)

    assert base_ui.edit_queued_message(entry, "edited") is True
    assert entry.text == "edited"
    assert base_ui.queued_message_count == 1

    # Once the turn starts (entry popped), the edit is refused.
    popped = await base_ui.message_queue.get()
    assert popped is entry
    assert base_ui.edit_queued_message(entry, "too late") is False
    assert entry.text == "edited"


def test_edit_queued_message_strips_whitespace(base_ui):
    entry = make_entry("original")
    base_ui.message_queue.put_nowait(entry)

    assert base_ui.edit_queued_message(entry, "  edited  ") is True
    assert entry.text == "edited"
    assert entry.is_editable


# ── MultiUI routing (effective_message_queue + shared-entry redraw) ────────


class FakeMultiUIParent:
    def __init__(self, children=None):
        self.message_queue = MessageQueue()
        self.children = children if children is not None else []


class RecordingUI(ConcreteUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redrawn = []
        self.removed = []

    def redraw_echo(self, entry):
        self.redrawn.append(entry)

    def remove_echo(self, entry):
        self.removed.append(entry)


def make_ui():
    return RecordingUI(
        ctx=Context(SharedContext(), "test", 0, ""),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
    )


def test_effective_message_queue_routes_to_parent_queue(base_ui):
    """A child UI in a MultiUI submits and edits against the shared queue."""
    parent = FakeMultiUIParent()
    base_ui.multi_ui_parent = parent
    entry = make_entry("hello")
    parent.message_queue.put_nowait(entry)

    assert base_ui.effective_message_queue is parent.message_queue
    assert base_ui.queued_message_count == 1


def test_edit_queued_message_updates_shared_entry_and_broadcasts_redraw():
    """Editing from one child rewrites the shared entry for every child."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent.message_queue.put_nowait(entry)

    assert child_a.edit_queued_message(entry, "edited") is True
    assert entry.text == "edited"
    assert parent.message_queue.contains(entry)
    # The entry is shared, so the echo redraw was broadcast to both children.
    assert child_a.redrawn == [entry]
    assert child_b.redrawn == [entry]


@pytest.mark.asyncio
async def test_edit_queued_message_refused_after_turn_started_in_multi_ui():
    """A message popped from the shared queue is no longer editable."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent.message_queue.put_nowait(entry)

    popped = await parent.message_queue.get()
    assert popped is entry

    assert child_a.edit_queued_message(entry, "too late") is False
    assert entry.text == "original"
    assert child_a.redrawn == []
    assert child_b.redrawn == []


def test_delete_queued_message_drops_the_entry_for_every_child():
    """The entry is shared, but each child's output buffer holds its own echo,
    so a delete has to reach all of them — a sibling left out would show a line
    for a message whose turn never runs."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent.message_queue.put_nowait(entry)

    child_a.delete_queued_message(entry)

    assert not parent.message_queue.contains(entry)
    assert child_a.removed == [entry]
    assert child_b.removed == [entry]


@pytest.mark.asyncio
async def test_delete_queued_message_leaves_a_started_message_alone():
    """A message popped from the shared queue is no longer deletable, and no
    child is asked to take an echo out for it."""
    child_a, child_b = make_ui(), make_ui()
    parent = FakeMultiUIParent(children=[child_a, child_b])
    child_a.multi_ui_parent = parent
    child_b.multi_ui_parent = parent
    entry = make_entry("original")
    parent.message_queue.put_nowait(entry)

    popped = await parent.message_queue.get()
    assert popped is entry

    child_a.delete_queued_message(entry)

    assert child_a.removed == []
    assert child_b.removed == []
