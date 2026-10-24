"""`history_through_deferred_returns` against the shapes history has taken.

The function decides how far a resumed round got, by looking for a return of one
of the deferred calls. A history written before pydantic-ai 2.60 holds that
answer as the deprecated `RetryPromptPart`, and missing it makes the runner
execute a tool it already ran.
"""

from datetime import datetime

from pydantic_ai import DeferredToolResults
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart

from zrb.llm.agent.run.history_utils import history_through_deferred_returns


def _call(tool_call_id: str) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="t", args={}, tool_call_id=tool_call_id)],
        timestamp=datetime.now(),
    )


def _legacy_retry(tool_call_id: str) -> ModelRequest:
    # lazy: heavy third-party -- pydantic_ai (the deprecated class under test)
    from pydantic_ai.messages import RetryPromptPart

    return ModelRequest(
        parts=[
            RetryPromptPart(content="bad", tool_name="t", tool_call_id=tool_call_id)
        ]
    )


def _results(tool_call_id: str) -> DeferredToolResults:
    return DeferredToolResults(approvals={tool_call_id: True})


def test_a_legacy_retry_part_is_a_deferred_call_s_answer():
    """Before pydantic-ai 2.60 the answer was a `RetryPromptPart`; not
    recognizing it returns None, so the runner never commits a round that ran."""
    messages = [_call("d1"), _legacy_retry("d1")]

    assert history_through_deferred_returns(messages, _results("d1")) == messages


def test_no_answer_yet_returns_none():
    messages = [_call("d1")]

    assert history_through_deferred_returns(messages, _results("d1")) is None
