"""Paste-burst merging under `CFG.LLM_UI_PASTE_MERGE_MS`.

Lines a terminal without bracketed paste splits into per-line Enter submits
are coalesced back into one queued message. This file covers the burst window,
its barriers (a queued `/exec` job), and how a merged line is reflected on the
echo targets — spliced in place where possible, echoed to a bufferless child
alone, kept visible when a child's redraw fails, and rendered through the
markdown path when the combined text turns Markdown.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

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
    target = BurstTarget(can_redraw=False)
    queue = MessageQueue()

    submit_burst(queue, target, "git status")
    submit_burst(queue, target, "git add .")

    assert queue.qsize() == 1
    assert queue.peek_latest().text == "git status\ngit add ."
    assert len(target.outputs) == 2
    assert "git status" in target.outputs[0]
    assert "git add ." in target.outputs[1]


def test_submit_via_queue_reflects_merged_line_per_multiui_child(monkeypatch):
    """A MultiUI mixing spliceable (TUI) and bufferless (Telegram) children: the
    merged line is redrawn in place for the former and echoed to the latter
    alone — never broadcast a second copy to the child that redrew."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    tui = BurstTarget()
    telegram = BurstTarget(can_redraw=False)
    queue = MessageQueue()

    def broadcast(*values, **kwargs):
        text = "".join(str(v) for v in values) + kwargs.get("end", "")
        tui.outputs.append(text)
        telegram.outputs.append(text)

    submit_user_message_via_queue(
        append_to_output=broadcast,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[tui, telegram],
        echo_targets=[tui, telegram],
        llm_task=object(),
        user_message="git status",
        marker="💬",
    )
    submit_user_message_via_queue(
        append_to_output=broadcast,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[tui, telegram],
        echo_targets=[tui, telegram],
        llm_task=object(),
        user_message="git add .",
        marker="💬",
    )

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "git status\ngit add ."
    assert tui.redrawn == [entry]
    # The TUI got the opening line once and then a splice, never a copy.
    assert len(tui.outputs) == 1
    # The bufferless child got the opening line via the broadcast and the
    # merged line through its own echo — nothing disappeared.
    assert len(telegram.outputs) == 2
    assert "git status" in telegram.outputs[0]
    assert "git add ." in telegram.outputs[1]


def test_submit_via_queue_renders_merged_markdown_via_echo_path(monkeypatch):
    """A burst whose combined text turns Markdown (e.g. `- item` after `hello`)
    drops the plain echo's span and echoes the merged line through the render
    path — no literal Markdown splice, no duplicate of the full combined
    message, and nothing left behind for a later edit to re-splice."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    outputs: list[str] = []
    rendered: list[str] = []
    redrawn: list[QueuedMessage] = []

    class MarkdownTarget:
        def append_to_output(self, *values, **kwargs):
            outputs.append("".join(str(v) for v in values) + kwargs.get("end", ""))

        def append_markdown(self, markdown_text):
            rendered.append(markdown_text)

        def take_pending_attachments(self):
            return []

        def _track_echo_span(self, entry, echo):
            pass

        def _redraw_echo(self, entry):
            redrawn.append(entry)
            return None

    target = MarkdownTarget()
    queue = MessageQueue()

    submit_user_message_via_queue(
        append_to_output=target.append_to_output,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[target],
        echo_targets=[target],
        llm_task=object(),
        user_message="hello",
        marker="💬",
        append_markdown=target.append_markdown,
    )
    submit_user_message_via_queue(
        append_to_output=target.append_to_output,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[target],
        echo_targets=[target],
        llm_task=object(),
        user_message="- item",
        marker="💬",
        append_markdown=target.append_markdown,
    )

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "hello\n- item"
    # The plain echo's span is dropped, so no literal splice is possible and a
    # later edit has nothing stale to redraw.
    assert entry.echo_span is None
    # Only the merged line is rendered — the combined message is never echoed a
    # second time, so `hello` appears once and there is no duplicate block.
    assert rendered == ["- item"]
    assert redrawn == [entry]
    # The plain opening line was echoed raw; the merged line went through the
    # target's own header + markdown path.
    assert sum("hello" in o for o in outputs) == 1
    assert any(o.endswith(">> ") for o in outputs)


def test_submit_via_queue_survives_a_child_redraw_failure(monkeypatch):
    """A child whose `_redraw_echo` raises mid-merge must not crash the
    submission or stop the other targets — the failure is logged, the broken
    child falls back to an ordinary echo, and a healthy child still redraws."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_MS", 60_000, raising=False)
    broken = BurstTarget(redraw_error=RuntimeError("buffer closed"))
    healthy = BurstTarget()
    queue = MessageQueue()

    def broadcast(*values, **kwargs):
        text = "".join(str(v) for v in values) + kwargs.get("end", "")
        broken.outputs.append(text)
        healthy.outputs.append(text)

    submit_user_message_via_queue(
        append_to_output=broadcast,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[broken, healthy],
        echo_targets=[broken, healthy],
        llm_task=object(),
        user_message="git status",
        marker="💬",
    )
    submit_user_message_via_queue(
        append_to_output=broadcast,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[broken, healthy],
        echo_targets=[broken, healthy],
        llm_task=object(),
        user_message="git add .",
        marker="💬",
    )

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "git status\ngit add ."
    # The healthy target redrew the merged line in place...
    assert healthy.redrawn == [entry]
    assert len(healthy.outputs) == 1
    # ...and the broken child still got the merged line as an echo, so nothing
    # disappeared for it either.
    assert len(broken.outputs) == 2
    assert "git add ." in broken.outputs[1]