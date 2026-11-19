import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zrb.runner.chat.chat_api_route import resolve_llm_chat_task_for_session

_SRC = Path(__file__).resolve().parents[3] / "src"

# A web server's startup imports `zrb.builtin.llm.deferred` and nothing that
# builds the chat task, so the task module has to be loaded by whoever resumes
# a session — the `LLMChatTask` construction used to be imported lazily at
# exactly that point, and the seam that replaced it registers nothing until that
# module loads.
_DELEGATED_RESUME_PROBE = """
import asyncio
import sys

import zrb.builtin.llm.deferred  # what starting the web server pays
from zrb.runner.chat.chat_api_route import resolve_llm_chat_task_for_session

import zrb.llm.orchestration.subagent.building as building
from zrb.llm.orchestration.subagent.definition import SubAgentDefinition
from zrb.llm.orchestration.subagent.manager.manager import sub_agent_manager

assert "zrb.llm.orchestration.task.chat.task" not in sys.modules, "probe must start without it"
building.resolve_configured_model = lambda *args, **kwargs: "probe-model"
sub_agent_manager.add_agent(
    SubAgentDefinition(
        name="probe-agent",
        path=".",
        description="probe",
        system_prompt="You are a probe.",
        tools=[],
        model="probe-model",
    )
)
task, _ = asyncio.run(
    resolve_llm_chat_task_for_session("parent-sub-probe-agent-abcd1234", None)
)
print(type(task).__name__, "zrb.llm.orchestration.task.chat.task" in sys.modules)
"""


def test_a_delegated_session_resumes_before_any_chat_task_was_loaded():
    """The first delegated session on a fresh server still resumes.

    `zrb.builtin.llm.deferred` exists to keep the chat task's import off
    startup, so a server that has only served normal sessions has not loaded
    `zrb.llm.orchestration.task.chat.task`. The route must not need it loaded first:
    `resumed_session.py` imports it when a session is actually resumed.
    """
    result = subprocess.run(
        [sys.executable, "-c", _DELEGATED_RESUME_PROBE],
        capture_output=True,
        text=True,
        cwd=_SRC.parent,
        env={**os.environ, "PYTHONPATH": str(_SRC)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["LLMChatTask", "True"], result.stdout


@pytest.mark.asyncio
async def test_ordinary_session_uses_the_shared_main_chat_task():
    root_group = MagicMock()
    main_task = MagicMock()

    with patch(
        "zrb.runner.chat.chat_api_route.get_llm_chat_task",
        return_value=main_task,
    ):
        llm_chat, not_found_msg = await resolve_llm_chat_task_for_session(
            "my-project-chat", root_group
        )

    assert llm_chat is main_task
    assert not_found_msg  # unused on the success path, but always a string


@pytest.mark.asyncio
async def test_ordinary_session_missing_main_task_reports_not_registered():
    root_group = MagicMock()

    with patch("zrb.runner.chat.chat_api_route.get_llm_chat_task", return_value=None):
        llm_chat, not_found_msg = await resolve_llm_chat_task_for_session(
            "my-project-chat", root_group
        )

    assert llm_chat is None
    assert "llm chat" in not_found_msg.lower()


@pytest.mark.asyncio
async def test_delegated_session_resumes_via_the_subagent_persona():
    root_group = MagicMock()
    resumed_task = MagicMock()

    with patch("zrb.runner.chat.chat_api_route.sub_agent_manager") as mock_manager:
        mock_manager.create_llm_chat_task.return_value = resumed_task
        llm_chat, _ = await resolve_llm_chat_task_for_session(
            "sess1-sub-code-reviewer-a1b2c3d4", root_group
        )

    mock_manager.create_llm_chat_task.assert_called_once_with("code-reviewer")
    assert llm_chat is resumed_task


@pytest.mark.asyncio
async def test_delegated_session_with_unresolvable_agent_reports_the_agent_name():
    root_group = MagicMock()

    with patch("zrb.runner.chat.chat_api_route.sub_agent_manager") as mock_manager:
        mock_manager.create_llm_chat_task.return_value = None
        llm_chat, not_found_msg = await resolve_llm_chat_task_for_session(
            "sess1-sub-ghost-agent-deadbeef", root_group
        )

    assert llm_chat is None
    assert "ghost-agent" in not_found_msg


@pytest.mark.asyncio
async def test_delegated_session_never_falls_back_to_the_main_chat_task():
    root_group = MagicMock()
    main_task = MagicMock()

    with (
        patch(
            "zrb.runner.chat.chat_api_route.get_llm_chat_task",
            return_value=main_task,
        ),
        patch("zrb.runner.chat.chat_api_route.sub_agent_manager") as mock_manager,
    ):
        mock_manager.create_llm_chat_task.return_value = None
        llm_chat, _ = await resolve_llm_chat_task_for_session(
            "sess1-sub-researcher-deadbeef", root_group
        )

    assert llm_chat is not main_task
    assert llm_chat is None
