"""A background command's wake-up shares the user's queue, not the user's rights.

It queues like a typed message, so a running turn reads it at its next model
request and an idle session runs it as a turn. It differs in two ways: it never
cuts the voice, and a session can only be woken so many times in a row.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.input_source import BACKGROUND_INPUT, KEYBOARD_INPUT
from zrb.llm.ui.base.message_queue import MessageQueue, submit_user_message_via_queue


async def _stub_stream_ai_response(llm_task, text, attachments):
    pass


def _submit(queue, message, source, notices=None):
    submit_user_message_via_queue(
        append_to_output=lambda *values, **_k: (
            notices.append(" ".join(str(v) for v in values))
            if notices is not None
            else None
        ),
        stream_ai_response=_stub_stream_ai_response,
        queue=queue,
        attachment_sources=[],
        echo_targets=[],
        llm_task=object(),
        user_message=message,
        marker="💬",
        source=source,
    )


@pytest.fixture
def hushed(monkeypatch):
    """The calls made to quiet the voice."""
    calls = []
    monkeypatch.setattr(
        "zrb.llm.speech.feature.interrupt_speech", lambda: calls.append(1)
    )
    return calls


def test_a_wake_up_queues_like_a_typed_message(hushed):
    queue = MessageQueue()

    _submit(queue, "[Background process x finished]", BACKGROUND_INPUT)

    entry = queue.peek_latest()
    assert entry is not None
    assert entry.text == "[Background process x finished]"
    assert entry.source is not None
    assert entry.source.channel == "background process"


def test_a_wake_up_does_not_cut_the_voice(hushed):
    """The user has not moved on: a command ending is no reason to stop a reply."""
    queue = MessageQueue()

    _submit(queue, "[Background process x finished]", BACKGROUND_INPUT)
    assert hushed == []

    _submit(queue, "next question", KEYBOARD_INPUT)
    assert hushed == [1]


def test_wake_ups_stop_at_the_limit_until_the_user_writes(monkeypatch, hushed):
    monkeypatch.setattr(CFG, "LLM_BACKGROUND_WAKE_MAX_CONSECUTIVE", 2)
    queue = MessageQueue()
    notices: list[str] = []

    for number in range(3):
        _submit(queue, f"wake {number}", BACKGROUND_INPUT, notices)

    assert [entry.text for entry in queue.pending()] == ["wake 0", "wake 1"]
    (notice,) = [text for text in notices if "wake-ups in a row" in text]
    assert "2 background wake-ups in a row" in notice

    _submit(queue, "I am back", KEYBOARD_INPUT)
    _submit(queue, "wake 3", BACKGROUND_INPUT)

    assert queue.pending()[-1].text == "wake 3"


def test_a_limit_of_zero_removes_the_limit(monkeypatch, hushed):
    monkeypatch.setattr(CFG, "LLM_BACKGROUND_WAKE_MAX_CONSECUTIVE", 0)
    queue = MessageQueue()

    for number in range(20):
        _submit(queue, f"wake {number}", BACKGROUND_INPUT)

    assert queue.qsize() == 20


def test_words_that_are_not_the_users_do_not_refill_the_allowance(monkeypatch, hushed):
    """A sub-agent's message (source None) is not the user writing."""
    monkeypatch.setattr(CFG, "LLM_BACKGROUND_WAKE_MAX_CONSECUTIVE", 1)
    queue = MessageQueue()
    _submit(queue, "wake 0", BACKGROUND_INPUT)

    _submit(queue, "from a sub-agent", None)
    _submit(queue, "wake 1", BACKGROUND_INPUT)

    assert [entry.text for entry in queue.pending()] == ["wake 0", "from a sub-agent"]
