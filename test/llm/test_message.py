from datetime import datetime

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.message import (
    ensure_alternating_roles,
    get_tool_pairs,
    validate_tool_pair_integrity,
)


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


# ── get_tool_pairs ─────────────────────────────────────────────────────────────


def test_get_tool_pairs_basic_call_and_return():
    """ToolCallPart followed by ToolReturnPart produces a paired entry."""
    call_part = ToolCallPart(tool_name="my_tool", args={}, tool_call_id="id-1")
    return_part = ToolReturnPart(tool_name="my_tool", content="ok", tool_call_id="id-1")

    req = ModelRequest(parts=[return_part])
    res = ModelResponse(parts=[call_part], timestamp=datetime.now())

    pairs = get_tool_pairs([res, req])

    assert "id-1" in pairs
    assert pairs["id-1"]["call_idx"] == 0
    assert pairs["id-1"]["return_idx"] == 1


def test_get_tool_pairs_return_before_call():
    """When a ToolReturnPart is seen before its ToolCallPart the entry still records both."""
    call_part = ToolCallPart(tool_name="my_tool", args={}, tool_call_id="id-2")
    return_part = ToolReturnPart(tool_name="my_tool", content="ok", tool_call_id="id-2")

    # Return message comes first (index 0), call message second (index 1)
    req = ModelRequest(parts=[return_part])
    res = ModelResponse(parts=[call_part], timestamp=datetime.now())

    pairs = get_tool_pairs([req, res])

    assert "id-2" in pairs
    # call_idx updated to 1 when call seen after return
    assert pairs["id-2"]["call_idx"] == 1
    assert pairs["id-2"]["return_idx"] == 0


def test_get_tool_pairs_message_without_parts():
    """Messages that raise AttributeError on .parts are skipped gracefully (lines 60, 62)."""

    class BadMessage:
        @property
        def parts(self):
            raise AttributeError("no parts")

    bad = BadMessage()
    call_part = ToolCallPart(tool_name="t", args={}, tool_call_id="id-3")
    res = ModelResponse(parts=[call_part], timestamp=datetime.now())

    pairs = get_tool_pairs([bad, res])

    assert "id-3" in pairs
    assert pairs["id-3"]["call_idx"] == 1


# ── validate_tool_pair_integrity ───────────────────────────────────────────────


def test_validate_tool_pair_integrity_valid():
    """All calls have matching returns — should be valid with no problems."""
    call_part = ToolCallPart(tool_name="t", args={}, tool_call_id="id-10")
    return_part = ToolReturnPart(tool_name="t", content="res", tool_call_id="id-10")

    res = ModelResponse(parts=[call_part], timestamp=datetime.now())
    req = ModelRequest(parts=[return_part])

    is_valid, problems = validate_tool_pair_integrity([res, req])

    assert is_valid is True
    assert problems == []


def test_validate_tool_pair_integrity_orphaned_call():
    """A call without a matching return should be reported as a problem (lines 119-129)."""
    call_part = ToolCallPart(tool_name="t", args={}, tool_call_id="id-11")

    res = ModelResponse(parts=[call_part], timestamp=datetime.now())

    is_valid, problems = validate_tool_pair_integrity([res])

    assert is_valid is False
    assert any("id-11" in p for p in problems)


def test_validate_tool_pair_integrity_orphaned_return():
    """A return without a matching call should be reported as a problem (lines 135-136)."""
    return_part = ToolReturnPart(tool_name="t", content="res", tool_call_id="id-12")

    req = ModelRequest(parts=[return_part])

    is_valid, problems = validate_tool_pair_integrity([req])

    assert is_valid is False
    assert any("id-12" in p for p in problems)
