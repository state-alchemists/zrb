from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.agent.run.history_utils import (
    close_dangling_tool_calls,
    sanitize_history,
    strip_thinking_parts,
    strip_to_text_only,
)
from zrb.llm.message import TOOL_CALL_PLACEHOLDER


class UnknownMessage:
    pass


def test_strip_to_text_only_parallel_tool_calls():
    """N parallel tool calls in one ModelResponse paired with N returns in
    one ModelRequest: every call/return becomes plain text and no
    tool_call_id survives on either side. Pairing-by-id (already done in
    sanitize_orphaned_tool_calls) is therefore moot for this output.
    """
    history = [
        ModelRequest(parts=[UserPromptPart(content="run three things")]),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="a", args="{}", tool_call_id="c1"),
                ToolCallPart(tool_name="b", args="{}", tool_call_id="c2"),
                ToolCallPart(tool_name="c", args="{}", tool_call_id="c3"),
            ]
        ),
        # Returns intentionally NOT in call-order to exercise id-based reasoning
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="c", content="rc", tool_call_id="c3"),
                ToolReturnPart(tool_name="a", content="ra", tool_call_id="c1"),
                ToolReturnPart(tool_name="b", content="rb", tool_call_id="c2"),
            ]
        ),
    ]

    result = strip_to_text_only(history)

    # ModelResponse: three TextParts (one per call), no ToolCallParts remain.
    assert isinstance(result[1], ModelResponse)
    assert all(isinstance(p, TextPart) for p in result[1].parts)
    assert all(not hasattr(p, "tool_call_id") for p in result[1].parts)

    # ModelRequest: three UserPromptParts (one per return), no ToolReturnParts.
    assert isinstance(result[2], ModelRequest)
    assert all(isinstance(p, UserPromptPart) for p in result[2].parts)
    # UserPromptParts carry no tool_call_id, so no cross-reference survives.
    contents = [p.content for p in result[2].parts]
    assert all("(sanitized-history)" in c for c in contents)
    assert "c" in contents[0] and "rc" in contents[0]
    assert "a" in contents[1] and "ra" in contents[1]
    assert "b" in contents[2] and "rb" in contents[2]


def test_sanitize_history_chains_all_steps():
    """The orchestrator runs before EVERY model call; verify the three steps
    compose: nil content is patched, orphaned returns are stripped, complete
    tool pairs survive, and consecutive same-role messages are merged."""
    messages = [
        ModelResponse(
            parts=[
                TextPart(content="calling"),
                ToolCallPart(tool_name="x", args={}, tool_call_id="A"),
            ]
        ),
        ModelRequest(
            parts=[ToolReturnPart(content="result", tool_name="x", tool_call_id="A")]
        ),
        # Orphaned return (no matching call) — must be removed.
        ModelRequest(
            parts=[ToolReturnPart(content="orphan", tool_name="z", tool_call_id="Z")]
        ),
        # Nil content — must be patched, not dropped.
        ModelRequest(parts=[UserPromptPart(content="")]),
    ]

    result = sanitize_history(messages, allow_orphaned_tool_calls=False)

    # msg1 + msg3 (both ModelRequest, after the orphan msg2 is dropped) merge.
    assert len(result) == 2
    assert isinstance(result[0], ModelResponse)
    # Complete pair A survives the orphan sweep.
    call_ids = [getattr(p, "tool_call_id", None) for p in result[0].parts]
    assert "A" in call_ids
    # No orphaned return Z anywhere in the result.
    all_ids = [getattr(p, "tool_call_id", None) for msg in result for p in msg.parts]
    assert "Z" not in all_ids
    # The empty UserPromptPart was patched to a placeholder, not dropped.
    user_parts = [p for p in result[1].parts if isinstance(p, UserPromptPart)]
    assert len(user_parts) == 1
    assert user_parts[0].content == "(empty)"
    # And the complete pair's return is still present in the merged request.
    return_ids = [
        getattr(p, "tool_call_id", None)
        for p in result[1].parts
        if isinstance(p, ToolReturnPart)
    ]
    assert "A" in return_ids


