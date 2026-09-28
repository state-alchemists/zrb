import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.ui.event_driven_ui import EventDrivenUI


class MockEventUI(EventDrivenUI):
    def __init__(self, custom_commands=None):
        ctx = MagicMock()
        llm_task = MagicMock()
        history_manager = MagicMock()
        super().__init__(
            ctx=ctx,
            llm_task=llm_task,
            history_manager=history_manager,
            custom_commands=custom_commands,
        )
        self.print_mock = AsyncMock()
        self.start_mock = AsyncMock()
        self.submit_user_message = MagicMock()

    async def print(self, text: str, kind: str = "text") -> None:
        await self.print_mock(text, kind=kind)

    async def start_event_loop(self):
        await self.start_mock()


@pytest.mark.asyncio
async def test_handle_incoming_message():
    ui = MockEventUI()

    # Not waiting for input -> submit message
    ui.waiting_for_input = False
    ui.handle_incoming_message("hello")
    ui.submit_user_message.assert_called_with(ui.llm_task, "hello")
    assert ui.input_queue.empty()

    # Waiting for input -> enqueue
    ui.waiting_for_input = True
    ui.handle_incoming_message("world")
    assert ui.input_queue.qsize() == 1
    msg = await ui.input_queue.get()
    assert msg == "world"


@pytest.mark.asyncio
async def test_get_input():
    ui = MockEventUI()

    # Pre-populate queue so it doesn't block forever
    ui.input_queue.put_nowait("response")

    result = await ui.get_input("Prompt:")
    assert result == "response"
    ui.print_mock.assert_called_with("❓ Prompt:", kind="text")
    assert ui.waiting_for_input is False


@pytest.mark.asyncio
async def test_get_input_no_prompt():
    ui = MockEventUI()

    # Pre-populate queue so it doesn't block forever
    ui.input_queue.put_nowait("response")

    result = await ui.get_input("")
    assert result == "response"
    assert ui.print_mock.call_count == 0


@pytest.mark.asyncio
async def test_handle_incoming_message_resolves_slash_command():
    from zrb.llm.custom_command import CustomCommand

    class CapturingEventUI(EventDrivenUI):
        submitted: list[str]

        def __init__(self, custom_commands=None):
            self.submitted = []
            ctx = MagicMock()
            llm_task = MagicMock()
            history_manager = MagicMock()
            super().__init__(
                ctx=ctx,
                llm_task=llm_task,
                history_manager=history_manager,
                custom_commands=custom_commands,
            )

        def submit_user_message(self, llm_task, user_message):
            self.submitted.append(user_message)

        async def print(self, text, kind="text"):
            pass

        async def start_event_loop(self):
            pass

    cmd = CustomCommand(
        command="/greet",
        description="Say hello",
        prompt="Please greet the user",
    )
    ui = CapturingEventUI(custom_commands=[cmd])

    ui.handle_incoming_message("/greet")
    assert ui.submitted == ["Please greet the user"]

    ui.handle_incoming_message("/unknown")
    assert ui.submitted[-1] == "/unknown"

    ui.handle_incoming_message("hello")
    assert ui.submitted[-1] == "hello"


@pytest.mark.asyncio
async def test_handle_incoming_message_runs_action_command():
    from zrb.llm.custom_command import ActionCommand

    class CapturingEventUI(EventDrivenUI):
        def __init__(self, custom_commands=None):
            self.submitted: list[str] = []
            self.printed: list[str] = []
            super().__init__(
                ctx=MagicMock(),
                llm_task=MagicMock(),
                history_manager=MagicMock(),
                custom_commands=custom_commands,
            )

        def submit_user_message(self, llm_task, user_message):
            self.submitted.append(user_message)

        async def print(self, text, kind="text"):
            self.printed.append(text)

        async def start_event_loop(self):
            pass

    ui = CapturingEventUI(
        custom_commands=[ActionCommand("/toggle", lambda kwargs, ui: "Toggled")]
    )

    ui.handle_incoming_message("/toggle")
    await asyncio.sleep(0)

    assert ui.submitted == []
    assert ui.printed == ["Toggled"]


def test_handle_incoming_message_forwards_non_string_input():
    from zrb.llm.custom_command import ActionCommand

    ui = MockEventUI(custom_commands=[ActionCommand("/toggle", lambda kwargs, ui: "x")])
    ui.waiting_for_input = False
    payload = {"type": "image"}

    ui.handle_incoming_message(payload)

    ui.submit_user_message.assert_called_with(ui.llm_task, payload)


@pytest.mark.asyncio
async def test_run_async_triggers_event_loop():
    ui = MockEventUI()
    ui.submit_user_message = MagicMock()

    # Let it run briefly and then cancel.
    # asyncio.wait_for will cancel the task, and SimpleUI's run_async
    # swallows CancelledError and returns normally.
    await asyncio.wait_for(ui.run_async(), timeout=0.1)

    ui.start_mock.assert_called_once()


@pytest.mark.asyncio
async def test_submit_answer_goes_to_the_waiting_question():
    ui = MockEventUI()
    assert ui.is_waiting_for_answer is False

    waiting = asyncio.create_task(ui.get_input(""))
    await asyncio.sleep(0)
    assert ui.is_waiting_for_answer is True

    ui.submit_answer("yes")
    assert await waiting == "yes"


@pytest.mark.asyncio
async def test_pending_answer_since_dates_the_waiting_question():
    ui = MockEventUI()
    assert ui.pending_answer_since is None
    assert not ui.is_prompt_answered_since(0)

    before = time.monotonic()
    waiting = asyncio.create_task(ui.get_input(""))
    await asyncio.sleep(0)
    since = ui.pending_answer_since

    assert since is not None and since >= before
    ui.submit_answer("yes")
    await waiting
    assert ui.pending_answer_since is None
    assert ui.is_prompt_answered_since(before)
    assert not ui.is_prompt_answered_since(time.monotonic())
