import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.default.lifecycle_mixin import LifecycleMixin


def create_mock_task():
    fut = asyncio.Future()
    fut.set_result(None)
    fut.cancel = MagicMock()
    return fut


class MockLifecycleUI(LifecycleMixin):
    def __init__(self):
        self._process_messages_task = create_mock_task()
        self._system_info_task = create_mock_task()
        self._refresh_task = create_mock_task()
        self._trigger_tasks = [create_mock_task()]
        self._message_queue = asyncio.Queue()
        self._background_tasks = set()
        self._message_queue.put_nowait("msg")
        self._triggers = [MagicMock()]
        self._application = MagicMock()

        def mock_create_bg_task(coro):
            coro.close()  # Consume coroutine to prevent "never awaited" warning
            return create_mock_task()

        self._application.create_background_task = MagicMock(
            side_effect=mock_create_bg_task
        )
        self._application.run_async = AsyncMock(return_value="test_run_async_result")
        self._capture = MagicMock()
        self._capture.get_buffered_output.return_value = "captured_output"
        self._update_system_info = AsyncMock()
        self._snapshot_manager = AsyncMock()
        self._input_field = MagicMock()
        self._output_field = MagicMock()
        self._llm_task = MagicMock()
        self._initial_message = "hello"
        self._submit_user_message = MagicMock()
        self.append_to_output = MagicMock()

    async def _trigger_loop(self, trigger):
        pass

    async def _process_messages_loop(self):
        pass

    async def _update_system_info_loop(self):
        pass

    async def _refresh_loop(self):
        pass


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


@pytest.mark.asyncio
async def test_handle_first_render():
    ui = MockLifecycleUI()

    ui.handle_first_render()

    # Verify handler removal and message submission
    ui._application.after_render.remove_handler.assert_called_once()
    ui._submit_user_message.assert_called_with(ui._llm_task, "hello")


@pytest.mark.asyncio
async def test_handle_application_run_error():
    ui = MockLifecycleUI()

    ui.handle_application_run_error(ValueError("run fail"))

    # Verify error message and kind in output
    args = ui.append_to_output.call_args[0][0]
    assert "[Error: run fail]" in args


@pytest.mark.asyncio
async def test_on_exit_logic():
    ui = MockLifecycleUI()
    task = MagicMock()
    task.done.return_value = False
    ui._background_tasks.add(task)

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        ui.on_exit()
        task.cancel.assert_called_once()
        mock_get_app.return_value.exit.assert_called_once()


@pytest.mark.asyncio
async def test_run_async():
    ui = MockLifecycleUI()

    with patch("builtins.print") as mock_print:
        result = await ui.run_async()

        assert result == "test_run_async_result"
        assert ui._application.create_background_task.call_count == 4
        ui._capture.start.assert_called_once()
        ui._update_system_info.assert_called_once()
        ui._snapshot_manager.take_init_snapshot.assert_called_once()
        ui._application.run_async.assert_called_once()
        ui._capture.stop.assert_called_once()
        mock_print.assert_called_with("captured_output", end="")


@pytest.mark.asyncio
async def test_invalidate_ui():
    ui = MockLifecycleUI()
    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        ui.invalidate_ui()
        mock_get_app.return_value.invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_ui_exception():
    ui = MockLifecycleUI()
    with patch("prompt_toolkit.application.get_app", side_effect=Exception("error")):
        ui.invalidate_ui()  # should not raise exception


@pytest.mark.asyncio
async def test_on_exit_exception():
    ui = MockLifecycleUI()
    with patch("prompt_toolkit.application.get_app", side_effect=Exception("error")):
        ui.on_exit()  # should not raise exception
