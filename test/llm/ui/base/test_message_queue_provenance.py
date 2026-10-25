"""What a queued message tells the model about *when* it arrived.

A turn's own words carry no time. The queue knows when the previous turn
finished, so the gap can be measured where the message is submitted instead of
being guessed from the transcript.
"""

import asyncio
import time

import pytest

from zrb.llm.input_source import KEYBOARD_INPUT
from zrb.llm.ui.base.message_queue import MessageQueue, submit_user_message_via_queue


async def _stub_stream_ai_response(llm_task, text, attachments):
    pass


def _submit(queue, message="hello", stream=_stub_stream_ai_response):
    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        stream_ai_response=stream,
        queue=queue,
        attachment_sources=[],
        echo_targets=[],
        llm_task=object(),
        user_message=message,
        marker="💬",
    )


def test_a_submitted_message_reports_how_long_the_chat_was_quiet():
    """Without this a reply to a sentence just read and a reply to one written
    an hour ago reach the model as the same act."""
    queue = MessageQueue()
    queue.last_turn_finished_at = time.monotonic() - 194

    _submit(queue, "still there?")

    entry = queue.peek_latest()
    assert entry is not None
    assert entry.source is not None
    assert entry.source.idle_seconds == pytest.approx(194, abs=2)
    assert "after 3m14s of silence" in entry.source.render()


def test_the_first_message_of_a_session_carries_no_silence():
    """Nothing has finished yet, so the source stays the untouched default and
    the paste-merge rule that compares it to `KEYBOARD_INPUT` keeps working."""
    queue = MessageQueue()

    _submit(queue)

    entry = queue.peek_latest()
    assert entry is not None
    assert entry.source == KEYBOARD_INPUT


def test_a_message_sent_during_a_running_turn_reports_no_idle_gap():
    """The end of the *previous* turn is the wrong yardstick while another turn
    is running: the model has just seen this conversation, not an hour of
    silence, and "after 1h of silence" would be a lie it acts on."""
    queue = MessageQueue()
    queue.last_turn_finished_at = time.monotonic() - 3600
    queue.turn_started_at = time.monotonic() - 5

    _submit(queue, "and another thing")

    entry = queue.peek_latest()
    assert entry is not None
    assert entry.source is not None
    assert entry.source.idle_seconds == 0
    assert "silence" not in entry.source.render()


@pytest.mark.asyncio
async def test_a_finished_turn_records_when_it_finished():
    queue = MessageQueue()
    ran = asyncio.Event()

    async def stream_ai_response(llm_task, text, attachments):
        assert queue.turn_started_at is not None  # marked while it runs
        ran.set()

    _submit(queue, stream=stream_ai_response)
    entry = queue.peek_latest()
    assert entry is not None
    await entry.run()

    assert ran.is_set()
    assert queue.turn_started_at is None
    assert queue.last_turn_finished_at is not None
