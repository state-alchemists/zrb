"""Tests for the task `chat_api_route` resolves `llm chat` to, and the check that reads it.

`get_llm_chat_task` reaches the chat task through `extract_node`, so it reads
the tree the way the web does: a `cli_only` override is not served here. That is
an answer about serving, not about permission, and `_require_auth` must not read
it as "no chat task is registered".
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.group.group import Group
from zrb.runner.chat.chat_api_route import _require_auth, get_llm_chat_task
from zrb.task.base.base_task import BaseTask


def _root_with_chat(cli_only: bool = False) -> tuple[Group, BaseTask]:
    chat = BaseTask(name="chat", cli_only=cli_only)
    llm = Group(name="llm")
    llm.add_task(chat)
    root = Group(name="root")
    root.add_group(llm)
    return root, chat


@pytest.mark.asyncio
async def test_get_llm_chat_task_finds_the_registered_chat_task():
    root, chat = _root_with_chat()
    assert await get_llm_chat_task(root) is chat


@pytest.mark.asyncio
async def test_get_llm_chat_task_returns_none_when_missing():
    """Internal helper returns None when the chat node isn't registered."""
    assert await get_llm_chat_task(Group(name="root")) is None


@pytest.mark.asyncio
async def test_get_llm_chat_task_ignores_a_cli_only_chat_override():
    """A project shadowing `llm chat` with a CLI-only task is not serving it
    to browsers through this route."""
    root, _ = _root_with_chat(cli_only=True)
    assert await get_llm_chat_task(root) is None


@pytest.mark.asyncio
async def test_require_auth_forbids_a_chat_task_kept_off_the_web():
    """A hidden chat task is forbidden, not unregistered.

    The lookup answers nothing for a `cli_only` override, and reading that as
    "no chat task is registered" let every chat endpoint through with no access
    check: listing sessions, reading their messages, uploading attachments.
    """
    root, _ = _root_with_chat(cli_only=True)
    caller = MagicMock()
    caller.can_access_task.return_value = True

    with patch(
        "zrb.runner.chat.chat_api_route.get_user_from_request",
        new=AsyncMock(return_value=caller),
    ):
        response = await _require_auth(MagicMock(), root, MagicMock())

    assert response is not None
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_require_auth_allows_an_accessible_chat_task():
    """The visible, accessible case still passes through untouched."""
    root, chat = _root_with_chat()
    caller = MagicMock()
    caller.can_access_task.return_value = True

    with patch(
        "zrb.runner.chat.chat_api_route.get_user_from_request",
        new=AsyncMock(return_value=caller),
    ):
        response = await _require_auth(MagicMock(), root, MagicMock())

    assert response is None
    caller.can_access_task.assert_called_once_with(chat)


@pytest.mark.asyncio
async def test_require_auth_allows_when_no_chat_task_is_registered():
    """A project without `llm chat` has no chat to guard."""
    caller = MagicMock()

    with patch(
        "zrb.runner.chat.chat_api_route.get_user_from_request",
        new=AsyncMock(return_value=caller),
    ):
        response = await _require_auth(MagicMock(), Group(name="root"), MagicMock())

    assert response is None
