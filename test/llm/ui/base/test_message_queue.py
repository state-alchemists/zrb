import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import UserContent

from zrb.config.config import CFG
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
    attachments: list[UserContent] = ["image-bytes"]

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


def test_submit_user_message_via_queue_renders_markdownish_echo():
    """A markdownish paste renders via append_markdown and claims no echo span."""
    outputs: list[tuple[tuple, dict]] = []
    rendered: list[str] = []

    class Target:
        def take_pending_attachments(self):
            return []

        def _track_echo_span(self, entry, echo):
            raise AssertionError("a rendered echo must not claim a span")

    queue = MessageQueue()
    body = "## Plan\n\n- a\n- b"

    submit_user_message_via_queue(
        append_to_output=lambda *v, **k: outputs.append((v, k)),
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[Target()],
        echo_targets=[Target()],
        llm_task=object(),
        user_message=body,
        marker="💬",
        append_markdown=rendered.append,
    )

    assert rendered == [body]
    assert len(outputs) == 1
    header_values, header_kwargs = outputs[0]
    assert header_kwargs == {"end": ""}
    assert header_values[0].startswith("\n💬 ")
    assert header_values[0].endswith(">> ")
    entry = queue.peek_latest()
    assert entry.text == body
    assert entry.echo_span is None


def test_submit_user_message_via_queue_keeps_raw_echo_for_plain_single_line():
    """A plain one-line message keeps the raw echo and its edit-redraw span."""
    outputs: list[str] = []
    rendered: list[str] = []
    tracked: list[str] = []

    class Target:
        def take_pending_attachments(self):
            return []

        def _track_echo_span(self, entry, echo):
            tracked.append(echo)

    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=lambda *v, **k: outputs.append(
            "".join(str(x) for x in v) + k.get("end", "")
        ),
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[Target()],
        echo_targets=[Target()],
        llm_task=object(),
        user_message="hello",
        marker="💬",
        append_markdown=rendered.append,
    )

    assert rendered == []
    assert len(outputs) == 1 and "hello" in outputs[0]
    assert len(tracked) == 1


# ── paste-burst merging (LLM_UI_PASTE_MERGE_MS) ──────────────────────────────


class BurstTarget:
    """Standalone-UI shape with attachments, an echo-span hook, and a spy on
    the merge redraw."""

    def __init__(self):
        self.outputs: list[str] = []
        self.redrawn: list[QueuedMessage] = []
        self._attachment_index = 0

    def take_pending_attachments(self):
        self._attachment_index += 1
        return [f"img-{self._attachment_index}"]

    def _track_echo_span(self, entry, echo):
        pass

    def _redraw_echo(self, entry):
        self.redrawn.append(entry)
        return True


def submit_burst(queue, target, text):
    submit_user_message_via_queue(
        append_to_output=target.outputs.append,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[target],
        echo_targets=[target],
        llm_task=object(),
        user_message=text,
        marker="💬",
    )


def test_submit_via_queue_merges_paste_burst_into_one_queued_message(monkeypatch):
    """Lines a terminal split into per-line Enter submits join a single turn."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    target = BurstTarget()
    queue = MessageQueue()

    submit_burst(queue, target, "git status")
    submit_burst(queue, target, "git add .")
    submit_burst(queue, target, "git commit")

    assert queue.qsize() == 1
    entry = queue.peek_latest()
    assert entry.text == "git status\ngit add .\ngit commit"
    assert entry.attachments == ["img-1", "img-2", "img-3"]
    assert entry.submitted_at is not None
    # Only the opening line is echoed; merged lines redraw that echo in place
    # instead of each writing their own.
    assert len(target.outputs) == 1
    assert target.redrawn == [entry, entry]


def test_submit_via_queue_does_not_merge_past_the_burst_window():
    """A message older than the window starts its own turn — the queue keeps
    both entries and the LLM sees two messages."""
    target = BurstTarget()
    queue = MessageQueue()

    submit_burst(queue, target, "first")
    # Expire the queued message beyond the (default 100ms) merge window.
    queue.peek_latest().submitted_at = datetime.now() - timedelta(seconds=11)
    submit_burst(queue, target, "second")

    assert queue.qsize() == 2
    assert queue.peek_latest().text == "second"
    assert len(target.outputs) == 2


def test_submit_via_queue_partial_burst_merges_only_while_fresh(monkeypatch):
    """A burst merges; a pause long enough to leave the window then splits —
    the rolling `submitted_at` keeps a long paste together but lets a pause
    start a new message."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 10_000, raising=False)
    target = BurstTarget()
    queue = MessageQueue()

    submit_burst(queue, target, "line one")
    submit_burst(queue, target, "line two")
    # A pause that outlives the window ends the burst.
    queue.peek_latest().submitted_at = datetime.now() - timedelta(seconds=11)
    submit_burst(queue, target, "later")

    assert queue.qsize() == 2
    newest = queue.latest_editable()
    older = queue.editable_before(newest)
    assert newest.text == "later"
    assert older.text == "line one\nline two"


def test_submit_via_queue_zero_window_disables_merging(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 0, raising=False)
    target = BurstTarget()
    queue = MessageQueue()

    submit_burst(queue, target, "one")
    submit_burst(queue, target, "two")

    assert queue.qsize() == 2
    assert len(target.outputs) == 2


def test_submit_user_message_via_queue_echoes_a_steered_live_run_message():
    """A message steered into a live run never reaches the queue, so the shared
    echo below the steer would not run for it — it must be echoed explicitly or
    the user's line disappears from the UI while the model still receives it."""
    run_context = MagicMock()
    outputs: list[str] = []

    submit_user_message_via_queue(
        append_to_output=outputs.append,
        active_run_context=run_context,
        stream_ai_response=_stub_stream_ai_response,
        queue=MessageQueue(),
        attachment_sources=[],
        echo_targets=[],
        llm_task=object(),
        user_message="steer me",
        marker="💬",
    )

    run_context.enqueue.assert_called_once_with("steer me", priority="asap")
    assert len(outputs) == 1
    assert "💬" in outputs[0] and "steer me" in outputs[0]


def test_submit_via_queue_does_not_merge_across_a_queued_exec_job(monkeypatch):
    """A queued `/exec` job is a merge barrier: a burst line after it must not
    fold into the older editable message (which would move the line ahead of
    the job and change execution order)."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    target = BurstTarget()
    queue = MessageQueue()

    submit_burst(queue, target, "first")
    queue.put_nowait(make_entry("ls", kind="exec"))
    submit_burst(queue, target, "second")

    assert queue.qsize() == 3
    second = queue.peek_latest()
    assert second is not None
    assert second.is_editable and second.text == "second"
    first = queue.editable_before(second)
    assert first is not None and first.text == "first"
    assert len(target.outputs) == 2


def test_submit_via_queue_falls_back_to_echo_when_merge_cannot_redraw(monkeypatch):
    """A UI with no output buffer to splice (a no-op `_redraw_echo`) still shows
    each merged paste line as an ordinary echo — it must not vanish."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    target = BurstTarget()
    target._redraw_echo = lambda entry: None  # bufferless UI: nothing redrawn
    queue = MessageQueue()

    submit_burst(queue, target, "git status")
    submit_burst(queue, target, "git add .")

    assert queue.qsize() == 1
    assert queue.peek_latest().text == "git status\ngit add ."
    assert len(target.outputs) == 2
    assert "git status" in target.outputs[0]
    assert "git add ." in target.outputs[1]
