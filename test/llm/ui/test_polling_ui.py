import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.llm.ui.polling_ui import PollingUI


@pytest.fixture
def polling_ui():
    ctx = MagicMock()
    llm_task = MagicMock()
    history_manager = MagicMock()
    return PollingUI(ctx=ctx, llm_task=llm_task, history_manager=history_manager)


@pytest.mark.asyncio
async def test_polling_ui_print(polling_ui):
    await polling_ui.print("hello", kind="text")
    res = await polling_ui.output_queue.get()
    assert res == "hello"


@pytest.mark.asyncio
async def test_polling_ui_get_input_lifecycle(polling_ui):
    # Simulate a user answering a prompt
    async def answer_later():
        await asyncio.sleep(0.01)
        polling_ui.handle_incoming_message("answer")

    asyncio.create_task(answer_later())

    res = await polling_ui.get_input("prompt")
    assert res == "answer"

    # Check that it printed the prompt to output queue
    prompt_out = await polling_ui.output_queue.get()
    assert "❓ prompt" in prompt_out


@pytest.mark.asyncio
async def test_polling_ui_handle_incoming_idle(polling_ui):
    polling_ui._submit_user_message = MagicMock()

    polling_ui.handle_incoming_message("new message")

    polling_ui._submit_user_message.assert_called_once()


def test_polling_ui_input_queue_property(polling_ui):
    assert polling_ui.input_queue is polling_ui._input_queue
