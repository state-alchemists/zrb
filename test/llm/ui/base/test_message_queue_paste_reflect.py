"""How a merged paste line is reflected on the echo targets.

How a paste burst folds into one queued message is covered by
`test_message_queue_paste_merge.py`; this file covers what each target sees:
the line spliced in place where possible, echoed to a bufferless child alone,
kept visible when a child's redraw fails, rendered whole when the combined
text turns Markdown (with a verbatim fallback for targets that cannot splice),
and never duplicated across a MultiUI's shared `QueuedMessage` echo-span state.
"""

from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.ui.base.message_queue import (
    EchoSpan,
    MessageQueue,
    QueuedMessage,
    submit_user_message_via_queue,
)
from zrb.llm.ui.base.user_echo import should_render_user_markdown


def _stub_stream_ai_response(llm_task, text, attachments):
    pass


class BurstTarget:
    """Standalone-UI shape with attachments, an echo-span hook, a spy on the
    merge redraw, and its own output sink.

    `can_redraw=False` models a bufferless UI whose `redraw_echo` is a no-op,
    so a merged line is echoed through the target's own `append_to_output`.
    `redraw_error` makes `redraw_echo` raise, modelling a child whose buffer
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

    def track_echo_span(self, entry, echo):
        pass

    def redraw_echo(self, entry):
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


class SpliceableTarget:
    """Spliceable shape mirroring the default TUI's per-buffer echo bookkeeping:
    an own output buffer and an own echo span keyed by `self`, spliced in place.

    `track_echo_span`/`redraw_echo` reproduce how `UIMessageEditing` records
    and splices the echoed line in the real default UI, so this exercises the
    shared-`QueuedMessage` span state instead of a spy that never reads it.
    `append_to_output` matches the real writer's trailing newline — the echoed
    line already ends with one, and the writer appends a separator after it —
    so a span is only usable if its recording survives that extra blank line.
    `redraw_echo` picks its body the way the real one does — a render of the
    whole entry text when it carries a Markdown construct (stood in for by
    uppercasing), the raw line otherwise — so a merge and a later edit draw
    the same thing.
    """

    def __init__(self):
        self.buffer = ""
        self.splices = 0
        self.rendered: list[str] = []

    def append_to_output(self, *values, **kwargs):
        self.buffer += "".join(str(v) for v in values) + kwargs.get("end", "\n")

    def append_markdown(self, markdown_text):
        self.rendered.append(markdown_text)

    def take_pending_attachments(self):
        return []

    def track_echo_span(self, entry, echo):
        if self.buffer.endswith(echo) or self.buffer.endswith(echo + "\n"):
            index = self.buffer.rfind(echo)
            if index < 0:
                return
            entry.echo_spans[self] = EchoSpan(
                start=index,
                end=index + len(echo),
                text=echo,
            )

    def _resolve_span(self, entry):
        span = entry.echo_spans.get(self)
        if span is None:
            return None
        if span.end > len(self.buffer) or (
            span.text and self.buffer[span.start : span.end] != span.text
        ):
            del entry.echo_spans[self]
            return None
        return span

    def _splice_echo(self, entry, body):
        span = self._resolve_span(entry)
        if span is None:
            return None
        marker = entry.echo_marker or "💬"
        ts = entry.echo_timestamp or "10:00"
        echo = f"\n{marker} {ts} >> {body}\n"
        self.buffer = self.buffer[: span.start] + echo + self.buffer[span.end :]
        entry.echo_spans[self] = EchoSpan(
            start=span.start,
            end=span.start + len(echo),
            text=echo,
        )
        self.splices += 1
        return echo

    def redraw_echo(self, entry):
        if should_render_user_markdown(entry.text):
            return self._splice_echo(entry, entry.text.upper())
        return self._splice_echo(entry, entry.text.strip())


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


def test_submit_via_queue_falls_back_to_echo_when_merge_cannot_redraw(monkeypatch):
    """A UI with no output buffer to splice (a no-op `redraw_echo`) still shows
    each merged paste line as an ordinary echo — it must not vanish."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
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
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
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


