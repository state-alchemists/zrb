from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.agent.run.history_utils import drop_oldest_turn, filter_nil_content


class UnknownMessage:
    pass


class PartWithoutContent:
    pass


class PartWithContent:
    def __init__(self, content):
        self.content = content


def test_drop_oldest_turn_empty():
    assert drop_oldest_turn([]) == []


def test_drop_oldest_turn_single():
    assert drop_oldest_turn(["msg1"]) == []


def test_drop_oldest_turn_multiple():
    req1 = ModelRequest(parts=[UserPromptPart(content="1")])
    res1 = ModelResponse(parts=[TextPart(content="2")])
    req2 = ModelRequest(parts=[UserPromptPart(content="3")])
    res2 = ModelResponse(parts=[TextPart(content="4")])

    # is_turn_start checks if it is ModelRequest with UserPromptPart or SystemPromptPart
    history = [req1, res1, req2, res2]
    new_hist = drop_oldest_turn(history)
    assert new_hist == [req2, res2]


def test_filter_nil_content():
    # Test ModelRequest filtering
    msg1 = ModelRequest(
        parts=[
            ToolCallPart(tool_name="tool1", args="{}"),
            ToolCallPart(
                tool_name="", args="{}"
            ),  # Should be dropped if it doesn't have tool_name (actually wait, my mock tool_name isn't used, but the logic says `if part.tool_name:`
            ToolReturnPart(tool_name="tool1", content=None, tool_call_id="1"),
            ToolReturnPart(tool_name="tool1", content="result", tool_call_id="2"),
            ThinkingPart(content=None),
            ThinkingPart(content="think"),
            TextPart(content=None),
            TextPart(content="text"),
            UserPromptPart(content=None),
            UserPromptPart(content="prompt"),
            SystemPromptPart(content=None),
            SystemPromptPart(content="sys"),
            PartWithoutContent(),
        ]
    )

    # Test ModelResponse filtering
    msg2 = ModelResponse(
        parts=[
            TextPart(content=None),
            TextPart(content="res_text"),
            ToolCallPart(tool_name="tool2", args="{}"),
            ThinkingPart(content=None),
            ThinkingPart(content="res_think"),
            PartWithoutContent(),
        ]
    )

    # Test Response with tool call but no text part
    msg3 = ModelResponse(parts=[ToolCallPart(tool_name="tool3", args="{}")])

    msg4 = UnknownMessage()

    messages = [msg1, msg2, msg3, msg4]

    filtered = filter_nil_content(messages)

    assert len(filtered) == 4

    # Check msg1
    m1 = filtered[0]
    assert isinstance(m1, ModelRequest)
    assert len(m1.parts) == 12  # ToolCallPart with no tool_name is dropped
    assert m1.parts[1].content == "null"
    assert m1.parts[3].content == "."
    assert m1.parts[5].content == "."
    assert m1.parts[7].content == "."
    assert m1.parts[9].content == "."

    # Check msg2
    m2 = filtered[1]
    assert isinstance(m2, ModelResponse)
    assert len(m2.parts) == 6
    assert m2.parts[0].content == "."

    # Check msg3
    m3 = filtered[2]
    assert isinstance(m3, ModelResponse)
    assert len(m3.parts) == 2
    assert isinstance(m3.parts[0], TextPart)
    assert m3.parts[0].content == "."
    assert isinstance(m3.parts[1], ToolCallPart)
