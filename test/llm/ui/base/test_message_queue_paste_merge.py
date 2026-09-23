"""Paste-burst merging under `CFG.LLM_UI_PASTE_MERGE_MS`.

Lines a terminal without bracketed paste splits into per-line Enter submits
are coalesced back into one queued message. This file covers the merge
decision — the burst window, its rolling refresh, `0` disabling it, and the
queued `/exec` barrier. How a merged line is reflected on the echo targets
lives in `test_message_queue_paste_reflect.py`.
"""

from datetime import datetime, timedelta

from zrb.config.config import CFG
from zrb.llm.ui.base.message_queue import (
    MessageQueue,
    QueuedMessage,
    submit_user_message_via_queue,
)


def make_entry(text, kind="message"):
    async def run():
        pass

    return QueuedMessage(text=text, attachments=[], kind=kind, run=run)


def _stub_stream_ai_response(llm_task, text, attachments):
    pass


class BurstTarget:
    """Standalone-UI shape with attachments, an echo-span hook, a spy on the
    merge redraw, and its own output sink.

    `can_redraw=False` models a bufferless UI whose `_redraw_echo` is a no-op,
    so a merged line is echoed through the target's own `append_to_output`.
    `redraw_error` makes `_redraw_echo` raise, modelling a child whose buffer
    went away mid-merge.
    """

    def __init__(self, can_redraw=True, redraw_error=None):
        self.outputs: list[str] = []
        self.redrawn: list[QueuedMessage] = []
        self._attachment_index = 0
        self.can_redraw = can_redraw
        self.redraw_error = redraw_error

    def append_to_output(self, *values, **kwargs):
        self.outputs.append("".join(str(v) for v in values) + kwargs.get("end", ""))

    def take_pending_attachments(self):
        self._attachment_index += 1
        return [f"img-{self._attachment_index}"]

    def _track_echo_span(self, entry, echo):
        pass

    def _redraw_echo(self, entry):
        if self.redraw_error is not None:
            raise self.redraw_error
        if not self.can_redraw:
            return None
        self.redrawn.append(entry)
        return "rewritten echo"


def submit_burst(queue, target, text):
    submit_user_message_via_queue(
        append_to_output=target.append_to_output,
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