def test_submit_via_queue_replaces_echo_with_full_rendered_merged_markdown(monkeypatch):
    """A burst whose combined text turns Markdown is shown on a spliceable TUI
    as the whole combined message rendered in place of the plain opening echo.
    Rendering only the newest line would leave a multi-line construct half on
    screen (e.g. a fenced code block's closing fence), so the target must
    render the full message; the re-tracked span keeps a later edit able to
    rewrite the display."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
    target = SpliceableTarget()
    queue = MessageQueue()

    def submit(text):
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
            append_markdown=target.append_markdown,
        )

    submit("hello")
    submit("- item")

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "hello\n- item"
    assert target.splices == 1
    # The plain opening echo is gone, replaced by a render of the full
    # combined message (the double's stand-in renderer uppercases it) — the
    # merged line alone is never what gets drawn.
    assert "hello" not in target.buffer
    assert ">> HELLO\n- ITEM\n" in target.buffer
    # The echo span survives, re-tracked over the rendered replacement, so a
    # later edit can still rewrite the displayed message.
    span = entry.echo_spans[target]
    assert span.text.startswith("\n💬 ")
    assert span.text.endswith(">> HELLO\n- ITEM\n")


def test_submit_via_queue_echoes_merged_markdown_line_verbatim_without_splice(
    monkeypatch,
):
    """A target with no echo to splice must never render just the new line of
    a combined message that turned Markdown — a bare `- item` or a lone fence
    is meaningless without the rest of the message. The line lands verbatim,
    so nothing is partial and nothing disappears."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
    outputs: list[str] = []
    rendered: list[str] = []

    class MarkdownBufferlessTarget:
        def append_to_output(self, *values, **kwargs):
            outputs.append("".join(str(v) for v in values) + kwargs.get("end", ""))

        def append_markdown(self, markdown_text):
            rendered.append(markdown_text)

        def take_pending_attachments(self):
            return []

        def track_echo_span(self, entry, echo):
            pass

        def redraw_echo(self, entry):
            return None

    target = MarkdownBufferlessTarget()
    queue = MessageQueue()

    def submit(text):
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
            append_markdown=target.append_markdown,
        )

    submit("hello")
    submit("- item")

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "hello\n- item"
    # Nothing rendered — a view of just `- item` would be a fragment of a
    # Markdown list with no context; the merged line echoed verbatim instead.
    assert rendered == []
    assert len(outputs) == 2
    assert "hello" in outputs[0]
    assert "- item" in outputs[1]


def test_submit_via_queue_survives_a_child_redraw_failure(monkeypatch):
    """A child whose `redraw_echo` raises mid-merge must not crash the
    submission or stop the other targets — the failure is logged, the broken
    child falls back to an ordinary echo, and a healthy child still redraws."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
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


def test_submit_via_queue_merge_keeps_each_childs_own_echo_span(monkeypatch):
    """Two spliceable children (the real TUI shape) each splice a merged paste
    line into their own buffer exactly once. A shared scalar span on the
    `QueuedMessage` would make the second child see the first child's
    just-rewritten span as stale, fall back to an echo, and duplicate the
    line."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
    child_a = SpliceableTarget()
    child_b = SpliceableTarget()
    queue = MessageQueue()

    def broadcast(*values, **kwargs):
        text = "".join(str(v) for v in values) + kwargs.get("end", "")
        child_a.buffer += text
        child_b.buffer += text

    for message in ("git status", "git add ."):
        submit_user_message_via_queue(
            append_to_output=broadcast,
            active_run_context=None,
            stream_ai_response=_stub_stream_ai_response,
            queue=queue,
            attachment_sources=[child_a, child_b],
            echo_targets=[child_a, child_b],
            llm_task=object(),
            user_message=message,
            marker="💬",
        )

    entry = queue.peek_latest()
    assert queue.qsize() == 1
    assert entry.text == "git status\ngit add ."
    # Both children spliced the merged line in place, each into its own buffer,
    # exactly once — no duplicate echo anywhere.
    assert child_a.splices == 1
    assert child_b.splices == 1
    assert child_a.buffer.count("git add .") == 1
    assert child_b.buffer.count("git add .") == 1
    # Each child still tracks its own live span of the merged echo.
    assert len(entry.echo_spans) == 2
    assert child_a in entry.echo_spans
    assert child_b in entry.echo_spans


def test_submit_via_queue_merge_echoes_line_when_attachment_collection_fails(
    monkeypatch,
):
    """A burst line whose attachment source raises aborts both the merge and
    the per-target reflection — the line's only trace. The echo must still be
    emitted so the submitted input stays visible on the failure."""
    monkeypatch.setattr(CFG, "LLM_UI_PASTE_MERGE_WINDOW", 60_000, raising=False)
    outputs: list[str] = []
    tui = BurstTarget()
    queue = MessageQueue()

    def broadcast(*values, **kwargs):
        outputs.append("".join(str(v) for v in values) + kwargs.get("end", ""))

    submit_user_message_via_queue(
        append_to_output=broadcast,
        active_run_context=None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[tui],
        echo_targets=[tui],
        llm_task=object(),
        user_message="git status",
        marker="💬",
    )

    class BrokenSource:
        def take_pending_attachments(self):
            raise RuntimeError("camera unavailable")

    with pytest.raises(RuntimeError, match="camera unavailable"):
        submit_user_message_via_queue(
            append_to_output=broadcast,
            active_run_context=None,
            stream_ai_response=_stub_stream_ai_response,
            queue=queue,
            attachment_sources=[BrokenSource()],
            echo_targets=[tui],
            llm_task=object(),
            user_message="git add .",
            marker="💬",
        )

    # The paste was not merged (collection failed) and its line is still on
    # screen — the echo was emitted before the failure propagated.
    assert queue.qsize() == 1
    assert queue.peek_latest().text == "git status"
    assert len(outputs) == 2
    assert "git status" in outputs[0]
    assert "git add ." in outputs[1]
