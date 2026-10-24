"""Tool pairing against history written before pydantic-ai 2.60.

A retry used to be one part, `RetryPromptPart`, for both cases: one that answers
a tool call and one that answers nothing. Pairing has to keep telling them
apart — a tool that answers no call is not a return, and a return that answers a
call must not be stripped as an orphan — while recognizing the part by its kind,
never by importing the deprecated class.
"""

from datetime import datetime

from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart

from zrb.llm.message import (
    get_tool_pairs,
    sanitize_orphaned_tool_calls,
    strip_orphaned_returns,
)


def test_a_legacy_retry_part_still_completes_its_pair():
    """The call it answers must not be stripped as orphaned — that leaves the
    retry dangling, which providers reject with a 400."""
    # lazy: heavy third-party -- pydantic_ai (the deprecated class under test)
    from pydantic_ai.messages import RetryPromptPart

    call = ModelResponse(
        parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="x1")],
        timestamp=datetime.now(),
    )
    retry = ModelRequest(
        parts=[RetryPromptPart(content="bad", tool_name="t", tool_call_id="x1")]
    )

    assert get_tool_pairs([call, retry]) == {"x1": {"call_idx": 0, "return_idx": 1}}
    for sanitize in (sanitize_orphaned_tool_calls, strip_orphaned_returns):
        assert sanitize([call, retry]) == [call, retry]


def test_a_legacy_tool_less_retry_is_not_a_tool_return():
    """pydantic-ai generates a `tool_call_id` for a tool-less retry, so the id
    cannot be what identifies a return: this part answers no call, and pairing
    must ignore it — as the pre-2.60 code did by requiring a `tool_name`."""
    # lazy: heavy third-party -- pydantic_ai (the deprecated class under test)
    from pydantic_ai.messages import RetryPromptPart

    part = RetryPromptPart(content="validation failed")
    req = ModelRequest(parts=[part])

    assert get_tool_pairs([req]) == {}
    assert sanitize_orphaned_tool_calls([req]) == [req]
    assert strip_orphaned_returns([req]) == [req]
