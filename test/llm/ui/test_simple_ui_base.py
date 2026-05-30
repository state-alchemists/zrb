import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from zrb.llm.ui.simple_ui_base import SimpleUI


class ConcreteSimpleUI(SimpleUI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prints = []
        self.inputs = []

    async def print(self, text: str, kind: str) -> None:
        self.prints.append((text, kind))

    async def get_input(self, prompt: str) -> str:
        self.inputs.append(prompt)
        return "user input"


class IncompleteUI(SimpleUI):
    pass


@pytest.fixture
def deps():
    return {"ctx": MagicMock(), "llm_task": MagicMock(), "history_manager": MagicMock()}


def test_simple_ui_init(deps):
    ui = ConcreteSimpleUI(**deps)
    assert ui._assistant_name == "Assistant"  # From UIConfig.default()
    assert ui.yolo is False


def test_simple_ui_incomplete_methods(deps):
    ui = IncompleteUI(**deps)
    with pytest.raises(NotImplementedError):
        # We need an event loop to run the async method
        asyncio.run(ui.print("test", "text"))

    with pytest.raises(NotImplementedError):
        asyncio.run(ui.get_input("prompt"))


@pytest.mark.asyncio
async def test_simple_ui_append_to_output(deps):
    ui = ConcreteSimpleUI(**deps)
    ui.append_to_output("hello", "world", kind="progress")
    # Wait for the task to run
    await asyncio.sleep(0.01)
    assert len(ui.prints) == 1
    assert ui.prints[0] == ("hello world\n", "progress")


def test_simple_ui_append_to_output_sync_fallback(deps, capsys):
    ui = ConcreteSimpleUI(**deps)
    # Patch asyncio.get_running_loop to raise RuntimeError
    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
        ui.append_to_output("hello", "world")

    captured = capsys.readouterr()
    assert captured.out == "hello world\n"
    assert len(ui.prints) == 0


@pytest.mark.asyncio
async def test_simple_ui_ask_user(deps):
    ui = ConcreteSimpleUI(**deps)
    res = await ui.ask_user("prompt?")
    assert res == "user input"
    assert ui.inputs == ["prompt?"]


@pytest.mark.asyncio
async def test_simple_ui_run_interactive_command(deps):
    ui = ConcreteSimpleUI(**deps)
    res = await ui.run_interactive_command("echo hello")
    assert res == 1
    assert len(ui.prints) == 1
    assert "not supported" in ui.prints[0][0]


@pytest.mark.asyncio
async def test_simple_ui_run_async(deps):
    ui = ConcreteSimpleUI(initial_message="start", **deps)
    ui._submit_user_message = MagicMock()

    async def fast_loop():
        # Stop quickly
        return

    ui._run_loop = fast_loop

    with patch(
        "zrb.llm.ui.base.ui.BaseUI.last_output", new_callable=PropertyMock
    ) as mock_last:
        mock_last.return_value = "Done"
        res = await ui.run_async()
        assert res == "Done"

    ui._submit_user_message.assert_called_once_with(ui._llm_task, "start")


@pytest.mark.asyncio
async def test_simple_ui_run_async_cancelled(deps):
    ui = ConcreteSimpleUI(**deps)

    async def cancel_loop():
        raise asyncio.CancelledError()

    ui._run_loop = cancel_loop

    res = await ui.run_async()
    assert True
