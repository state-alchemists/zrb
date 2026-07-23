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
    TOOL_CALL_PLACEHOLDER,
    ensure_alternating_roles,
    get_tool_pairs,
    sanitize_orphaned_tool_calls,
    strip_orphaned_returns,
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


def test_alternating_roles_request_merge_preserves_metadata():
    # Merging must keep non-part fields (instructions, ...) of the kept
    # request — a freshly constructed ModelRequest would drop them.
    req1 = ModelRequest(parts=[UserPromptPart(content="Hello")], instructions="sys")
    req2 = ModelRequest(parts=[UserPromptPart(content="World")])

    result = ensure_alternating_roles([req1, req2])

    assert len(result) == 1
    assert result[0].instructions == "sys"
    assert len(result[0].parts) == 2


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


# ── sanitize_orphaned_tool_calls ────────────────────────────────────────────────


def test_sanitize_orphaned_tool_calls_no_orphans_returns_input():
    """When every call has a matching return, the original list is returned as-is."""
    call_part = ToolCallPart(tool_name="t", args={}, tool_call_id="id-20")
    return_part = ToolReturnPart(tool_name="t", content="res", tool_call_id="id-20")
    res = ModelResponse(parts=[call_part], timestamp=datetime.now())
    req = ModelRequest(parts=[return_part])
    messages = [res, req]

    result = sanitize_orphaned_tool_calls(messages)

    assert result is messages


def test_sanitize_orphaned_tool_calls_strips_orphaned_call_and_inserts_placeholder():
    """An orphaned ToolCallPart is removed; a then text-less response gets a placeholder.

    The response keeps a *paired* call so it does not collapse to empty, but has
    no TextPart — so stripping the orphan must trigger the placeholder insertion.
    """
    orphan_call = ToolCallPart(tool_name="t", args={}, tool_call_id="orphan-call")
    paired_call = ToolCallPart(tool_name="t", args={}, tool_call_id="paired")
    paired_return = ToolReturnPart(tool_name="t", content="x", tool_call_id="paired")
    res = ModelResponse(parts=[orphan_call, paired_call], timestamp=datetime.now())
    req = ModelRequest(parts=[paired_return])

    result = sanitize_orphaned_tool_calls([res, req])

    parts = result[0].parts
    # Orphaned call removed, paired call kept, placeholder text part prepended.
    assert all(
        not (isinstance(p, ToolCallPart) and p.tool_call_id == "orphan-call")
        for p in parts
    )
    assert any(
        isinstance(p, ToolCallPart) and p.tool_call_id == "paired" for p in parts
    )
    assert any(
        isinstance(p, TextPart) and p.content == TOOL_CALL_PLACEHOLDER for p in parts
    )


def test_sanitize_orphaned_tool_calls_drops_empty_response():
    """A response containing only orphaned calls (no need for text) collapses to None and is dropped."""
    orphan_call = ToolCallPart(tool_name="t", args={}, tool_call_id="o1")
    # Two orphaned calls in one response; once stripped the message is empty and dropped.
    res = ModelResponse(
        parts=[
            ToolCallPart(tool_name="t", args={}, tool_call_id="o1"),
            orphan_call,
        ],
        timestamp=datetime.now(),
    )
    # A valid pair so the function does not early-return.
    paired_call = ToolCallPart(tool_name="t", args={}, tool_call_id="paired")
    paired_return = ToolReturnPart(tool_name="t", content="x", tool_call_id="paired")
    res2 = ModelResponse(parts=[paired_call], timestamp=datetime.now())
    req2 = ModelRequest(parts=[paired_return])

    result = sanitize_orphaned_tool_calls([res, res2, req2])

    # The all-orphan response is dropped entirely.
    assert res not in result
    assert res2 in result
    assert req2 in result


def test_sanitize_orphaned_tool_calls_strips_orphaned_return():
    """An orphaned ToolReturnPart in a ModelRequest is stripped."""
    orphan_return = ToolReturnPart(
        tool_name="t", content="r", tool_call_id="orphan-ret"
    )
    user = UserPromptPart(content="hi")
    req = ModelRequest(parts=[orphan_return, user])
    # Add a valid pair so the function proceeds past the early-return guard.
    paired_call = ToolCallPart(tool_name="t", args={}, tool_call_id="p2")
    paired_return = ToolReturnPart(tool_name="t", content="x", tool_call_id="p2")
    res = ModelResponse(parts=[paired_call], timestamp=datetime.now())
    req_ret = ModelRequest(parts=[paired_return])

    result = sanitize_orphaned_tool_calls([req, res, req_ret])

    # The orphaned return is gone but the user prompt survives.
    surviving_req = result[0]
    assert all(
        not (isinstance(p, ToolReturnPart) and p.tool_call_id == "orphan-ret")
        for p in surviving_req.parts
    )
    assert any(isinstance(p, UserPromptPart) for p in surviving_req.parts)


