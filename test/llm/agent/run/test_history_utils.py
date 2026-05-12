from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.agent.run.history_utils import (
    drop_oldest_turn,
    filter_nil_content,
    strip_to_text_only,
)


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


def test_drop_oldest_turn_min_turns():
    req1 = ModelRequest(parts=[UserPromptPart(content="1")])
    res1 = ModelResponse(parts=[TextPart(content="2")])
    req2 = ModelRequest(parts=[UserPromptPart(content="3")])
    res2 = ModelResponse(parts=[TextPart(content="4")])

    history = [req1, res1, req2, res2]

    # min_turns=1: can drop 1st turn because 2nd turn exists
    assert drop_oldest_turn(history, min_turns=1) == [req2, res2]

    # min_turns=2: cannot drop because only 2 turns exist
    assert drop_oldest_turn(history, min_turns=2) == history


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


def test_filter_nil_content_preserves_builtin_tool_call_part():
    # BuiltinToolCallPart is a dataclass without a `content` field; it must
    # pass through filter_nil_content untouched rather than crashing the
    # sanitizer when the model uses provider-side tools (e.g. web_search).
    btc = BuiltinToolCallPart(tool_name="web_search", args="{}")
    msg = ModelResponse(parts=[btc, TextPart(content="ok")])

    filtered = filter_nil_content([msg])

    assert len(filtered) == 1
    out = filtered[0]
    assert isinstance(out, ModelResponse)
    assert len(out.parts) == 2
    assert isinstance(out.parts[0], BuiltinToolCallPart)
    assert out.parts[0].tool_name == "web_search"


def test_strip_to_text_only_strips_thinking_and_tool_structure():
    """strip_to_text_only converts ToolCallPart/ToolReturnPart to descriptive
    text, removes ThinkingPart, and fixes nil/empty content."""
    history = [
        ModelRequest(parts=[UserPromptPart(content="deploy to prod")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="deploy", args='{"env":"prod"}', tool_call_id="c1"
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="deploy", content="started", tool_call_id="c1")
            ]
        ),
        ModelResponse(
            parts=[
                ThinkingPart(content="verifying"),
                TextPart(content="Done, deployment running"),
            ]
        ),
    ]

    result = strip_to_text_only(history)

    # All 4 messages preserved (tool parts become TextPart, ThinkingPart dropped)
    assert len(result) == 4

    # msg[0]: UserPromptPart unchanged
    assert isinstance(result[0], ModelRequest)
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert result[0].parts[0].content == "deploy to prod"

    # msg[1]: ToolCallPart converted to descriptive text
    assert isinstance(result[1], ModelResponse)
    assert len(result[1].parts) == 1
    assert isinstance(result[1].parts[0], TextPart)
    assert result[1].parts[0].content == '[Tool: deploy({"env":"prod"})]'

    # msg[2]: ToolReturnPart converted to UserPromptPart (preserves role semantics)
    assert isinstance(result[2], ModelRequest)
    assert len(result[2].parts) == 1
    assert isinstance(result[2].parts[0], UserPromptPart)
    assert result[2].parts[0].content == "[Result (deploy): started]"

    # msg[3]: ThinkingPart stripped, TextPart kept
    assert isinstance(result[3], ModelResponse)
    assert len(result[3].parts) == 1
    assert isinstance(result[3].parts[0], TextPart)
    assert result[3].parts[0].content == "Done, deployment running"
    assert not any(
        isinstance(p, ThinkingPart) for m in result for p in getattr(m, "parts", [])
    )


