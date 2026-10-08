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
    def count_tokens(self, obj) -> int:
        if isinstance(obj, list):
            return sum(self.count_tokens(x) for x in obj)
        return 1

    def truncate_text(self, text: str, max_tokens: int) -> str:
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

    assert is_split_safe(messages, 1, tool_pairs)

    assert not is_split_safe(messages, 2, tool_pairs)

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

    idx = find_safe_split_index(messages, limiter, 100)
    assert idx == 3

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

    idx = find_safe_split_index(messages, limiter, 2)
    assert idx == 3


def test_find_best_effort_split(limiter):
    messages = [
        ModelRequest(parts=[UserPromptPart(content="0")]),
        ModelResponse(parts=[ToolCallPart(tool_name="a", args={}, tool_call_id="1")]),
        ModelRequest(parts=[UserPromptPart(content="2")]),
    ]

    to_sum, to_keep = find_best_effort_split(messages, limiter, 100)

    assert len(to_sum) == 1
    assert len(to_keep) == 2


def test_split_history_near_window(limiter):
    messages = [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(10)]

    to_sum, to_keep = split_history(messages, 3, limiter, 100)
    assert len(to_keep) == 3

    to_sum, to_keep = split_history(messages, 3, limiter, 2)
    assert len(to_keep) == 1
