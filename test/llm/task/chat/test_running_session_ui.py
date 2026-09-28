"""The UI a chat run binds to its session, for hooks and triggers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.task.chat.running import ChatRunning
from zrb.llm.util.feature_config import (
    get_session_ui,
    reset_session_ui,
    set_session_ui,
)


class _ChatTask:
    """The state `run_non_interactive_session` reads off `LLMChatTask`."""

    ui_factories: list = []
    custom_commands: list = []

    def get_model(self, ctx):
        return "test-model"


async def _ui_seen_during_a_run(attached: list) -> list:
    """Run once with *attached* UIs; return what `get_session_ui` gave inside."""
    ctx = MagicMock()
    ctx.xcom = {}
    seen = []
    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(
        side_effect=lambda session: seen.append(get_session_ui())
    )
    llm_task_core.get_uis.return_value = attached
    await ChatRunning(_ChatTask()).run_non_interactive_session(  # type: ignore[arg-type]
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )
    return seen


@pytest.fixture
def outer_ui():
    """A UI already bound when the run starts."""
    ui = MagicMock(spec=[])
    set_session_ui(ui)
    yield ui
    reset_session_ui()


@pytest.mark.asyncio
async def test_a_run_binds_its_ui_and_puts_back_the_one_before(outer_ui):
    sink = MagicMock(spec=[])

    assert await _ui_seen_during_a_run([sink]) == [sink]
    assert get_session_ui() is outer_ui


@pytest.mark.asyncio
async def test_a_run_without_a_ui_hides_the_one_bound_before_it(outer_ui):
    assert await _ui_seen_during_a_run([]) == [None]
    assert get_session_ui() is outer_ui