def test_sanitize_history_allow_orphaned_tool_calls_keeps_pending_call():
    """With allow_orphaned_tool_calls=True (deferred-results path) a tool call
    with no return is legitimately pending and must be preserved."""
    messages = [
        ModelResponse(
            parts=[
                TextPart(content="t"),
                ToolCallPart(tool_name="x", args={}, tool_call_id="A"),
            ]
        ),
    ]

    kept = sanitize_history(messages, allow_orphaned_tool_calls=True)
    kept_call_ids = [
        getattr(p, "tool_call_id", None)
        for msg in kept
        for p in msg.parts
        if isinstance(p, ToolCallPart)
    ]
    assert "A" in kept_call_ids

    # Default path strips the orphaned call (it has no matching return).
    stripped = sanitize_history(messages, allow_orphaned_tool_calls=False)
    stripped_call_ids = [
        getattr(p, "tool_call_id", None)
        for msg in stripped
        for p in msg.parts
        if isinstance(p, ToolCallPart)
    ]
    assert "A" not in stripped_call_ids


def test_strip_thinking_parts_passes_through_non_response():
    """Messages that aren't ModelResponse are returned unchanged."""
    req = ModelRequest(parts=[UserPromptPart(content="hi")])
    unknown = UnknownMessage()

    result = strip_thinking_parts([req, unknown])

    assert result[0] is req
    assert result[1] is unknown


def test_strip_thinking_parts_removes_thinking_but_keeps_text():
    """ThinkingPart is stripped; an existing text part is preserved as-is."""
    msg = ModelResponse(
        parts=[ThinkingPart(content="reasoning"), TextPart(content="hello")]
    )

    result = strip_thinking_parts([msg])

    out = result[0]
    assert isinstance(out, ModelResponse)
    assert [type(p).__name__ for p in out.parts] == ["TextPart"]
    assert out.parts[0].content == "hello"


def test_strip_thinking_parts_injects_placeholder_when_all_parts_removed():
    """A thinking-only response becomes empty after stripping, so a
    '(tool call)' TextPart is injected to keep providers happy."""
    msg = ModelResponse(parts=[ThinkingPart(content="just thinking")])

    result = strip_thinking_parts([msg])

    out = result[0]
    assert len(out.parts) == 1
    assert isinstance(out.parts[0], TextPart)
    assert out.parts[0].content == TOOL_CALL_PLACEHOLDER


def test_strip_thinking_parts_injects_placeholder_when_only_tool_calls_remain():
    """After stripping thinking, a tool-call-only response has no text part, so
    a leading '(tool call)' TextPart is inserted."""
    msg = ModelResponse(
        parts=[
            ThinkingPart(content="reasoning"),
            ToolCallPart(tool_name="x", args="{}", tool_call_id="c1"),
        ]
    )

    result = strip_thinking_parts([msg])

    out = result[0]
    assert [type(p).__name__ for p in out.parts] == ["TextPart", "ToolCallPart"]
    assert out.parts[0].content == TOOL_CALL_PLACEHOLDER


def test_sanitize_history_debug_logging_detects_problems():
    """With DEBUG logging enabled, sanitize_history runs _detect_problems over
    the pre-fix history: messages with no parts, nil-content parts, text-less
    ModelResponses, and consecutive same-role messages are all detected and
    logged, then the fix pipeline still returns a valid list."""
    import logging as _logging

    from zrb.config.config import CFG

    messages = [
        # No parts at all — triggers the "has no parts" detection.
        ModelResponse(parts=[]),
        # Nil-content thinking-only response: nil content + no-text/no-tool +
        # consecutive-same-role (two ModelResponses in a row) all detected.
        ModelResponse(parts=[ThinkingPart(content=None)]),
        # Orphaned tool return so validate_tool_pair_integrity yields problems.
        ModelRequest(
            parts=[ToolReturnPart(tool_name="z", content="x", tool_call_id="Z")]
        ),
    ]

    prev_level = CFG.LOGGER.level
    CFG.LOGGER.setLevel(_logging.DEBUG)
    try:
        result = sanitize_history(messages, allow_orphaned_tool_calls=False)
    finally:
        CFG.LOGGER.setLevel(prev_level)

    assert isinstance(result, list)


def test_strip_to_text_only_native_tool_return_in_response():
    """A BaseToolReturnPart (NativeToolReturnPart) inside a ModelResponse is
    converted to a sanitized-history TextPart."""
    history = [
        ModelResponse(
            parts=[
                NativeToolReturnPart(
                    tool_name="web_search", content="hits", tool_call_id="c1"
                )
            ]
        )
    ]

    result = strip_to_text_only(history)

    out = result[0]
    assert isinstance(out, ModelResponse)
    assert isinstance(out.parts[0], TextPart)
    assert "(sanitized-history)" in out.parts[0].content
    assert "web_search" in out.parts[0].content
    assert "hits" in out.parts[0].content


