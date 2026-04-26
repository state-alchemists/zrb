import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.default.lifecycle_mixin import LifecycleMixin


class MockLifecycleUI(LifecycleMixin):
    def __init__(self):
        self._process_messages_task = MagicMock(spec=asyncio.Task)
        self._system_info_task = MagicMock(spec=asyncio.Task)
        self._refresh_task = MagicMock(spec=asyncio.Task)
        self._trigger_tasks = [MagicMock(spec=asyncio.Task)]
        self._message_queue = asyncio.Queue()
        self._background_tasks = set()
        self._message_queue.put_nowait("msg")

    async def _cancel_and_discard(self, task):
        if task:
            task.cancel()


@pytest.mark.asyncio
async def test_cleanup_background_tasks():
    ui = MockLifecycleUI()
    ui._cancel_and_discard = AsyncMock()

    await ui.cleanup_background_tasks()

    assert (
        ui._cancel_and_discard.call_count == 4
    )  # process, 1 trigger, system_info, refresh
    assert ui._message_queue.empty()
    assert len(ui._trigger_tasks) == 0


def test_handle_first_render():
    ui = MockLifecycleUI()
    ui._application = MagicMock()
    ui._llm_task = MagicMock()
    ui._initial_message = "hello"
    ui._submit_user_message = MagicMock()

    ui.handle_first_render()

    # Verify handler removal and message submission
    ui._application.after_render.remove_handler.assert_called_once()
    ui._submit_user_message.assert_called_with(ui._llm_task, "hello")


def test_handle_application_run_error():
    ui = MockLifecycleUI()
    ui.append_to_output = MagicMock()

    ui.handle_application_run_error(ValueError("run fail"))

    # Verify error message and kind in output
    args = ui.append_to_output.call_args[0][0]
    assert "[Error: run fail]" in args


def test_on_exit_logic():
    ui = MockLifecycleUI()
    task = MagicMock()
    task.done.return_value = False
    ui._background_tasks.add(task)

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        ui.on_exit()
        task.cancel.assert_called_once()
        mock_get_app.return_value.exit.assert_called_once()
