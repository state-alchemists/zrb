from datetime import datetime

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.message import ensure_alternating_roles


def test_alternating_roles_merge_user_requests():
    # User -> User should merge
    req1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    req2 = ModelRequest(parts=[UserPromptPart(content="World")])

    result = ensure_alternating_roles([req1, req2])

    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)
    assert len(result[0].parts) == 2
    assert result[0].parts[0].content == "Hello"
    assert result[0].parts[1].content == "World"


def test_alternating_roles_merge_model_responses():
    # Assistant -> Assistant should merge
    res1 = ModelResponse(
        parts=[TextPart(content="Thinking...")], timestamp=datetime.now()
    )
    res2 = ModelResponse(parts=[TextPart(content="Answer")], timestamp=datetime.now())

    result = ensure_alternating_roles([res1, res2])

    assert len(result) == 1
    assert isinstance(result[0], ModelResponse)
    assert len(result[0].parts) == 2
    assert result[0].parts[0].content == "Thinking..."
    assert result[0].parts[1].content == "Answer"


def test_alternating_roles_mixed_sequence():
    # User -> Assistant -> User -> Assistant -> User -> User
    req1 = ModelRequest(parts=[UserPromptPart(content="1")])
    res1 = ModelResponse(parts=[TextPart(content="2")], timestamp=datetime.now())
    req2 = ModelRequest(parts=[UserPromptPart(content="3")])
    res2 = ModelResponse(parts=[TextPart(content="4")], timestamp=datetime.now())
    req3 = ModelRequest(parts=[UserPromptPart(content="5")])
    req4 = ModelRequest(parts=[UserPromptPart(content="6")])

    result = ensure_alternating_roles([req1, res1, req2, res2, req3, req4])

    assert len(result) == 5
    assert result[0].parts[0].content == "1"
    assert result[1].parts[0].content == "2"
    assert result[2].parts[0].content == "3"
    assert result[3].parts[0].content == "4"
    # Merged last two
    assert len(result[4].parts) == 2
    assert result[4].parts[0].content == "5"
    assert result[4].parts[1].content == "6"


def test_alternating_roles_tool_call_flow():
    # User -> ToolCall -> ToolReturn -> Text -> User
    # This is: Req -> Res -> Req -> Res -> Req
    # Should result in NO merges

    req1 = ModelRequest(parts=[UserPromptPart(content="Do X")])
    res1 = ModelResponse(
        parts=[ToolCallPart(tool_name="tool_x", args={"a": 1})],
        timestamp=datetime.now(),
    )
    req2 = ModelRequest(parts=[ToolReturnPart(tool_name="tool_x", content="Result X")])
    res2 = ModelResponse(parts=[TextPart(content="Done")], timestamp=datetime.now())
    req3 = ModelRequest(parts=[UserPromptPart(content="Thx")])

    result = ensure_alternating_roles([req1, res1, req2, res2, req3])

    assert len(result) == 5
    assert isinstance(result[0], ModelRequest)
    assert isinstance(result[1], ModelResponse)
    assert isinstance(result[2], ModelRequest)
    assert isinstance(result[3], ModelResponse)
    assert isinstance(result[4], ModelRequest)


def test_alternating_roles_empty_and_single():
    assert ensure_alternating_roles([]) == []

    req = ModelRequest(parts=[UserPromptPart(content="Hi")])
    assert ensure_alternating_roles([req]) == [req]


def test_alternating_roles_tool_return_and_user_prompt():
    # ToolReturn -> UserPrompt (same turn essentially)
    # Req -> Req
    # Should merge

    req1 = ModelRequest(parts=[ToolReturnPart(tool_name="x", content="res")])
    req2 = ModelRequest(parts=[UserPromptPart(content="Next")])

    result = ensure_alternating_roles([req1, req2])

    assert len(result) == 1
    assert isinstance(result[0], ModelRequest)
    assert len(result[0].parts) == 2
    assert isinstance(result[0].parts[0], ToolReturnPart)
    assert isinstance(result[0].parts[1], UserPromptPart)
