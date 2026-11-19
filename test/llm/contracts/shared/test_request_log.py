"""A row per model request: what a turn spent, read where it was made.

The summed line (`usage_log`) answers what a turn cost. These rows answer what
it was spent on: which request, why it was sent, and a digest of the prompt it
sent — the three the sum cannot hold (board 0003 §4).
"""

import copy
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage, RunUsage

from zrb.config.config import CFG
from zrb.llm.contracts.shared.request_log import (
    REASON_FOLLOW_UP,
    REASON_OPENING,
    REASON_RETRY,
    RequestRecord,
    read_requests,
    record_requests,
    record_round_requests,
)
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.agent.run.turn_cursor import TurnCursor
from zrb.llm.contracts.config.limiter import LLMLimiter
from zrb.llm.contracts.shared.usage_log import read_records

JANUARY = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """Point both logs at a temporary directory rather than the user's home."""
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def _round(prompt: str = "Hi", answer: str = "done", instructions: str | None = None) -> list:
    """One round that made two requests: a tool call, then the answer."""
    return [
        ModelRequest(parts=[UserPromptPart(content=prompt)], instructions=instructions),
        ModelResponse(
            parts=[ToolCallPart(tool_name="read", args={})],
            usage=RequestUsage(input_tokens=100, output_tokens=5),
            model_name="test-model",
        ),
        ModelRequest(parts=[ToolReturnPart(tool_name="read", content="ok")]),
        ModelResponse(
            parts=[TextPart(content=answer)],
            usage=RequestUsage(
                input_tokens=140, output_tokens=7, cache_read_tokens=120
            ),
            model_name="test-model",
        ),
    ]


def test_a_round_writes_one_row_per_request(usage_dir):
    """Two requests in a round are two rows, and the second is a follow-up."""
    cursor = TurnCursor(history=[])

    record_round_requests(cursor, _round(), REASON_OPENING)

    first, second = read_requests()
    assert [first.index, second.index] == [0, 1]
    assert first.reason == REASON_OPENING
    assert second.reason == REASON_FOLLOW_UP
    assert first.input_tokens == 100
    assert second.input_tokens == 140
    assert second.cache_read_tokens == 120
    assert first.prompt_messages == 1
    assert second.prompt_messages == 3
    assert first.turn == cursor.turn_id == second.turn


def test_the_rows_of_one_turn_are_numbered_across_rounds(usage_dir):
    """A retried round carries on the numbering rather than restarting it."""
    cursor = TurnCursor(history=[])

    record_round_requests(cursor, _round(), REASON_OPENING)
    record_round_requests(cursor, _round(), REASON_RETRY)

    rows = read_requests()
    assert [row.index for row in rows] == [0, 1, 2, 3]
    assert [row.reason for row in rows] == [
        REASON_OPENING,
        REASON_FOLLOW_UP,
        REASON_RETRY,
        REASON_FOLLOW_UP,
    ]


def test_a_resend_that_rebuilds_its_request_reads_the_same_digest(usage_dir):
    """The fact the digest exists for: one prompt sent twice, whatever the cache did.

    A retry sends the stored history again and makes its own request message,
    which is stamped when it is made. The stamp is bookkeeping no provider
    receives, so the two sendings must read as one prompt — reading it as a
    change would make every resend look like a rewrite of zrb's, which is the
    wrong answer to the question this row is for.
    """
    cursor = TurnCursor(history=[])
    sent = _round()
    resent = [ModelRequest(parts=[UserPromptPart(content="Hi")])] + sent[1:]

    record_round_requests(cursor, sent, REASON_OPENING)
    record_round_requests(cursor, resent, REASON_RETRY)

    rows = {row.index: row for row in read_requests()}
    assert rows[0].prompt_messages == rows[2].prompt_messages
    assert rows[0].prompt_hash == rows[2].prompt_hash


def test_metadata_no_provider_receives_does_not_move_the_digest(usage_dir):
    """The strip, proved on its own: same words, different bookkeeping.

    A message rebuilt with new ids, timestamps and metadata — and a response
    that cost a different number of tokens — is the same prompt as far as the
    provider is concerned, so it must be the same digest here.
    """
    cursor = TurnCursor(history=[])
    plain = _round()
    decorated = copy.deepcopy(plain)
    for message in decorated:
        message.metadata = {"seen": "twice"}
        for part in message.parts:
            part.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    decorated[1].usage = RequestUsage(input_tokens=9_999, output_tokens=1)
    decorated[1].model_name = "another-model"

    record_round_requests(cursor, plain, REASON_OPENING)
    record_round_requests(cursor, decorated, REASON_RETRY)

    rows = {row.index: row for row in read_requests()}
    assert rows[0].prompt_hash == rows[2].prompt_hash
    # The second request of each round carries the response it followed, so its
    # prompt covers the response's own fields as well.
    assert rows[1].prompt_hash == rows[3].prompt_hash


def test_a_rewritten_prefix_changes_the_digest_at_the_same_length(usage_dir):
    """The other half: same number of messages, different words, different digest.

    This is the shape of a prefix zrb rewrote in place, which moves the digest
    while leaving the count alone — so a reader can tell it from ordinary growth.
    """
    cursor = TurnCursor(history=[])

    record_round_requests(cursor, _round(prompt="Hi"), REASON_OPENING)
    record_round_requests(cursor, _round(prompt="Hello"), REASON_RETRY)

    rows = {row.index: row for row in read_requests()}
    assert rows[0].prompt_messages == rows[2].prompt_messages == 1
    assert rows[0].prompt_hash != rows[2].prompt_hash


