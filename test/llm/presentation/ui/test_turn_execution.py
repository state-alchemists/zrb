"""The one chat turn: what it settles, what it clears, and how it fails.

`run_turn` is the sequence `BaseUI` and `MultiUI` used to write twice. These
tests pin it on a real `BaseUI` — the display rule `last_output` follows is
`BaseUIDisplay`'s, so a stand-in would prove nothing about the drift that put
the turn here in the first place.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.capabilities.permission.state import (
    AgentMode,
    get_current_agent_mode,
    set_current_agent_mode,
)
from zrb.llm.presentation.ui.simple_ui_base import SimpleUI
from zrb.llm.presentation.ui.turn_execution import build_turn_session, run_turn
from zrb.session.session import Session


class _RecordingUI(SimpleUI):
    """A real `BaseUI` that keeps what it wrote instead of drawing a stream."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.written: list[str] = []

    def append_to_output(
        self, *values, sep=" ", end="\n", file=None, flush=False, kind="text"
    ):
        self.written.append(sep.join(str(value) for value in values) + end)

    async def print(self, text: str, kind: str) -> None:
        self.written.append(text)

    async def get_input(self, prompt: str) -> str:
        return ""


def _ui() -> _RecordingUI:
    ui = _RecordingUI(
        ctx=MagicMock(), llm_task=MagicMock(), history_manager=MagicMock()
    )
    # A chosen name, not a generated one, so a finished turn does not start an
    # auto-naming model call inside the test.
    ui.conversation_session_name = "chosen-by-the-user"
    return ui


def _task(result: object = None, error: BaseException | None = None) -> MagicMock:
    task = MagicMock()
    task.set_ui = MagicMock()
    if error is not None:
        task.async_run = AsyncMock(side_effect=error)
    else:
        task.async_run = AsyncMock(return_value=result)
    return task


def test_build_turn_session_names_it_after_the_ui_it_runs_on():
    ui = SimpleNamespace(
        conversation_session_name="chosen-by-the-user",
        yolo=True,
        model="openai:gpt-5.6-luna",
        append_to_output=lambda *values, **kwargs: None,
    )

    session = build_turn_session(ui, "hello", ["an-attachment"])

    assert isinstance(session, Session)
    assert session.shared_ctx.input == {
        "message": "hello",
        "session": "chosen-by-the-user",
        "yolo": True,
        "attachments": ["an-attachment"],
        "model": "openai:gpt-5.6-luna",
    }


def test_build_turn_session_falls_back_to_default_when_the_ui_names_nothing():
    ui = SimpleNamespace(
        conversation_session_name="",
        yolo=False,
        model=None,
        append_to_output=lambda *values, **kwargs: None,
    )

    assert build_turn_session(ui, "hello", []).shared_ctx.input["session"] == "default"


@pytest.mark.asyncio
async def test_a_failed_turn_leaves_no_answer_behind():
    """The drift this module closes: the base UI kept the previous turn's
    result, so `display.last_output` answered with it after a failure."""
    ui = _ui()
    ui.last_result_data = "the previous answer"

    await run_turn(ui, _task(error=ValueError("boom")), "hello")

    assert ui.last_result_data is None
    assert ui.display.last_output == ""
    assert "[Error: ValueError: boom]" in ui.written[-1]


@pytest.mark.asyncio
async def test_a_cancelled_turn_is_announced_and_re_raised():
    ui = _ui()

    with pytest.raises(asyncio.CancelledError):
        await run_turn(ui, _task(error=asyncio.CancelledError()), "hello")

    assert "[Cancelled]" in ui.written[-1]
    assert ui.is_thinking is False


@pytest.mark.asyncio
async def test_a_finished_turn_keeps_the_markers_and_shows_the_plain_answer():
    ui = _ui()

    await run_turn(ui, _task(result="<spoken>Hello, Go.</spoken>"), "hello")

    # The raw result keeps its markers for speech; the screen gets the words.
    assert ui.last_result_data == "<spoken>Hello, Go.</spoken>"
    assert ui.display.last_output == "<spoken>Hello, Go.</spoken>"
    assert "Hello, Go." in "".join(ui.written)
    assert "<spoken>" not in "".join(ui.written)


