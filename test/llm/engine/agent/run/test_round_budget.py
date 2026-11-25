"""The round-boundary probe records what the trigger would have seen, and nothing else.

No test here asserts that anything was compacted or masked: the probe is a dry
run, and these cases pin the numbers a later rule would be decided on — how many
calls the turn had already made, what the trigger would have compared, and what
masking the old results would have to be paid for.
"""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.contracts.config.limiter import LLMLimiter
from zrb.llm.engine.agent.run.round_budget import (
    MASK_AGE_MESSAGES,
    measure_round_budget,
)


def _user(text: str = "hello") -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _reply(text: str = "ok") -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=text)])


def _tool_result(body: str, call_id: str = "c1") -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart(tool_name="Read", content=body, tool_call_id=call_id)]
    )


def _measure(history, **overrides):
    """A probe under a small, readable budget: 1,000 tokens, 100 of them prompt."""
    fields = dict(
        requests_before=0,
        trigger_tokens=1_000,
        system_tokens=100,
        message_window=300,
    )
    fields.update(overrides)
    return measure_round_budget(history, LLMLimiter(), **fields)


def test_a_short_history_is_under_the_trigger():
    history = [_user("hi"), _reply()]
    limiter = LLMLimiter()

    budget = _measure(history)

    assert budget.history_tokens == limiter.count_tokens(history)
    assert budget.messages == 2
    assert budget.allowed_tokens == 900
    assert budget.is_over_trigger is False
    assert budget.requests_before == 0


def test_the_system_prompt_counts_against_the_allowance():
    """The trigger subtracts the prompt it will send; a probe that did not would
    report a crossing several thousand tokens early."""
    history = [_user("x" * 3_600)]

    budget = _measure(history, trigger_tokens=1_000, system_tokens=400)

    assert budget.allowed_tokens == 600
    assert budget.history_tokens > 600
    assert budget.is_over_trigger is True


def test_the_message_window_alone_crosses():
    """The trigger answers two limits, and a history can be under the token
    threshold and over the window at once."""
    budget = _measure([_user(), _reply(), _user()], message_window=2)

    assert budget.is_over_trigger is True


def test_the_allowance_never_goes_below_one():
    """A prompt larger than the threshold leaves a one-token allowance, which is
    what `_maybe_compress_history` measures against."""
    budget = _measure([_user()], trigger_tokens=100, system_tokens=500)

    assert budget.allowed_tokens == 1


def test_tool_results_older_than_the_window_are_measured():
    opening = _user()
    old = [_tool_result("A" * 4_000, f"old{index}") for index in range(3)]
    filler = [_reply() for _ in range(MASK_AGE_MESSAGES)]
    recent = [_tool_result("B" * 4_000, "recent")]
    history = [opening, *old, *filler, *recent]
    limiter = LLMLimiter()

    budget = measure_round_budget(
        history,
        limiter,
        requests_before=12,
        trigger_tokens=200_000,
        system_tokens=5_000,
        message_window=300,
    )

    assert budget.tool_tokens == sum(limiter.count_content_tokens(msg) for msg in old)
    # The oldest maskable result is the first of the three, so a mask rewrites
    # everything from it on: that is what the send would pay again.
    assert budget.mask_resend_tokens == limiter.count_content_tokens(history[1:])
    assert budget.requests_before == 12


def test_a_result_inside_the_window_is_not_measured():
    """The newest results are the ones a turn is still working from."""
    history = [
        _user(),
        *[_reply() for _ in range(MASK_AGE_MESSAGES)],
        _tool_result("B" * 4_000),
    ]

    budget = _measure(history)

    assert budget.tool_tokens == 0
    assert budget.mask_resend_tokens == 0


def test_the_pending_guard_and_the_wait_are_carried():
    budget = _measure([_user()], is_result_pending=True, gap_seconds=17.5)

    assert budget.is_result_pending is True
    assert budget.gap_seconds == pytest.approx(17.5)


def test_a_first_round_has_no_wait_behind_it():
    assert _measure([_user()]).gap_seconds is None
