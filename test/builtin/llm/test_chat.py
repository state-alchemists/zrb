"""Delegate tool registration on the built-in chat task follows the profile.

``minimal`` is the one profile that drops delegation (ADR-0049): the roster
schema and fan-out machinery never reach a ~3B model. Drive the public tool
factory against the environment and assert on what it produces.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.llm.chat import llm_chat
from zrb.context.shared_context import SharedContext
from zrb.llm.tool.delegate import AgentTaskResult
from zrb.llm.tool.delegate_background import (
    create_background_delegate_tool,
    get_background_registry,
)
from zrb.llm.tool.registry import tool_name


def _names(profile: str, model: str | None = None) -> list[str]:
    with patch.dict("os.environ", {"ZRB_LLM_PROFILE": profile}):
        context = SharedContext(input={"model": model or ""})
        delegate_names = {
            "DelegateToAgent",
            "SearchAgent",
            "DelegateToAgentBackground",
            "GetDelegationResult",
        }
        return [
            name
            for tool in llm_chat.get_all_tools(context)
            if (name := tool_name(tool)) in delegate_names
        ]


def test_standard_profile_registers_the_delegate_tools():
    assert set(_names("standard")) == {
        "DelegateToAgent",
        "SearchAgent",
        "DelegateToAgentBackground",
        "GetDelegationResult",
    }


def test_capable_profile_registers_the_delegate_tools():
    assert set(_names("capable")) == {
        "DelegateToAgent",
        "SearchAgent",
        "DelegateToAgentBackground",
        "GetDelegationResult",
    }


def test_minimal_profile_registers_no_delegate_tools():
    assert _names("minimal") == []


def test_auto_profile_uses_the_run_model_for_delegate_registration():
    assert _names("auto", "ollama:qwen2.5:3b") == []


@pytest.mark.asyncio
async def test_background_delegation_notice_reaches_the_chat_live_context():
    """The parent must learn a finished background delegation on its own next
    turn, instead of relying on the model remembering to poll
    GetDelegationResult — driven end-to-end through the same
    ``prompt_manager`` the built-in chat task composes its prompt from."""

    async def quick_task(*args, **kwargs):
        return AgentTaskResult("agent", "ok", None)

    delegate = create_background_delegate_tool(MagicMock())
    try:
        with (
            patch(
                "zrb.llm.tool.delegate_background.run_agent_task",
                side_effect=quick_task,
            ),
            patch(
                "zrb.llm.tool.delegate_background.get_current_ui",
                return_value=MagicMock(),
            ),
        ):
            msg = await delegate("agent", "deliver", "do it", [])
            for _ in range(5):
                await asyncio.sleep(0)

        handle = msg.split("Handle:")[1].split(".")[0].strip()
        live_context = llm_chat.prompt_manager.create_live_context(SharedContext())
        assert handle in live_context
        assert "GetDelegationResult" in live_context
    finally:
        get_background_registry().cancel_all()
