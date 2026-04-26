import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.ui.default.confirmation_mixin import ConfirmationMixin


class MockConfirmationUI(ConfirmationMixin):
    def __init__(self):
        self._confirmation_queue = []
        self._current_confirmation = None

    def append_to_output(self, text, end="\n"):
        pass

    def invalidate_ui(self):
        pass


@pytest.mark.asyncio
async def test_ask_user_queueing():
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app") as mock_get_app:
        # First call becomes current
        task1 = asyncio.create_task(ui.ask_user("prompt 1"))
        await asyncio.sleep(0.01)
        assert ui._current_confirmation is not None

        # Second call is queued
        task2 = asyncio.create_task(ui.ask_user("prompt 2"))
        await asyncio.sleep(0.01)
        assert len(ui._confirmation_queue) == 2  # task1 and task2

        # Submit first answer
        ui.submit_user_answer("answer 1")
        res1 = await task1
        assert res1 == "answer 1"

        # Second call should now be current
        assert ui._current_confirmation is not None

        # Submit second answer
        ui.submit_user_answer("answer 2")
        res2 = await task2
        assert res2 == "answer 2"
        assert ui._current_confirmation is None


@pytest.mark.asyncio
async def test_cancel_pending_confirmations():
    ui = MockConfirmationUI()

    with patch("prompt_toolkit.application.get_app"):
        task = asyncio.create_task(ui.ask_user("prompt"))
        await asyncio.sleep(0.01)

        ui.cancel_pending_confirmations()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ui._current_confirmation is None
        assert len(ui._confirmation_queue) == 0
