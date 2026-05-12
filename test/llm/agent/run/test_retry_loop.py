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
    assert "Your previous response was rejected" in outcome.new_message
    assert outcome.new_message.startswith("hello")
    print_fn.assert_called()


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
    """Unclassified 400 with current_message fires opaque retry."""
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
    """Opaque 400 with current_message=None fires retry + injects fallback prompt.

    Previously this was skipped because ``current_message is not None`` guarded the
    handler, but during tool-call iterations and outer-retry resume the user message
    is often merged into history (making current_message None). The handler now
    injects a fallback prompt into the text-only history as a replacement user message.
    """
    state = RetryState(opaque_retry_done=False)
    exc = Exception("Bad request")
    exc.status_code = 400
    print_fn = MagicMock()

    outcome = await handle_stream_error(state, exc, ["msg1"], None, [], print_fn)

    assert outcome.should_retry is True
    assert state.opaque_retry_done is True
    assert outcome.new_message is None  # fallback baked into history
    assert len(outcome.new_history) == 2
    # The fallback prompt was injected as a ModelRequest with a UserPromptPart
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    injected = outcome.new_history[1]
    assert isinstance(injected, ModelRequest)
    assert isinstance(injected.parts[0], UserPromptPart)
    assert "plain-text" in injected.parts[0].content


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
