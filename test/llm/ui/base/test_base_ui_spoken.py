"""The turn's answer reaches the screen without the `<spoken>` markers.

The answer keeps them for speech — the stop hook reads the same string — so the
screen copy is stripped where it is rendered. `test_base_ui.py` is at the
test-file size limit; this is its own subject.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.ui.base.ui import BaseUI

ANSWER = "<spoken>😊 Fixed the parser. All tests pass.</spoken>\n`main.py`: 3 tests."


class RecordingUI(BaseUI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rendered: list[str] = []

    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    def append_markdown(self, markdown_text: str) -> None:
        self.rendered.append(markdown_text)

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        return ""


@pytest.fixture
def recording_ui():
    ctx = Context(SharedContext(), "test", 0, "")
    llm_task = MagicMock(hook_manager=None, active_hook_manager=None)
    return RecordingUI(
        ctx=ctx,
        llm_task=llm_task,
        history_manager=MagicMock(),
    )


@pytest.mark.asyncio
async def test_the_answer_is_rendered_without_the_markers(recording_ui):
    recording_ui.llm_task.async_run = AsyncMock(return_value=ANSWER)

    await recording_ui.stream_ai_response(recording_ui.llm_task, "user message")

    [rendered] = recording_ui.rendered
    assert "spoken" not in rendered
    assert "😊 Fixed the parser. All tests pass." in rendered
    assert "`main.py`: 3 tests." in rendered


@pytest.mark.asyncio
async def test_the_answer_keeps_its_markers_for_speech(recording_ui):
    """The stop hook reads the run's own output: what speech needs must survive
    the screen's copy, or the block would be lost by the time it is spoken."""
    recording_ui.llm_task.async_run = AsyncMock(return_value=ANSWER)

    await recording_ui.stream_ai_response(recording_ui.llm_task, "user message")

    assert recording_ui.last_output == ANSWER
