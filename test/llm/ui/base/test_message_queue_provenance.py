"""What a queued message tells the model about *when* it arrived.

A turn's own words carry no time. The queue knows when the previous turn
finished, so the gap can be measured where the message is submitted instead of
being guessed from the transcript.
"""

import asyncio
import time

import pytest

from zrb.llm.input_source import KEYBOARD_INPUT
from zrb.llm.ui.base.message_queue import (
    MessageQueue,
    QueuedMessage,
    _run_queued_message,
    submit_user_message_via_queue,
)


async def _noop():
    pass


async def _stub_stream_ai_response(llm_task, text, attachments):
    pass


def _submit(queue, message="hello"):
    submit_user_message_via_queue(
        append_to_output=lambda *_a, **_k: None,
        stream_ai_response=_stub_stream_ai_response,
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


@pytest.mark.asyncio
async def test_a_finished_turn_records_when_it_finished():
    queue = MessageQueue()
    ran = asyncio.Event()

    async def stream_ai_response(llm_task, text, attachments):
        ran.set()

    entry = QueuedMessage(text="hello", attachments=[], kind="message", run=_noop)
    await _run_queued_message(stream_ai_response, object(), entry, queue)

    assert ran.is_set()
    assert queue.last_turn_finished_at is not None