@pytest.mark.asyncio
async def test_the_turn_is_thinking_while_it_runs_and_not_after():
    ui = _ui()
    seen = []

    async def _answer(*args, **kwargs):
        seen.append(ui.is_thinking)
        return "done"

    task = MagicMock()
    task.async_run = _answer

    await run_turn(ui, task, "hello")

    assert seen == [True]
    assert ui.is_thinking is False


@pytest.mark.asyncio
async def test_the_turn_gives_the_task_this_ui_and_its_confirmation():
    ui = _ui()
    task = _task(result="done")

    await run_turn(ui, task, "hello")

    task.set_ui.assert_called_once_with(ui)
    assert task.tool_confirmation == ui.confirm_tool_execution


@pytest.mark.asyncio
async def test_plan_mode_on_the_ui_reaches_the_run():
    ui = _ui()
    ui.plan_mode_active = True
    seen = []

    async def _answer(*args, **kwargs):
        seen.append(get_current_agent_mode())
        return "done"

    task = MagicMock()
    task.async_run = _answer
    try:
        await run_turn(ui, task, "hello")
        assert seen == [AgentMode.PLAN]
    finally:
        # The mode is a ContextVar: leave BUILD behind for the next test.
        set_current_agent_mode(AgentMode.BUILD)


@pytest.mark.asyncio
async def test_an_in_run_mode_switch_is_copied_back_to_the_badge():
    """EnterPlanMode/ExitPlanMode change the turn-local mode; the badge must
    still show the mode the run ended in."""
    ui = _ui()
    ui.plan_mode_active = False

    async def _answer(*args, **kwargs):
        set_current_agent_mode(AgentMode.PLAN)  # EnterPlanMode mid-run
        return "planned"

    task = MagicMock()
    task.async_run = _answer
    try:
        await run_turn(ui, task, "hello")
    finally:
        set_current_agent_mode(AgentMode.BUILD)

    assert ui.plan_mode_active is True


@pytest.mark.asyncio
async def test_interleaved_turns_keep_their_own_mode_and_copy_the_final_one_back():
    """Two turns running concurrently in one process must not inherit each
    other's mode: the setter writes a turn-local state, and each badge gets
    the mode its own run ended in."""
    plan_ui = _ui()
    plan_ui.plan_mode_active = True
    build_ui = _ui()
    build_ui.plan_mode_active = False

    plan_started = asyncio.Event()
    build_started = asyncio.Event()
    plan_seen: list[AgentMode] = []
    build_seen: list[AgentMode] = []

    async def plan_answer(*args, **kwargs):
        plan_seen.append(get_current_agent_mode())
        plan_started.set()
        await build_started.wait()
        # The build turn flipped its own mode in between; this run must not see it.
        plan_seen.append(get_current_agent_mode())
        set_current_agent_mode(AgentMode.BUILD)  # ExitPlanMode mid-run
        return "planned"

    async def build_answer(*args, **kwargs):
        await plan_started.wait()
        build_seen.append(get_current_agent_mode())
        set_current_agent_mode(AgentMode.PLAN)  # EnterPlanMode mid-run
        build_started.set()
        await asyncio.sleep(0)
        # The plan turn resumed and flipped its own mode; this run keeps PLAN.
        build_seen.append(get_current_agent_mode())
        return "built"

    plan_task = MagicMock()
    plan_task.async_run = plan_answer
    build_task = MagicMock()
    build_task.async_run = build_answer
    try:
        await asyncio.gather(
            run_turn(plan_ui, plan_task, "plan"),
            run_turn(build_ui, build_task, "build"),
        )
    finally:
        # The write-back leaves the shared default mutated; reset for other tests.
        set_current_agent_mode(AgentMode.BUILD)

    assert plan_seen == [AgentMode.PLAN, AgentMode.PLAN]
    assert build_seen == [AgentMode.BUILD, AgentMode.PLAN]
    # Each badge shows the mode its own run ended in.
    assert plan_ui.plan_mode_active is False
    assert build_ui.plan_mode_active is True


@pytest.mark.asyncio
async def test_a_finished_turn_offers_the_conversation_for_auto_naming():
    ui = _ui()
    ui.conversation.schedule_auto_name = MagicMock()

    await run_turn(ui, _task(result="done"), "hello")

    ui.conversation.schedule_auto_name.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_the_system_info_is_refreshed_even_when_the_turn_fails():
    ui = _ui()
    ui.update_system_info = AsyncMock()

    await run_turn(ui, _task(error=ValueError("boom")), "hello")

    ui.update_system_info.assert_awaited_once()
