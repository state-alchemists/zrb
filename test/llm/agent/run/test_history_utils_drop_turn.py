from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
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


def _content(part) -> object:
    """The `content` a part carries, whatever part class it turned out to be."""
    return getattr(part, "content", None)


class UnknownMessage:
    pass


class PartWithoutContent:
    pass


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
    # `content=None` is illegal per the part types and deliberate here: it is
    # what a misbehaving provider sends, and normalizing it is the whole point.
    # Test ModelRequest filtering
    msg1 = ModelRequest(
        parts=[
            ToolCallPart(tool_name="tool1", args="{}"),
            ToolCallPart(
                tool_name="", args="{}"
            ),  # Should be dropped if it doesn't have tool_name (actually wait, my mock tool_name isn't used, but the logic says `if part.tool_name:`
            # pyright: ignore[reportArgumentType]
            ToolReturnPart(tool_name="tool1", content=None, tool_call_id="1"),
            ToolReturnPart(tool_name="tool1", content="result", tool_call_id="2"),
            ThinkingPart(content=None),  # pyright: ignore[reportArgumentType]
            ThinkingPart(content="think"),
            TextPart(content=None),  # pyright: ignore[reportArgumentType]
            TextPart(content="text"),
            UserPromptPart(content=None),  # pyright: ignore[reportArgumentType]
            UserPromptPart(content="prompt"),
            SystemPromptPart(content=None),  # pyright: ignore[reportArgumentType]
            SystemPromptPart(content="sys"),
            PartWithoutContent(),
        ]
    )

    # Test ModelResponse filtering
    msg2 = ModelResponse(
        parts=[
            TextPart(content=None),  # pyright: ignore[reportArgumentType]
            TextPart(content="res_text"),
            ToolCallPart(tool_name="tool2", args="{}"),
            ThinkingPart(content=None),  # pyright: ignore[reportArgumentType]
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
    assert _content(m1.parts[1]) == "null"
    assert _content(m1.parts[3]) == "(empty)"
    assert _content(m1.parts[5]) == "(empty)"
    assert _content(m1.parts[7]) == "(empty)"
    assert _content(m1.parts[9]) == "(empty)"

    # Check msg2
    m2 = filtered[1]
    assert isinstance(m2, ModelResponse)
    assert len(m2.parts) == 6
    assert _content(m2.parts[0]) == "(empty)"

    # Check msg3 — a tool-call-only response is valid without text, so NO
    # "(tool call)" placeholder is injected (it would otherwise leak into
    # history and get imitated by weaker models).
    m3 = filtered[2]
    assert isinstance(m3, ModelResponse)
    assert len(m3.parts) == 1
    assert isinstance(m3.parts[0], ToolCallPart)
    assert not any(
        isinstance(p, TextPart) and p.content == "(tool call)" for p in m3.parts
    )


def test_filter_nil_content_injects_placeholder_when_no_text_and_no_tool_call():
    """A response with neither text nor tool calls (e.g. thinking-only) still
    gets the "(tool call)" placeholder — providers reject a truly empty turn."""
    msg = ModelResponse(parts=[ThinkingPart(content="reasoning only")])

    filtered = filter_nil_content([msg])

    out = filtered[0]
    assert isinstance(out, ModelResponse)
    assert isinstance(out.parts[0], TextPart)
    assert out.parts[0].content == "(tool call)"


def test_filter_nil_content_no_placeholder_for_tool_call_only():
    """Tool-call-only response is left untouched: no placeholder TextPart."""
    msg = ModelResponse(parts=[ToolCallPart(tool_name="t", args="{}")])

    filtered = filter_nil_content([msg])

    out = filtered[0]
    assert [type(p).__name__ for p in out.parts] == ["ToolCallPart"]


def test_filter_nil_content_preserves_builtin_tool_call_part():
    # NativeToolCallPart is a dataclass without a `content` field; it must
    # pass through filter_nil_content untouched rather than crashing the
    # sanitizer when the model uses provider-side tools (e.g. web_search).
    btc = NativeToolCallPart(tool_name="web_search", args="{}")
    msg = ModelResponse(parts=[btc, TextPart(content="ok")])

    filtered = filter_nil_content([msg])

    assert len(filtered) == 1
    out = filtered[0]
    assert isinstance(out, ModelResponse)
    assert len(out.parts) == 2
    assert isinstance(out.parts[0], NativeToolCallPart)
    assert out.parts[0].tool_name == "web_search"


def test_strip_to_text_only_converts_all_non_text_parts():
    """ToolCallPart, ToolReturnPart → ``(sanitized-history) …`` prose,
    ThinkingPart → its text content.
    """
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

    # All 4 messages preserved (tool parts become descriptive TextPart)
    assert len(result) == 4

    # msg[0]: UserPromptPart unchanged
    assert result[0].parts[0].content == "deploy to prod"

    # msg[1]: ToolCallPart → sanitized-history prose carrying tool name + args.
    msg1_text = result[1].parts[0].content
    assert "(sanitized-history)" in msg1_text
    assert "deploy" in msg1_text
    assert '"env":"prod"' in msg1_text

    # msg[2]: ToolReturnPart → UserPromptPart (TextPart is illegal in ModelRequest;
    # pydantic-ai's _map_user_message hits assert_never on any non-{System,User,
    # ToolReturn,Retry}PromptPart in a user-role message).
    assert isinstance(result[2], ModelRequest)
    assert isinstance(result[2].parts[0], UserPromptPart)
    msg2_text = result[2].parts[0].content
    assert "(sanitized-history)" in msg2_text
    assert "deploy" in msg2_text
    assert "started" in msg2_text

    # msg[3]: ThinkingPart → TextPart, TextPart kept
    assert isinstance(result[3], ModelResponse)
    assert len(result[3].parts) == 2
    assert isinstance(result[3].parts[0], TextPart)
    assert result[3].parts[0].content == "verifying"
    assert _content(result[3].parts[1]) == "Done, deployment running"


def test_strip_to_text_only_normalizes_null_content():
    """None/empty content becomes '.'; tool parts become descriptive TextPart."""
    history = [
        ModelRequest(
            parts=[
                UserPromptPart(content=None),  # pyright: ignore[reportArgumentType]
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

    # msg[0]: UserPromptPart fixed, ToolReturnPart → UserPromptPart (text in a
    # ModelRequest must be UserPromptPart, not TextPart).
    assert len(result[0].parts) == 2
    assert result[0].parts[0].content == "(empty)"
    assert isinstance(result[0].parts[1], UserPromptPart)
    msg0_p1 = result[0].parts[1].content
    assert "(sanitized-history)" in msg0_p1
    assert "t1" in msg0_p1
    assert "(no value)" in msg0_p1

    # msg[1]: TextPart fixed, ToolCallPart → TextPart
    assert len(result[1].parts) == 2
    assert result[1].parts[0].content == "(empty)"
    msg1_p1 = result[1].parts[1].content
    assert "(sanitized-history)" in msg1_p1
    assert "t2" in msg1_p1


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
    text = result[0].parts[0].content
    assert "(sanitized-history)" in text
    assert '"x"' in text


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
    # msg[1] → sanitized-history prose for get_weather/Boston
    assert isinstance(result[1].parts[0], TextPart)
    assert "(sanitized-history)" in result[1].parts[0].content
    assert "get_weather" in result[1].parts[0].content
    assert "Boston" in result[1].parts[0].content
    # msg[2] → UserPromptPart, sanitized-history record of result
    assert isinstance(result[2].parts[0], UserPromptPart)
    msg2_text = result[2].parts[0].content
    assert "(sanitized-history)" in msg2_text
    assert "get_weather" in msg2_text
    assert "72F" in msg2_text
    # msg[3] unchanged
    assert result[3].parts[0].content == "It is 72F in Boston."
    # msg[4] unchanged
    assert result[4].parts[0].content == "What about NYC?"
    # msg[5] → sanitized-history prose for get_weather/NYC
    assert isinstance(result[5].parts[0], TextPart)
    assert "(sanitized-history)" in result[5].parts[0].content
    assert "NYC" in result[5].parts[0].content
    # msg[6] → UserPromptPart, sanitized-history record of result
    assert isinstance(result[6].parts[0], UserPromptPart)
    msg6_text = result[6].parts[0].content
    assert "(sanitized-history)" in msg6_text
    assert "get_weather" in msg6_text
    assert "80F" in msg6_text
    # msg[7] unchanged
    assert result[7].parts[0].content == "It is 80F in NYC."


def test_strip_to_text_only_unnamed_tool_call_part():
    """ToolCallPart without tool_name becomes a sanitized-history label using
    ``(unnamed)``, not dropped."""
    history = [
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="", args="{}", tool_call_id="c1"),
            ]
        ),
    ]
    result = strip_to_text_only(history)
    assert len(result) == 1
    assert len(result[0].parts) == 1
    assert isinstance(result[0].parts[0], TextPart)
    text = result[0].parts[0].content
    assert "(sanitized-history)" in text
    assert "(unnamed)" in text


def test_filter_nil_content_uses_null_for_builtin_tool_return():
    # NativeToolReturnPart is a sibling of ToolReturnPart (both extend
    # BaseToolReturnPart). A nil content must become "null" (not "(empty)"),
    # so the placeholder is parseable as a tool result.
    msg = ModelRequest(
        parts=[
            NativeToolReturnPart(
                tool_name="web_search", content=None, tool_call_id="1"
            ),
        ]
    )

    filtered = filter_nil_content([msg])

    assert len(filtered) == 1
    assert filtered[0].parts[0].content == "null"


def test_strip_to_text_only_never_puts_textpart_in_modelrequest():
    """Regression: pydantic-ai's _map_user_message asserts_never on any non
    {System,User,ToolReturn,Retry}PromptPart inside a ModelRequest. A
    ToolReturnPart converted to TextPart used to crash the OpenAI mapper
    with ``AssertionError: Expected code to be unreachable, but got:
    TextPart(content='[Result (...): ...]')``.
    """
    from pydantic_ai.messages import RetryPromptPart, SystemPromptPart

    history = [
        ModelRequest(
            parts=[
                SystemPromptPart(content="you are a helpful assistant"),
                UserPromptPart(content="hi"),
                ToolReturnPart(
                    tool_name="ActivateSkill", content="ok", tool_call_id="c1"
                ),
                RetryPromptPart(
                    content="malformed args",
                    tool_name="ActivateSkill",
                    tool_call_id="c2",
                ),
            ]
        ),
        ModelResponse(parts=[TextPart(content="ack")]),
    ]

    result = strip_to_text_only(history)

    # Every part of the resulting ModelRequest must be one of the four
    # part types the OpenAI mapper accepts.
    allowed = (SystemPromptPart, UserPromptPart, ToolReturnPart, RetryPromptPart)
    for msg in result:
        if isinstance(msg, ModelRequest):
            for p in msg.parts:
                assert isinstance(
                    p, allowed
                ), f"illegal part type {type(p).__name__} in ModelRequest"
                # And specifically: no TextPart inside ModelRequest, ever.
                assert not isinstance(p, TextPart)
