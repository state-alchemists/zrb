"""Tests for chat_api_route.py's LLM-task resolution."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.runner.chat.chat_api_route import resolve_llm_chat_task_for_session


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
    """A session_id shaped like a persisted delegation transcript must be
    driven by that sub-agent's own task, not the shared main chat task."""
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
    """create_llm_chat_task returns None for an unknown/agent_instance-backed
    definition — the error must name the specific agent, not a generic one."""
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
    """A delegated session_id must not silently resume as the main agent even
    when the shared task is available -- persona mismatch would be a real
    surprise for whoever resumes it."""
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