def test_the_prompt_digest_covers_the_history_it_was_sent_with(usage_dir):
    """Two rounds with the same new messages are still different prompts when
    the history underneath them differs — and the length says which it was."""
    cursor = TurnCursor(history=[])
    record_round_requests(cursor, _round(), REASON_OPENING)

    cursor.begin_round(_round(prompt="Earlier", answer="earlier answer"))
    record_round_requests(cursor, _round(), REASON_RETRY)

    rows = {row.index: row for row in read_requests()}
    assert rows[2].prompt_messages == rows[0].prompt_messages + 4
    assert rows[2].prompt_hash != rows[0].prompt_hash


def test_the_digest_moves_when_the_instructions_change(usage_dir):
    """The instructions ride on the request message, so they are hashed too.

    A system prompt that changed is a prompt the cache cannot match, at the same
    length — which is the other in-place rewrite a reader has to be able to see.
    """
    cursor = TurnCursor(history=[])

    record_round_requests(cursor, _round(instructions="be brief"), REASON_OPENING)
    record_round_requests(cursor, _round(instructions="be thorough"), REASON_RETRY)

    rows = {row.index: row for row in read_requests()}
    assert rows[0].prompt_messages == rows[2].prompt_messages == 1
    assert rows[0].prompt_hash != rows[2].prompt_hash


def test_a_row_keeps_the_conversation_it_belongs_to(usage_dir):
    """A conversation is renamed after its first turn, so the row keys on the
    stable name — the same identity the summed log uses."""
    record_requests(
        [
            RequestRecord(
                timestamp=JANUARY,
                model="test-model",
                session="bold-arch-1234-greetings",
                component="main_agent",
                reason=REASON_OPENING,
                turn="abc",
                index=0,
                input_tokens=10,
                output_tokens=2,
                cache_read_tokens=0,
                cache_write_tokens=0,
                reasoning_tokens=0,
                prompt_messages=1,
                prompt_hash="0123456789ab",
            )
        ]
    )

    (row,) = read_requests(session_key="bold-arch-1234")
    assert row.session == "bold-arch-1234-greetings"
    assert row.prompt_hash == "0123456789ab"
    assert read_requests(session_key="another-conversation") == []


def test_the_two_logs_share_a_directory_without_mixing(usage_dir):
    """One directory, two prefixes: reading the summed log never meets a request
    row, and a reader of either finds its own files."""
    record_requests([_row()])

    assert (usage_dir / "request-2026-01.jsonl").exists()
    assert read_requests() != []
    assert read_records() == []


def test_a_log_that_cannot_be_written_costs_only_its_rows(usage_dir, monkeypatch):
    """A read-only home must not fail the turn that produced the numbers."""
    blocked = usage_dir / "blocked"
    blocked.write_text("not a directory")
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(blocked), raising=False)

    assert record_requests([_row()]) == []


def test_a_run_that_cannot_list_its_messages_writes_no_request_rows(usage_dir):
    """No rows is better than a guessed one: a mocked or failed run sent nothing."""
    cursor = TurnCursor(history=[])

    record_round_requests(cursor, MagicMock(), REASON_OPENING)

    assert read_requests() == []


@pytest.mark.asyncio
async def test_a_turn_writes_its_id_on_both_logs(usage_dir):
    """The join is exact: the summed line and the rows under it name one turn."""
    messages = _round()
    result = MagicMock()
    result.output = "done"
    result.all_messages.return_value = messages
    result.new_messages.return_value = messages
    result.usage = RunUsage(input_tokens=240, output_tokens=12, requests=2)
    result.response.model_name = "test-model"
    agent = MagicMock()
    agent.run = _fake_run_from(result)

    await run_agent(agent=agent, message="Hi", message_history=[], limiter=LLMLimiter())

    (turn,) = read_records()
    rows = read_requests()
    assert len(rows) == 2
    assert turn.turn
    assert {row.turn for row in rows} == {turn.turn}
    assert rows[0].reason == REASON_OPENING


def _row(**changes) -> RequestRecord:
    """A minimal row, with any field a test cares about replaced."""
    base = dict(
        timestamp=JANUARY,
        model="test-model",
        session="",
        component="main_agent",
        reason=REASON_OPENING,
        turn="abc",
        index=0,
        input_tokens=10,
        output_tokens=2,
        cache_read_tokens=0,
        cache_write_tokens=0,
        reasoning_tokens=0,
        prompt_messages=1,
        prompt_hash="0123456789ab",
    )
    return RequestRecord(**{**base, **changes})


def _fake_run_from(result):
    """An `agent.run` that yields *result*, the way the real stream handler does.

    Mirrors the fake in `test_usage_log`: the trailing `AgentRunResultEvent` is
    stripped out of the stream and returned as ``agent.run()``'s value.
    """

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        seen = []

        async def events():
            yield AgentRunResultEvent(result=result)
            seen.append(result)

        if handler is not None:
            await handler(MagicMock(), events())
        return seen[0] if seen else None

    return fake_run
