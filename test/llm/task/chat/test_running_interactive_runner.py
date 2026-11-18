"""An interactive run with nothing to present itself through."""

from unittest.mock import MagicMock

import pytest

from zrb.llm.shared import session_presentation
from zrb.llm.task.chat.running import ChatRunning


class _ChatTask:
    """The state `run_interactive_session` would read off `LLMChatTask`."""

    custom_commands: list = []


@pytest.mark.asyncio
async def test_an_interactive_run_with_no_runner_says_so(monkeypatch):
    monkeypatch.setattr(session_presentation, "_runner", None)

    with pytest.raises(RuntimeError, match="No interactive session runner"):
        await ChatRunning(_ChatTask()).run_interactive_session(  # type: ignore[arg-type]
            ctx=MagicMock(),
            llm_task_core=MagicMock(),
            history_manager=MagicMock(),
            ui_commands={},
            initial_message=None,
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )
