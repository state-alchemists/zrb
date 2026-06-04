import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.retry_loop import RetryOutcome, RetryState, handle_stream_error


@pytest.mark.asyncio
async def test_handle_stream_error_transient():
    state = RetryState(transient_retry_count=0, max_transient_retries=2)
    exc = Exception("Rate limit")
    exc.status_code = 429
    current_history = ["msg1"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        outcome = await handle_stream_error(
            state, exc, current_history, current_message, run_history, print_fn
        )

    assert outcome.should_retry is True
    assert state.transient_retry_count == 1
    assert outcome.new_history == current_history
    assert outcome.new_message == current_message
    mock_sleep.assert_called_once()
    print_fn.assert_called()


@pytest.mark.asyncio
async def test_handle_stream_error_prompt_too_long():
    # We need to mock drop_oldest_turn
    state = RetryState(context_retry_count=0, max_context_retries=2)
    exc = Exception("Prompt too long")
    current_history = ["turn1_user", "turn1_model", "turn2_user"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    with patch(
        "zrb.llm.agent.run.retry_loop.drop_oldest_turn", return_value=["turn2_user"]
    ) as mock_drop:
        outcome = await handle_stream_error(
            state, exc, current_history, current_message, run_history, print_fn
        )

    assert outcome.should_retry is True
    assert state.context_retry_count == 1
    assert outcome.new_history == ["turn2_user"]
    mock_drop.assert_called_once_with(current_history, min_turns=0)
    print_fn.assert_called()


@pytest.mark.asyncio
async def test_prompt_too_long_does_not_reset_transient_counter():
    """A context-length prune must NOT refresh the transient (429/5xx)
    budget. The transient cap is global across the whole run."""
    state = RetryState(
        context_retry_count=0,
        max_context_retries=2,
        transient_retry_count=2,
        max_transient_retries=3,
    )
    exc = Exception("Prompt too long")
    print_fn = MagicMock()

    with patch(
        "zrb.llm.agent.run.retry_loop.drop_oldest_turn", return_value=["turn2_user"]
    ):
        outcome = await handle_stream_error(
            state, exc, ["a", "b"], "hello", [], print_fn
        )

    assert outcome.should_retry is True
    assert state.context_retry_count == 1
    # The transient counter is preserved, not zeroed.
    assert state.transient_retry_count == 2


@pytest.mark.asyncio
async def test_handle_stream_error_invalid_tool_call_with_string_message():
    state = RetryState(invalid_tool_retry_done=False)
    exc = Exception("Unknown tool")
    exc.status_code = 400
    current_history = ["msg1"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    outcome = await handle_stream_error(
        state, exc, current_history, current_message, run_history, print_fn
    )

    assert outcome.should_retry is True
    assert state.invalid_tool_retry_done is True
    assert "⛔ STOP" in outcome.new_message
    assert "BROKEN" in outcome.new_message
    assert outcome.new_message.startswith("hello")
    print_fn.assert_called()


@pytest.mark.asyncio
async def test_handle_stream_error_invalid_tool_call_includes_name_from_body():
    """When the exception body names the bad tool, the corrective quotes it."""
    state = RetryState(invalid_tool_retry_done=False)
    exc = Exception("body unused")
    exc.status_code = 400
    exc.body = {"message": "Unknown tool name: 'ReadReadRead'."}
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, ["msg"], "hello", [], print_fn)

    assert "`ReadReadRead`" in outcome.new_message


@pytest.mark.asyncio
async def test_handle_stream_error_invalid_tool_call_includes_name_from_history():
    """For providers whose body is generic, scan history for the wrapper's
    'Unknown tool name: X' rejection text."""
    state = RetryState(invalid_tool_retry_done=False)
    exc = Exception("body unused")
    exc.status_code = 400
    exc.body = {"message": "invalid tool call arguments"}  # generic — minimax/glm-style

    # Synthetic history entry — only the parts/content shape matters.
    class _Part:
        def __init__(self, content):
            self.content = content

    class _Msg:
        def __init__(self, parts):
            self.parts = parts

    history = [
        _Msg(
            [
                _Part(
                    "Return Unknown tool name: 'ActivateSkillReadRead'. Available tools: ..."
                )
            ]
        )
    ]
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, history, "hello", [], print_fn)

    assert "`ActivateSkillReadRead`" in outcome.new_message


@pytest.mark.asyncio
async def test_handle_stream_error_invalid_tool_call_without_string_message():
    state = RetryState(invalid_tool_retry_done=False)
    exc = Exception("Unknown tool")
    exc.status_code = 400
    current_history = ["msg1"]
    current_message = None
    run_history = ["msg0"]
    print_fn = MagicMock()

    # We need to mock ModelRequest and UserPromptPart
    with patch("pydantic_ai.messages.ModelRequest") as mock_req, patch(
        "pydantic_ai.messages.UserPromptPart"
    ) as mock_part:

        outcome = await handle_stream_error(
            state, exc, current_history, current_message, run_history, print_fn
        )

    assert outcome.should_retry is True
    assert state.invalid_tool_retry_done is True
    assert outcome.new_message is None
    assert len(outcome.new_history) == 2
    assert outcome.new_history[0] == "msg0"
    mock_part.assert_called_once()
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stream_error_opaque_400():
    """Unclassified 400 with current_message fires opaque retry, preserves
    current_message, and appends a sanitization explainer to history."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    state = RetryState(opaque_retry_done=False)
    exc = Exception("Bad request")
    exc.status_code = 400
    current_history = ["msg1", "msg2"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    outcome = await handle_stream_error(
        state, exc, current_history, current_message, run_history, print_fn
    )

    assert outcome.should_retry is True
    assert state.opaque_retry_done is True
    assert outcome.new_message == "hello"
    print_fn.assert_called()
    # Explainer ModelRequest appended after sanitized history.
    assert len(outcome.new_history) == 3
    explainer = outcome.new_history[-1]
    assert isinstance(explainer, ModelRequest)
    assert isinstance(explainer.parts[0], UserPromptPart)
    text = explainer.parts[0].content
    assert "(sanitized-history)" in text
    assert "tool-calling" in text


@pytest.mark.asyncio
async def test_handle_stream_error_opaque_400_only_once():
    """Second unclassified 400 with same state does NOT retry."""
    state = RetryState(opaque_retry_done=True)
    exc = Exception("Bad request")
    exc.status_code = 400
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, ["msg1"], "hello", [], print_fn)

    assert outcome.should_retry is False


@pytest.mark.asyncio
async def test_handle_stream_error_opaque_400_with_no_message():
    """Opaque 400 with current_message=None fires retry and injects the
    sanitization explainer as the next user-role message.

    During tool-call iterations and outer-retry resume the user message is
    often merged into history (making current_message None). The handler
    always appends the explainer ModelRequest so the model sees what was
    sanitized and that tool use is still expected.
    """
    state = RetryState(opaque_retry_done=False)
    exc = Exception("Bad request")
    exc.status_code = 400
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, ["msg1"], None, [], print_fn)

    assert outcome.should_retry is True
    assert state.opaque_retry_done is True
    assert outcome.new_message is None  # explainer baked into history
    assert len(outcome.new_history) == 2
    # The explainer was injected as a ModelRequest with a UserPromptPart
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    injected = outcome.new_history[1]
    assert isinstance(injected, ModelRequest)
    assert isinstance(injected.parts[0], UserPromptPart)
    text = injected.parts[0].content
    assert "(sanitized-history)" in text
    assert "tool-calling" in text


@pytest.mark.asyncio
async def test_handle_stream_error_opaque_400_skipped_for_non_400():
    """Opaque retry only fires for status 400."""
    state = RetryState(opaque_retry_done=False)
    exc = Exception("Not found")
    exc.status_code = 404
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, ["msg1"], "hello", [], print_fn)

    assert outcome.should_retry is False


@pytest.mark.asyncio
async def test_handle_stream_error_no_retry():
    state = RetryState(transient_retry_count=10, max_transient_retries=2)
    exc = Exception("Rate limit")
    exc.status_code = 429
    current_history = ["msg1"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    outcome = await handle_stream_error(
        state, exc, current_history, current_message, run_history, print_fn
    )

    assert outcome.should_retry is False


@pytest.mark.asyncio
async def test_handle_stream_error_unknown_exception():
    state = RetryState()
    exc = Exception("Something went wrong")
    current_history = ["msg1"]
    current_message = "hello"
    run_history = []
    print_fn = MagicMock()

    outcome = await handle_stream_error(
        state, exc, current_history, current_message, run_history, print_fn
    )

    assert outcome.should_retry is False


@pytest.mark.asyncio
async def test_handle_stream_error_deferred_mismatch():
    """UserError about unprocessed tool calls retries with intact run_history."""
    from pydantic_ai.exceptions import UserError as PydanticUserError

    state = RetryState(deferred_mismatch_retry_done=False)
    exc = PydanticUserError(
        "Tool call results were provided, but the message history "
        "does not contain any unprocessed tool calls."
    )
    run_history = ["intact-message"]
    print_fn = MagicMock()

    outcome = await handle_stream_error(
        state, exc, [], None, run_history, print_fn
    )

    assert outcome.should_retry is True
    assert outcome.clear_results is True
    # Must hand back the intact history, not None — the runner feeds
    # new_history straight into sanitize_history, which raises on None.
    assert outcome.new_history == run_history
    assert outcome.new_message is None
    assert state.deferred_mismatch_retry_done is True
    print_fn.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stream_error_deferred_mismatch_only_once():
    """Second UserError with deferred_mismatch_retry_done=True does NOT retry."""
    from pydantic_ai.exceptions import UserError as PydanticUserError

    state = RetryState(deferred_mismatch_retry_done=True)
    exc = PydanticUserError("message history does not contain any unprocessed tool calls")
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, [], None, [], print_fn)

    assert outcome.should_retry is False
    print_fn.assert_not_called()


@pytest.mark.asyncio
async def test_handle_stream_error_user_error_other_message():
    """Non-matching UserError is not caught by deferred mismatch handler."""
    from pydantic_ai.exceptions import UserError as PydanticUserError

    state = RetryState()
    exc = PydanticUserError("Some other user error")
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, [], None, [], print_fn)

    assert outcome.should_retry is False
    print_fn.assert_not_called()
