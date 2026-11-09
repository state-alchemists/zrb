"Tests for the rarely-hit branches in chunk_processor."

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.summarizer.chunk_processor import chunk_and_summarize
from zrb.llm.util.capabilities import model_capabilities

from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart


class _Limiter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return " ".join(text.split()[:max_tokens])


@pytest.mark.asyncio
async def test_empty_messages_returns_no_summaries_marker():
    """No messages → no chunks → fall through to the [No summaries] sentinel."""
    out = await chunk_and_summarize(
        messages=[],
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=100,
    )
    assert "[No summaries generated]" in out


@pytest.mark.asyncio
async def test_message_to_text_failure_falls_back_to_str():
    "If message_to_text raises, the converter falls back to str(m) and"
    with (
        patch(
            "zrb.llm.summarizer.chunk_processor.message_to_text",
            side_effect=RuntimeError("bad message shape"),
        ),
        patch(
            "zrb.llm.summarizer.chunk_processor.summarize_text_plain",
            new=AsyncMock(return_value="SUMMARY"),
        ),
    ):
        out = await chunk_and_summarize(
            messages=["msg one", "msg two"],
            agent=MagicMock(),
            limiter=_Limiter(),
            token_threshold=100,
        )
    assert "SUMMARY" in out


_TINY_MODEL = "zrb-test-tiny-window"
# Wide enough to hold a real chunk and the per-part instructions: the header
# costs about fifty tokens, so a hundred-token window asserted behaviour the
# model could not physically accept, and it went unnoticed while nothing checked
# the window at all.
_TINY_WINDOW = 400


@pytest.fixture
def tiny_window_model():
    "A registered model whose window forces more than one chunk."
    model_capabilities.register(_TINY_MODEL, context_window=_TINY_WINDOW)
    yield f"fake:{_TINY_MODEL}"
    model_capabilities.clear()


def _recording_summarizer(monkeypatch) -> list[str]:
    "Patch the summarizer seam and collect the text of every chunk it saw."
    sent: list[str] = []

    async def fake_summarize(text, agent, limiter, threshold, spent=None):
        sent.append(text)
        return "summary"

    monkeypatch.setattr(
        "zrb.llm.summarizer.chunk_processor.summarize_text_plain", fake_summarize
    )
    return sent


def _messages(words: int) -> list[str]:
    """Ten messages of *words* words each — `_Limiter` counts words as tokens."""
    return [" ".join(["w"] * words)] * 10


@pytest.mark.asyncio
async def test_chunk_is_capped_by_the_summarization_models_window(
    tiny_window_model, monkeypatch
):
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(80),
        agent=SimpleNamespace(model=tiny_window_model),
        limiter=_Limiter(),
        token_threshold=1000,
    )

    assert len(sent) > 1, "the request budget alone put the history in one chunk"
    assert all(
        _Limiter().count_tokens(chunk) <= int(_TINY_WINDOW * 0.9) for chunk in sent
    )


@pytest.mark.asyncio
async def test_the_instructions_are_paid_for_out_of_the_chunk_budget(
    tiny_window_model, monkeypatch
):
    """The header and the last-part note are appended after the split is sized.

    A chunk sized to 90% of the window and then given a header is a request the
    model refuses with `context_length_exceeded` — and a refused chunk fails the
    compaction, so the one turn that needed a summary gets an error instead.
    """
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(60),
        agent=SimpleNamespace(model=tiny_window_model),
        limiter=_Limiter(),
        token_threshold=1000,
        include_last_user_intent_instruction=True,
    )

    assert len(sent) > 1, "one chunk would not exercise the per-chunk header"
    assert all(
        _Limiter().count_tokens(chunk) <= _TINY_WINDOW for chunk in sent
    ), "a chunk plus its instructions is larger than the model's window"
    assert all("spine of it" in chunk for chunk in sent)
    assert "latest request" in sent[-1]


@pytest.mark.asyncio
async def test_a_single_message_larger_than_the_budget_is_clipped(
    tiny_window_model, monkeypatch
):
    """The split never breaks a message, so it would ride alone in an oversized chunk.

    Kept at full length and given its header, one fat message becomes a request
    past the window the model accepts, and a refused chunk fails the compaction.
    The archive keeps the message whole; the summarizer gets what fits.
    """
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=[" ".join(["w"] * 350)],
        agent=SimpleNamespace(model=tiny_window_model),
        limiter=_Limiter(),
        token_threshold=1000,
        include_last_user_intent_instruction=True,
    )

    assert len(sent) == 1
    assert _Limiter().count_tokens(sent[0]) <= _TINY_WINDOW


@pytest.mark.asyncio
async def test_chunk_uses_the_budget_when_the_model_window_is_unknown(monkeypatch):
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(80),
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=1000,
    )

    assert len(sent) == 1
    assert _Limiter().count_tokens(sent[0]) == 800


