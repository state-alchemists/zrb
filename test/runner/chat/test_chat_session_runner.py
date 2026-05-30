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

    # Make the LLM task fail
    llm_chat_task.async_run.side_effect = Exception("API failure")

    task = asyncio.create_task(
        run_chat_session(session, llm_chat_task, session_manager)
    )

    await asyncio.sleep(0.01)

    # Verify error was broadcasted
    assert session_manager.broadcast.call_count >= 2
    # The second call should contain the traceback and the error message
    error_msg = session_manager.broadcast.call_args_list[1][0][1]
    assert "API failure" in error_msg
    assert "[ERROR]" in error_msg

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


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