# ── strip_orphaned_returns ──────────────────────────────────────────────────────


def test_strip_orphaned_returns_no_orphans_returns_input():
    """With no orphaned returns the input list is returned unchanged."""
    call_part = ToolCallPart(tool_name="t", args={}, tool_call_id="id-30")
    return_part = ToolReturnPart(tool_name="t", content="res", tool_call_id="id-30")
    res = ModelResponse(parts=[call_part], timestamp=datetime.now())
    req = ModelRequest(parts=[return_part])
    messages = [res, req]

    result = strip_orphaned_returns(messages)

    assert result is messages


def test_strip_orphaned_returns_strips_return_keeps_orphaned_call():
    """Orphaned returns are removed but orphaned calls (pending deferred) are kept."""
    orphan_return = ToolReturnPart(tool_name="t", content="r", tool_call_id="dropped")
    orphan_call = ToolCallPart(tool_name="t", args={}, tool_call_id="pending")
    req = ModelRequest(parts=[orphan_return, UserPromptPart(content="hi")])
    res = ModelResponse(parts=[orphan_call], timestamp=datetime.now())

    result = strip_orphaned_returns([req, res])

    # The orphaned return is stripped from the request.
    surviving_req = result[0]
    assert all(
        not (isinstance(p, ToolReturnPart) and p.tool_call_id == "dropped")
        for p in surviving_req.parts
    )
    # The orphaned call survives untouched (it may be a pending deferred result).
    surviving_res = result[1]
    assert any(
        isinstance(p, ToolCallPart) and p.tool_call_id == "pending"
        for p in surviving_res.parts
    )


def test_strip_orphaned_returns_drops_emptied_request():
    """A request that becomes empty after stripping its only (orphaned) return is dropped."""
    orphan_return = ToolReturnPart(tool_name="t", content="r", tool_call_id="solo")
    req = ModelRequest(parts=[orphan_return])

    result = strip_orphaned_returns([req])

    assert result == []


def _retry_part(tool_call_id: str, tool_name: str | None = "t"):
    from pydantic_ai.messages import RetryPromptPart

    return RetryPromptPart(
        content="validation failed", tool_name=tool_name, tool_call_id=tool_call_id
    )


def test_retry_answered_call_is_a_complete_pair():
    """A ToolCallPart answered by a tool-linked RetryPromptPart is NOT orphaned.

    Providers serialize the retry as the tool-role response, so sanitizing must
    keep both sides; deleting the call while keeping the retry produces a
    dangling tool message that providers reject with 400.
    """
    call = ModelResponse(
        parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="x1")],
        timestamp=datetime.now(),
    )
    retry = ModelRequest(parts=[_retry_part("x1")])
    answer = ModelResponse(parts=[TextPart(content="ok")], timestamp=datetime.now())
    messages = [call, retry, answer]

    pairs = get_tool_pairs(messages)
    assert pairs["x1"] == {"call_idx": 0, "return_idx": 1}

    is_valid, problems = validate_tool_pair_integrity(messages)
    assert is_valid, problems

    assert sanitize_orphaned_tool_calls(messages) == messages
    assert strip_orphaned_returns(messages) == messages


def test_orphaned_tool_retry_is_stripped():
    """A tool-linked RetryPromptPart whose call was summarized away is removed."""
    req = ModelRequest(parts=[_retry_part("gone"), UserPromptPart(content="hi")])

    for fn in (sanitize_orphaned_tool_calls, strip_orphaned_returns):
        result = fn([req])
        assert len(result) == 1
        assert [type(p).__name__ for p in result[0].parts] == ["UserPromptPart"]


def test_tool_less_retry_is_ignored_by_pairing():
    """A RetryPromptPart without tool_name maps to a user message: despite its
    auto-generated tool_call_id it must not register as a tool return nor be
    stripped as an orphan."""
    req = ModelRequest(parts=[_retry_part("auto-id", tool_name=None)])

    assert get_tool_pairs([req]) == {}
    assert sanitize_orphaned_tool_calls([req]) == [req]
    assert strip_orphaned_returns([req]) == [req]
