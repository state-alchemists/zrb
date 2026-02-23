import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.history_splitter import (
    find_best_effort_split,
    find_safe_split_index,
    is_split_safe,
    split_history,
)


class DummyLimiter(LLMLimiter):
    def count_tokens(self, obj):
        if isinstance(obj, list):
            return sum(self.count_tokens(x) for x in obj)
        return 1

    def truncate_text(self, text, limit):
        return text


@pytest.fixture
def limiter():
    return DummyLimiter()


def test_is_split_safe_complete_pair():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="3")]),
    ]
    from zrb.llm.message import get_tool_pairs

    tool_pairs = get_tool_pairs(messages)

    # Split before ToolCall is safe (call and return both after split)
    assert is_split_safe(messages, 1, tool_pairs)
    # Split between ToolCall and ToolReturn is unsafe
    assert not is_split_safe(messages, 2, tool_pairs)
    # Split after ToolReturn is safe (call and return both before split)
    assert is_split_safe(messages, 3, tool_pairs)


def test_find_safe_split_index(limiter):
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelRequest(parts=[UserPromptPart(content="3")]),
    ]
    # token_threshold is 100, we expect it to find index 3
    # index 1 keeps 3 messages, index 3 keeps 1 message
    # it prefers the smallest valid index THAT is a turn start
    idx = find_safe_split_index(messages, limiter, 100)
    assert idx == 3

    # If there is no turn start, it should fallback to the smallest safe index
    messages_no_turn_start = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="a", content="done", tool_call_id="1")]
        ),
        ModelResponse(parts=[ToolCallPart(tool_name="b", args={}, tool_call_id="2")]),
    ]
    idx_no_turn = find_safe_split_index(messages_no_turn_start, limiter, 100)
    assert idx_no_turn == 1

    # If token threshold is 2 (0.8 * 2 = 1.6), we can only keep 1 message safely
    idx = find_safe_split_index(messages, limiter, 2)
    assert idx == 3


def test_find_best_effort_split(limiter):
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(parts=[UserPromptPart(content="2")]),
    ]
    # We have a tool call but no return.
    # If we split at 1, to_keep is [Call, Prompt]. Call is before split? No, Call is at 1. So call is kept. This is OK.
    # If we split at 2, to_keep is [Prompt]. Call is summarized. We lose incomplete pair.
    to_sum, to_keep = find_best_effort_split(messages, limiter, 100)
    # Should pick index 1 to keep more messages without breaking anything illegal
    assert len(to_sum) == 1
    assert len(to_keep) == 2


def test_split_history_near_window(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(10)]
    # All are turn starts.
    # summary_window = 3, target_idx = 7
    # Should split exactly at 7
    to_sum, to_keep = split_history(messages, 3, limiter, 100)
    assert len(to_keep) == 3

    # summary_window = 3, but token limit very low
    to_sum, to_keep = split_history(messages, 3, limiter, 2)
    assert len(to_keep) == 1