@pytest.mark.asyncio
async def test_consolidation_asks_for_a_merge_not_a_second_snapshot():
    """Two chunk summaries must become one snapshot, not two stacked ones."""
    from zrb.llm.summarizer.chunk_processor import consolidate_summaries

    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="merged"))
    await consolidate_summaries(
        "<state_snapshot>a</state_snapshot>\n<state_snapshot>b</state_snapshot>",
        agent,
        1000,
        True,
        limiter=_Limiter(),
    )

    prompt = agent.run.call_args.args[0]
    assert "Merge, do not append" in prompt
    assert "every section appears once" in prompt
    assert "newer observation wins" in prompt
    assert "keeps the observation time it was first recorded with" in prompt


@pytest.mark.asyncio
async def test_consolidation_never_drops_an_unanswered_request(monkeypatch):
    """The merge used to let eight messages outvote three hundred sixty-eight.

    "The newer observation wins" is right for state and wrong for a request: the
    newest snapshot is the end of the conversation, not the whole of what the user
    asked for, and a question nobody answered does not stop being owed.
    """
    from zrb.llm.summarizer.chunk_processor import consolidate_summaries

    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="merged"))
    await consolidate_summaries(
        "<state_snapshot>a</state_snapshot>\n<state_snapshot>b</state_snapshot>",
        agent,
        1000,
        True,
        limiter=_Limiter(),
    )

    prompt = agent.run.call_args.args[0]
    assert "size is not priority" in prompt
    assert "is never dropped" in prompt


@pytest.mark.asyncio
async def test_tool_output_is_clipped_before_the_summarizer_reads_it(monkeypatch):
    """A fat tool result spends the chunk budget on text the archive keeps.

    Unclipped, tool output is most of a long history's mass, so it decides where
    the chunks fall — and a split is what put one conversation's first half hour
    in a different snapshot from its last eight messages.
    """
    sent = _recording_summarizer(monkeypatch)
    fat = ModelRequest(
        parts=[
            ToolReturnPart(
                content="A" * 9_000, tool_name="Read", tool_call_id="call_1"
            )
        ]
    )

    await chunk_and_summarize(
        messages=[fat],
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=100_000,
    )

    assert len(sent) == 1
    assert "A" * 9_000 not in sent[0]
    assert "characters omitted" in sent[0]


@pytest.mark.asyncio
async def test_clipping_keeps_the_end_of_a_tool_result(monkeypatch):
    """A result's conclusion lives at its end as often as its subject at its start.

    The summary replaces the result outright, so a head-only clip can drop the
    one line the next session needed: the failing test's name, the `git status`
    that says what is still dirty, the match a search returned.
    """
    sent = _recording_summarizer(monkeypatch)
    body = "a line of scaffolding. " * 100
    fat = ModelRequest(
        parts=[
            ToolReturnPart(
                content=f"{body}{'DECISIVE'}", tool_name="Read", tool_call_id="call_1"
            )
        ]
    )

    await chunk_and_summarize(
        messages=[fat],
        agent=MagicMock(),
        limiter=_Limiter(),
        token_threshold=100_000,
    )

    assert len(sent) == 1
    assert "DECISIVE" in sent[0]
    assert "characters omitted" in sent[0]


class _CharLimiter:
    """A limiter that counts characters, for a test whose subject is text size."""

    def count_tokens(self, text: str) -> int:
        return len(text)


@pytest.mark.asyncio
async def test_clipping_keeps_a_tool_heavy_conversation_in_one_chunk(monkeypatch):
    """Twenty fat results put this history in two chunks before the clip began.

    One chunk is the point: two snapshots are merged by a prompt that says the
    newer observation wins, and the newer chunk is the end of the conversation
    rather than the whole of it.
    """
    sent = _recording_summarizer(monkeypatch)
    messages = []
    for i in range(20):
        messages.append(ModelRequest(parts=[UserPromptPart(content=f"q{i}")]))
        messages.append(
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        content="B" * 5_000, tool_name="Read", tool_call_id=f"c{i}"
                    )
                ]
            )
        )

    await chunk_and_summarize(
        messages=messages,
        agent=MagicMock(),
        limiter=_CharLimiter(),
        token_threshold=100_000,
    )

    assert len(sent) == 1
    assert sum(len(chunk) for chunk in sent) < 60_000


@pytest.mark.asyncio
async def test_every_part_is_told_the_user_words_are_the_spine(
    tiny_window_model, monkeypatch
):
    """The intent instruction used to reach the last chunk alone.

    In the session that exposed it, that chunk held 8 messages of 376, while the
    chunk holding the other 368 — including the user's opening question — was
    summarized as a work log.
    """
    sent = _recording_summarizer(monkeypatch)

    await chunk_and_summarize(
        messages=_messages(80),
        agent=SimpleNamespace(model=tiny_window_model),
        limiter=_Limiter(),
        token_threshold=1000,
        include_last_user_intent_instruction=True,
    )

    assert len(sent) > 1
    assert all("spine" in chunk for chunk in sent)
    assert all("part" in chunk for chunk in sent)
    assert "latest request" not in sent[0]
    assert sent[-1].count("latest request") == 1
    # Its own paragraph, never the last line of the transcript: the summarizer is
    # told to ignore directives it finds inside the history.
    assert "\n\nThis part ends the history" in sent[-1]
