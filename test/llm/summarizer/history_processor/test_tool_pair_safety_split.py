'Tests for tool call/return pair safety in summarization.'

from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.message import validate_tool_pair_integrity
from zrb.llm.summarizer.history_splitter import (
    find_best_effort_split,
    find_safe_split_index,
)


class MockLimiter:
    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(self.count_tokens(m) for m in content)

        return 10

    def truncate_text(self, text, limit):
        return text[:limit]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_find_safe_split_index_simple():
    'Test finding safe split index with simple history.'
    limiter = MockLimiter()

    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),
    ]


    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "zrb.llm.config.limiter.is_turn_start", lambda msg: msg == messages[4]
        )

        split_idx = find_safe_split_index(messages, limiter, 100)


        assert split_idx == 4


def test_find_safe_split_index_no_safe_split():
    'Test when no safe split is possible.'
    limiter = MockLimiter()


    messages = [
        ModelRequest(parts=[UserPromptPart("Hello")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),


    ]

    split_idx = find_safe_split_index(messages, limiter, 100)





    assert split_idx == 1


def test_find_best_effort_split():
    'Test best-effort split when no perfect split exists.'
    limiter = MockLimiter()


    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool2", args={}, tool_call_id="call_2")]
        ),

        ModelResponse(parts=[TextPart("A2")]),
    ]

    to_summarize, to_keep = find_best_effort_split(messages, limiter, 100)


    assert len(to_summarize) > 0
    assert len(to_keep) > 0
    assert len(to_summarize) + len(to_keep) == len(messages)


    assert to_summarize + to_keep == messages


def test_validate_tool_pair_integrity_valid():
    'Test validation of valid tool pairs.'
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == True
    assert len(problems) == 0


def test_validate_tool_pair_integrity_invalid():
    'Test validation of invalid tool pairs (calls without returns).'
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),

        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == False
    assert len(problems) == 1
    assert "call_1" in problems[0]
    assert "has no return" in problems[0]


def test_validate_tool_pair_integrity_orphaned_return():
    'Test validation with orphaned returns.'
    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="orphaned"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
    ]

    is_valid, problems = validate_tool_pair_integrity(messages)

    assert is_valid == False
    assert len(problems) == 1
    assert "orphaned" in problems[0]
    assert "has no call" in problems[0]


@pytest.mark.asyncio
async def test_integration_with_summarize_history():
    'Integration test with the actual summarize_history function.'
    from unittest.mock import AsyncMock, patch

    from zrb.llm.summarizer import summarize_history

    limiter = MockLimiter()
    agent = MagicMock()

    mock_result = MagicMock()
    mock_result.output = "<state_snapshot>Summary</state_snapshot>"
    agent.run = AsyncMock(return_value=mock_result)


    messages = [
        ModelRequest(parts=[UserPromptPart("Q1")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="tool1", args={}, tool_call_id="call_1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    content="result1", tool_name="tool1", tool_call_id="call_1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart("A1")]),
        ModelRequest(parts=[UserPromptPart("Q2")]),
    ]


    with patch(
        "zrb.llm.config.limiter.is_turn_start",
        side_effect=[False, False, False, False, True],
    ):

        with patch(
            "zrb.llm.summarizer.history_summarizer.chunk_and_summarize",
            AsyncMock(return_value="<state_snapshot>Summary</state_snapshot>"),
        ):

            result = await summarize_history(
                messages,
                agent=agent,
                summary_window=1,
                limiter=limiter,
                conversational_token_threshold=100,
            )


    assert len(result) == 1
    assert "Summary" in str(result[0])
    assert "Q2" in str(result[0])