def test_strip_to_text_only_normalizes_null_content():
    """None/empty content in any part becomes '.'; tool parts are converted to descriptive text."""
    history = [
        ModelRequest(
            parts=[
                UserPromptPart(content=None),
                ToolReturnPart(tool_name="t1", content=None, tool_call_id="c1"),
            ]
        ),
        ModelResponse(
            parts=[
                TextPart(content=""),
                ToolCallPart(tool_name="t2", args="{}", tool_call_id="c2"),
            ]
        ),
    ]

    result = strip_to_text_only(history)

    # msg[0]: UserPromptPart fixed, ToolReturnPart → "[Result (t1): (no value)]"
    assert isinstance(result[0], ModelRequest)
    assert len(result[0].parts) == 2
    assert result[0].parts[0].content == "."
    assert "[Result (t1): (no value)]" == result[0].parts[1].content

    # msg[1]: TextPart fixed, ToolCallPart → "[Tool: t2({})]"
    assert isinstance(result[1], ModelResponse)
    assert len(result[1].parts) == 2
    assert result[1].parts[0].content == "."
    assert "[Tool: t2({})]" == result[1].parts[1].content


def test_strip_to_text_only_empty_result_returns_original():
    """A ModelResponse with only tool calls becomes a descriptive TextPart, not empty."""
    history = [
        ModelResponse(parts=[ToolCallPart(tool_name="x", args="{}", tool_call_id="c1")])
    ]
    result = strip_to_text_only(history)
    assert len(result) == 1
    assert isinstance(result[0], ModelResponse)
    assert len(result[0].parts) == 1
    assert isinstance(result[0].parts[0], TextPart)
    assert "[Tool: x({})]" == result[0].parts[0].content


def test_strip_to_text_only_keeps_conversation_flow():
    """Multi-turn tool-using conversation: tool call/return parts are converted
    to descriptive text, preserving semantic context."""
    history = [
        ModelRequest(parts=[UserPromptPart(content="weather in Boston?")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="get_weather",
                    args='{"city":"Boston"}',
                    tool_call_id="c1",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="get_weather", content="72F", tool_call_id="c1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="It is 72F in Boston.")]),
        ModelRequest(parts=[UserPromptPart(content="What about NYC?")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="get_weather",
                    args='{"city":"NYC"}',
                    tool_call_id="c2",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="get_weather", content="80F", tool_call_id="c2"
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="It is 80F in NYC.")]),
    ]

    result = strip_to_text_only(history)
    # All 8 messages preserved (tool parts become descriptive TextPart)
    assert len(result) == 8

    # msg[0] unchanged
    assert result[0].parts[0].content == "weather in Boston?"
    # msg[1] → "[Tool: get_weather({"city":"Boston"})]"
    assert "get_weather" in result[1].parts[0].content
    assert "Boston" in result[1].parts[0].content
    # msg[2] → "[Result (get_weather): 72F]"
    assert "[Result (get_weather): 72F]" == result[2].parts[0].content
    # msg[3] unchanged
    assert result[3].parts[0].content == "It is 72F in Boston."
    # msg[4] unchanged
    assert result[4].parts[0].content == "What about NYC?"
    # msg[5] → "[Tool: get_weather({"city":"NYC"})]"
    assert "NYC" in result[5].parts[0].content
    # msg[6] → "[Result (get_weather): 80F]"
    assert "[Result (get_weather): 80F]" == result[6].parts[0].content
    # msg[7] unchanged
    assert result[7].parts[0].content == "It is 80F in NYC."


def test_strip_to_text_only_drops_empty_tool_call_part():
    """ToolCallPart without tool_name is dropped; TextPart('.')

    is injected to keep the message valid."""
    history = [
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="", args="{}", tool_call_id="c1"),
            ]
        ),
    ]
    result = strip_to_text_only(history)
    assert len(result) == 1
    parts = result[0].parts
    assert len(parts) == 1
    assert isinstance(parts[0], TextPart)
    assert parts[0].content == "."


def test_filter_nil_content_uses_null_for_builtin_tool_return():
    # BuiltinToolReturnPart is a sibling of ToolReturnPart (both extend
    # BaseToolReturnPart). A nil content must become "null", not ".",
    # so the placeholder is parseable as a tool result.
    msg = ModelRequest(
        parts=[
            BuiltinToolReturnPart(
                tool_name="web_search", content=None, tool_call_id="1"
            ),
        ]
    )

    filtered = filter_nil_content([msg])

    assert len(filtered) == 1
    assert filtered[0].parts[0].content == "null"
