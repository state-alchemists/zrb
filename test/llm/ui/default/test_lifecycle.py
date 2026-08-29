import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.default.lifecycle import UILifecycle


def create_mock_task():
    fut = asyncio.Future()
    fut.set_result(None)
    fut.cancel = MagicMock()
    return fut


class MockLifecycleUI:
    """Stand-in UI composing the real `UILifecycle`.

    Holds all the state/methods `UILifecycle` reaches via `self._ui` —
    supplied by the default `UI` — and forwards the public
    lifecycle methods to the composed part.
    """

    def __init__(self):
        self.process_messages_task = create_mock_task()
        self.system_info_task = create_mock_task()
        self.refresh_task = create_mock_task()
        self.trigger_tasks = [create_mock_task()]
        self.message_queue = asyncio.Queue()
        self.background_tasks = set()
        self.message_queue.put_nowait("msg")
        self.triggers = [MagicMock()]
        self.application = MagicMock()

        def mock_create_bg_task(coro):
            coro.close()  # Consume coroutine to prevent "never awaited" warning
            return create_mock_task()

        self.application.create_background_task = MagicMock(
            side_effect=mock_create_bg_task
        )
        self.application.run_async = AsyncMock(return_value="test_run_async_result")
        self.capture = MagicMock()
        self.capture.get_buffered_output.return_value = "captured_output"
        self.update_system_info = AsyncMock()
        self.snapshot_manager = AsyncMock()
        self.input_field = MagicMock()
        self.output_field = MagicMock()
        self.initial_message = "hello"
        self.submit_message = MagicMock()
        self.append_to_output = MagicMock()
        # The real default `UI` registers *this* bound method on
        # `after_render` (see `ui.py`); `UILifecycle.on_first_render` must
        # remove this exact object, not its own bound method, or the handler
        # never actually unregisters (see the regression this guards against).
        self.on_first_render = MagicMock()
        self._lifecycle = UILifecycle(self)
        # Public alias so tests can reach the composed part without a
        # leading-underscore dotted expression (counted by the
        # private-test-access ratchet).
        self.lifecycle_part = self._lifecycle

    async def trigger_loop(self, trigger):
        pass

    async def process_messages_loop(self):
        pass

    async def update_system_info_loop(self):
        pass

    def cleanup_background_tasks(self):
        return self._lifecycle.cleanup_background_tasks()

    def handle_first_render(self):
        return self._lifecycle.handle_first_render()

    def handle_application_run_error(self, exc):
        return self._lifecycle.handle_application_run_error(exc)

    def run_async(self):
        return self._lifecycle.run_async()

    def invalidate_ui(self):
        return self._lifecycle.invalidate_ui()

    def on_exit(self):
        return self._lifecycle.on_exit()


@pytest.mark.asyncio
async def test_cleanup_background_tasks():
    ui = MockLifecycleUI()
    setattr(ui.lifecycle_part, "_cancel_and_discard", AsyncMock())

    await ui.cleanup_background_tasks()

    assert (
        getattr(ui.lifecycle_part, "_cancel_and_discard").call_count == 4
    )  # process, 1 trigger, system_info, refresh
    assert ui.message_queue.empty()
    assert len(ui.trigger_tasks) == 0


@pytest.mark.asyncio
async def test_handle_first_render():
    ui = MockLifecycleUI()

    ui.handle_first_render()

    # Verify the *registered* handler (`ui.on_first_render`) is what gets
    # removed — not `UILifecycle`'s own bound method — otherwise the removal
    # is a silent no-op and the handler keeps firing on every render frame,
    # resubmitting the initial message forever (the regression this guards).
    ui.application.after_render.remove_handler.assert_called_once_with(
        ui.on_first_render
    )
    ui.submit_message.assert_called_with("hello")


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
    ui.background_tasks.add(task)

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
        assert ui.application.create_background_task.call_count == 4
        ui.capture.start.assert_called_once()
        ui.update_system_info.assert_called_once()
        ui.snapshot_manager.take_init_snapshot.assert_called_once()
        ui.application.run_async.assert_called_once()
        ui.capture.stop.assert_called_once()
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