def test_strip_to_text_only_unknown_request_part_passes_through():
    """A part in a ModelRequest that is not a tool-return / retry / user /
    system part falls through unchanged (the `return part` branch)."""
    text_part = TextPart(content="stray")
    history = [ModelRequest(parts=[text_part])]

    result = strip_to_text_only(history)

    assert isinstance(result[0], ModelRequest)
    assert result[0].parts[0] is text_part


def test_strip_to_text_only_native_tool_call_yields_placeholder():
    """A NativeToolCallPart (BaseToolCallPart but not ToolCallPart) converts to
    an empty text label, leaving the ModelResponse text-less, so a leading
    '(tool call)' placeholder is injected."""
    history = [
        ModelResponse(parts=[NativeToolCallPart(tool_name="web_search", args="{}")])
    ]

    result = strip_to_text_only(history)

    out = result[0]
    assert isinstance(out, ModelResponse)
    assert out.parts[0].content == TOOL_CALL_PLACEHOLDER


def test_strip_to_text_only_passes_through_unknown_message():
    """A message that is neither ModelRequest nor ModelResponse is kept as-is."""
    unknown = UnknownMessage()
    history = [ModelResponse(parts=[TextPart(content="ok")]), unknown]

    result = strip_to_text_only(history)

    assert result[1] is unknown


def test_strip_to_text_only_empty_request_returns_original():
    """When every message drops to no parts (an empty ModelRequest), the result
    would be empty, so the original history is returned untouched."""
    history = [ModelRequest(parts=[])]

    result = strip_to_text_only(history)

    assert result is history


def test_strip_to_text_only_truncates_long_tool_return():
    """A tool-return longer than the max is truncated with a trailing ellipsis."""
    long_content = "R" * 700
    history = [
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="big", content=long_content, tool_call_id="c1")
            ]
        )
    ]

    result = strip_to_text_only(history)

    text = result[0].parts[0].content
    assert isinstance(result[0].parts[0], UserPromptPart)
    assert text.endswith("...")
    assert "R" * 500 in text
    assert "R" * 700 not in text


def test_close_dangling_tool_calls_synthesizes_returns():
    """A trailing ModelResponse with unresolved tool calls gets a matching
    ModelRequest of synthetic ToolReturnParts appended, one per call."""
    history = [
        ModelRequest(parts=[UserPromptPart(content="do two things")]),
        ModelResponse(
            parts=[
                ToolCallPart(tool_name="a", args="{}", tool_call_id="c1"),
                ToolCallPart(tool_name="b", args="{}", tool_call_id="c2"),
            ]
        ),
    ]

    result = close_dangling_tool_calls(history, reason="[SYSTEM] Interrupted.")

    assert len(result) == 3
    closing = result[2]
    assert isinstance(closing, ModelRequest)
    assert len(closing.parts) == 2
    assert all(isinstance(p, ToolReturnPart) for p in closing.parts)
    assert {p.tool_call_id for p in closing.parts} == {"c1", "c2"}
    assert all(p.content == "[SYSTEM] Interrupted." for p in closing.parts)


def test_close_dangling_tool_calls_noop_on_complete_history():
    """A history ending in a ModelRequest (no dangling call) is returned as-is."""
    history = [
        ModelRequest(parts=[UserPromptPart(content="hi")]),
        ModelResponse(parts=[TextPart(content="hello")]),
    ]

    result = close_dangling_tool_calls(history, reason="ignored")

    assert result is history


def test_close_dangling_tool_calls_noop_on_empty_history():
    assert close_dangling_tool_calls([], reason="ignored") == []


def test_close_dangling_tool_calls_noop_when_response_has_no_tool_calls():
    """A trailing ModelResponse with only text has nothing to close."""
    history = [ModelResponse(parts=[TextPart(content="just text")])]

    result = close_dangling_tool_calls(history, reason="ignored")

    assert result is history


def test_strip_to_text_only_truncates_long_retry_prompt():
    """A tool-linked RetryPromptPart with an oversized content is collapsed to a
    UserPromptPart and truncated with an ellipsis."""
    from pydantic_ai.messages import RetryPromptPart

    long_content = "E" * 700
    history = [
        ModelRequest(
            parts=[
                RetryPromptPart(
                    content=long_content, tool_name="bad_tool", tool_call_id="c1"
                )
            ]
        )
    ]

    result = strip_to_text_only(history)

    out_part = result[0].parts[0]
    assert isinstance(out_part, UserPromptPart)
    text = out_part.content
    assert "(sanitized-history)" in text
    assert "bad_tool" in text
    assert text.endswith("...")
    assert "E" * 700 not in text
