import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.runner.chat.chat_session_manager import ChatSession
from zrb.runner.chat.chat_session_runner import run_chat_session


@pytest.fixture
def mock_deps():
    session = MagicMock(spec=ChatSession)
    session.session_id = "test-id"
    session.session_name = "test-name"
    session.approval_channel = MagicMock()
    session.input_queue = asyncio.Queue()

    llm_chat_task = MagicMock()
    llm_chat_task.ui_factories = ["orig_ui"]
    llm_chat_task.approval_channels = ["orig_ch"]
    llm_chat_task.history_manager = "orig_hm"
    llm_chat_task.include_default_ui = True
    llm_chat_task.async_run = AsyncMock()

    session_manager = MagicMock()
    session_manager._history_manager = "new_hm"
    session_manager.broadcast = AsyncMock()
    session_manager.set_processing = MagicMock()

    return session, llm_chat_task, session_manager


@pytest.mark.asyncio
async def test_run_chat_session_success(mock_deps):
    session, llm_chat_task, session_manager = mock_deps
    session.input_queue.put_nowait("hello")

    # Run the session in a task and cancel it after it processes the message
    task = asyncio.create_task(
        run_chat_session(session, llm_chat_task, session_manager)
    )

    # Give it a moment to process
    await asyncio.sleep(0.01)

    # Verify the message was processed
    llm_chat_task.async_run.assert_called_once()
    session_manager.broadcast.assert_called_with("test-id", "[USER] hello")

    # The web path must pin interactive off: falling back to the CLI default
    # (True) replays full history to the SSE client and tears down LSP
    # servers / fires SESSION_END hooks on every message.
    run_session = llm_chat_task.async_run.call_args.kwargs["session"]
    assert run_session.shared_ctx.input["interactive"] == "false"

    # Clean up
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify cleanup occurred (using public properties)
    assert llm_chat_task.ui_factories == ["orig_ui"]
    assert llm_chat_task.include_default_ui is True


@pytest.mark.asyncio
async def test_run_chat_session_timeout(mock_deps):
    session, llm_chat_task, session_manager = mock_deps
    session.input_queue.put_nowait("hello")

    # Make the LLM task hang
    async def hang(*args, **kwargs):
        await asyncio.sleep(1)

    llm_chat_task.async_run = hang

    with patch("zrb.runner.chat.chat_session_runner.CFG") as mock_cfg:
        mock_cfg.LLM_INPUT_QUEUE_TIMEOUT = 100
        mock_cfg.LLM_REQUEST_TIMEOUT = 1  # very short timeout for LLM request
        mock_cfg.LOGGER = MagicMock()

        task = asyncio.create_task(
            run_chat_session(session, llm_chat_task, session_manager)
        )

        # Wait for timeout to occur
        await asyncio.sleep(0.1)

        session_manager.broadcast.assert_any_call(
            "test-id", "[TIMEOUT] LLM request timed out"
        )

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_run_chat_session_error(mock_deps):
    session, llm_chat_task, session_manager = mock_deps
    session.input_queue.put_nowait("hello")

    # Make the LLM task fail once, then succeed
    llm_chat_task.async_run.side_effect = [Exception("API failure"), None]

    task = asyncio.create_task(
        run_chat_session(session, llm_chat_task, session_manager)
    )

    await asyncio.sleep(0.01)

    # Verify error was broadcasted (exactly once — no double [ERROR] broadcast)
    error_msgs = [
        call[0][1]
        for call in session_manager.broadcast.call_args_list
        if "[ERROR]" in call[0][1]
    ]
    assert len(error_msgs) == 1
    assert "API failure" in error_msgs[0]

    # The loop must survive the failure: the next queued message is processed
    # instead of sitting dead until the browser reopens the SSE stream.
    session.input_queue.put_nowait("still alive?")
    await asyncio.sleep(0.01)
    assert llm_chat_task.async_run.call_count == 2

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_run_chat_session_cancel_race_ends_as_cancellation(mock_deps):
    """A cancel() eaten by wait_for's timeout must still cancel the session.

    asyncio.wait_for can consume a CancelledError delivered in the same tick
    as its timeout and raise TimeoutError instead. The loop detects this via
    current_task.cancelling(), but must re-raise a real CancelledError — not
    the TimeoutError, which would fall into the generic error handler and let
    the task finish "successfully" while its canceller believes it cancelled.
    """
    session, llm_chat_task, session_manager = mock_deps

    async def timeout_eating_cancel(coro, *args, **kwargs):
        coro.close()
        # Simulate the race: cancellation is requested and delivered, but
        # swallowed — wait_for surfaces TimeoutError with cancelling() > 0.
        current = asyncio.current_task()
        assert current is not None
        current.cancel()
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        raise asyncio.TimeoutError()

    with patch("asyncio.wait_for", new=timeout_eating_cancel):
        task = asyncio.create_task(
            run_chat_session(session, llm_chat_task, session_manager)
        )
        with pytest.raises(asyncio.CancelledError):
            await task

    assert task.cancelled()


@pytest.mark.asyncio
async def test_run_chat_session_input_timeout_loop(mock_deps):
    session, llm_chat_task, session_manager = mock_deps

    with patch("zrb.runner.chat.chat_session_runner.CFG") as mock_cfg:
        mock_cfg.LLM_INPUT_QUEUE_TIMEOUT = 1  # extremely short queue timeout
        mock_cfg.LLM_REQUEST_TIMEOUT = 10000
        mock_cfg.LOGGER = MagicMock()

        task = asyncio.create_task(
            run_chat_session(session, llm_chat_task, session_manager)
        )

        # Wait for the queue to timeout a few times
        await asyncio.sleep(0.05)

        # Then cancel
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Ensure it didn't crash during the empty timeouts
        assert llm_chat_task.async_run.call_count == 0
