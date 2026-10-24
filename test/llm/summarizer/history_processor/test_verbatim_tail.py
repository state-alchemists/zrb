"""The kept tail is rendered to plain text, except a trailing deferred call.

Covers the behavior ADR-0041 (revised) describes: `split_history` no longer
avoids a tool call/return pair, because the kept tail is folded into the
summary turn as readable text instead of being resent as separate structured
messages. The one exception is a still-unresolved (deferred) tool call, which
must stay in native message form for pydantic-ai to resume it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.summarizer import summarize_history


class FixedLimiter:
    """Every message costs the same, so a split index is easy to predict."""

    def __init__(self, per_message: int = 10):
        self.per_message = per_message

    def count_tokens(self, content):
        if isinstance(content, list):
            return len(content) * self.per_message
        return self.per_message

    def truncate_text(self, text, limit):
        return text[:limit]


def _summarizer_agent(summary: str = "<state_snapshot>Summary</state_snapshot>"):
    agent = MagicMock()
    mock_result = MagicMock()
    mock_result.output = summary
    agent.run = AsyncMock(return_value=mock_result)
    return agent


def _structured_parts(messages) -> list:
    """Every `ToolCallPart`/`ToolReturnPart` still present as a real part,
    across every message, in order — what reaches the model in structured
    form rather than as rendered text."""
    structured = []
    for msg in messages:
        for part in getattr(msg, "parts", []):
            if isinstance(part, (ToolCallPart, ToolReturnPart)):
                structured.append(part)
    return structured


@pytest.mark.asyncio
async def test_a_resolved_tool_pair_spanning_almost_the_whole_history_is_still_kept():
    """Regression: a call paired with a return near the very end used to force
    `to_keep` to come back empty — no split was both within the tail budget
    and safe for the pair, so the whole history summarized as one chunk. The
    budget-only split now keeps a tail regardless, rendered as text."""
    call = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args={}, tool_call_id="1")]
    )
    filler = [ModelResponse(parts=[TextPart(content="x")]) for _ in range(20)]
    result = ModelRequest(
        parts=[
            ToolReturnPart(tool_name="read_file", content="contents", tool_call_id="1")
        ]
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="please read it")]),
        call,
        *filler,
        result,
    ]

    with patch(
        "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
        AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
    ):
        new_history = await summarize_history(
            messages,
            agent=_summarizer_agent(),
            summary_window=300,
            limiter=FixedLimiter(),
            conversational_token_threshold=100,
        )

    combined = "\n".join(
        str(getattr(p, "content", "")) for m in new_history for p in m.parts
    )
    assert "contents" in combined
    # The pair is resolved, so nothing needs to stay structured.
    assert _structured_parts(new_history) == []


@pytest.mark.asyncio
async def test_a_huge_tool_result_is_shortened_in_the_kept_tail():
    """The tail is a handover, not evidence.

    The replaced messages are archived in full, so 40,000 characters of tool
    output kept here would spend the next turn's window on text nobody reads
    again — and the summary would lose that room for saying what the work was.
    Only the tool result is cut: the turn after it survives whole.
    """
    huge = "y" * 40_000
    messages = [
        ModelRequest(parts=[UserPromptPart(content="run the suite")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="Shell", args={}, tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="filler")]),
        ModelResponse(parts=[TextPart(content="filler")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="Shell", content=huge, tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="now what?")]),
    ]

    with patch(
        "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
        AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
    ):
        new_history = await summarize_history(
            messages,
            agent=_summarizer_agent(),
            summary_window=300,
            limiter=FixedLimiter(),
            conversational_token_threshold=100,
        )

    combined = "\n".join(
        str(getattr(p, "content", "")) for m in new_history for p in m.parts
    )
    assert "[truncated:" in combined
    assert huge not in combined
    assert "now what?" in combined


@pytest.mark.asyncio
async def test_a_small_tool_result_is_kept_word_for_word():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="run it")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="Shell", args={}, tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="filler")]),
        ModelResponse(parts=[TextPart(content="filler")]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="Shell", content="3 passed in 0.10s", tool_call_id="1"
                )
            ]
        ),
        ModelRequest(parts=[UserPromptPart(content="now what?")]),
    ]

    with patch(
        "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
        AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
    ):
        new_history = await summarize_history(
            messages,
            agent=_summarizer_agent(),
            summary_window=300,
            limiter=FixedLimiter(),
            conversational_token_threshold=100,
        )

    combined = "\n".join(
        str(getattr(p, "content", "")) for m in new_history for p in m.parts
    )
    assert "3 passed in 0.10s" in combined
    assert "[truncated:" not in combined


@pytest.mark.asyncio
async def test_a_trailing_deferred_call_stays_in_native_message_form():
    """A tool call with no return yet (pending a deferred result) must still
    be resumable, so it is excluded from the text rendering and kept as a
    real `ModelResponse`/`ToolCallPart`."""
    pending_call = ToolCallPart(
        tool_name="run_shell", args={"cmd": "rm -rf /tmp/x"}, tool_call_id="pending-1"
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="clean up the temp dir")]),
        ModelResponse(parts=[pending_call]),
    ]

    with patch(
        "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
        AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
    ):
        new_history = await summarize_history(
            messages,
            agent=_summarizer_agent(),
            summary_window=0,
            limiter=FixedLimiter(),
            conversational_token_threshold=10,
            force=True,
        )

    structured = _structured_parts(new_history)
    assert len(structured) == 1
    assert structured[0] is pending_call
    assert isinstance(new_history[-1], ModelResponse)


@pytest.mark.asyncio
async def test_resolved_pairs_before_a_deferred_call_are_still_flattened():
    """Only the unresolved call's own turn stays structured; earlier, already
    resolved tool pairs in the kept tail are still rendered to text."""
    resolved_call = ModelResponse(
        parts=[ToolCallPart(tool_name="read_file", args={}, tool_call_id="done-1")]
    )
    resolved_return = ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name="read_file", content="earlier contents", tool_call_id="done-1"
            )
        ]
    )
    pending_call = ToolCallPart(
        tool_name="run_shell", args={"cmd": "ls"}, tool_call_id="pending-2"
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="read then list")]),
        resolved_call,
        resolved_return,
        ModelResponse(parts=[pending_call]),
    ]

    with patch(
        "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
        AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
    ):
        new_history = await summarize_history(
            messages,
            agent=_summarizer_agent(),
            summary_window=0,
            limiter=FixedLimiter(),
            conversational_token_threshold=50,
            force=True,
        )

    structured = _structured_parts(new_history)
    assert structured == [pending_call]
    combined = "\n".join(
        str(getattr(p, "content", "")) for m in new_history for p in m.parts
    )
    assert "earlier contents" in combined
