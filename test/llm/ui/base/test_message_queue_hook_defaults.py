"""`submit_user_message_via_queue` against UIs that never implemented a hook."""

from zrb.llm.ui.base.message_queue import MessageQueue, submit_user_message_via_queue
from zrb.llm.ui_fallback.std_ui import StdUI


def _stub_stream_ai_response(llm_task, text, attachments):
    pass


def test_a_markdownish_echo_reaches_a_ui_that_never_tracks_rendered_echoes():
    """The declared `track_rendered_echo` default is a no-op, so a UI without a
    rendered-echo span still queues the message and claims no span."""
    from zrb.llm.ui_fallback.std_ui import StdUI

    queue = MessageQueue()
    body = "## Plan\n\n- a\n- b"
    target = StdUI()

    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[target],
        echo_targets=[target],
        llm_task=object(),
        user_message=body,
        marker="\U0001f4ac",
        append_markdown=lambda _text: None,
    )

    entry = queue.peek_latest()
    assert entry.text == body
    assert entry.echo_spans == {}
