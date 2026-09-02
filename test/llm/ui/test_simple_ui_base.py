import asyncio
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from zrb.config.config import CFG
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
    assert ui.assistant_name == CFG.LLM_ASSISTANT_NAME  # From UIConfig.default()
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


@pytest.mark.asyncio
async def test_simple_ui_append_to_output_tracks_background_task(deps):
    # Regression: asyncio only holds a weak reference to a scheduled task —
    # without tracking it somewhere, it can be silently garbage-collected
    # mid-execution. Every other fire-and-forget task in this package tracks
    # itself in `_background_tasks`; this call site must too.
    ui = ConcreteSimpleUI(**deps)
    assert hasattr(ui, "_background_tasks")

    ui.append_to_output("hello")
    assert len(ui.background_tasks) == 1

    await asyncio.sleep(0.01)
    # The done-callback discards it once it completes.
    assert len(ui.background_tasks) == 0


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


class FastLoopSimpleUI(ConcreteSimpleUI):
    """`_run_loop` overridden to return immediately (no polling delay)."""

    async def _run_loop(self) -> None:
        return


@pytest.mark.asyncio
async def test_simple_ui_run_async(deps):
    ui = FastLoopSimpleUI(initial_message="start", **deps)
    ui.submit_user_message = MagicMock()

    with patch(
        "zrb.llm.ui.base.ui.BaseUI.last_output", new_callable=PropertyMock
    ) as mock_last:
        mock_last.return_value = "Done"
        res = await ui.run_async()
        assert res == "Done"

    ui.submit_user_message.assert_called_once_with(ui.llm_task, "start")


class CancellingSimpleUI(ConcreteSimpleUI):
    """`_run_loop` overridden to immediately raise `CancelledError`."""

    async def _run_loop(self) -> None:
        raise asyncio.CancelledError()


@pytest.mark.asyncio
async def test_simple_ui_run_async_cancelled(deps):
    ui = CancellingSimpleUI(**deps)

    await ui.run_async()
