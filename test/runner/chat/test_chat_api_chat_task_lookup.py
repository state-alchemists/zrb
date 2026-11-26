"""Tests for the task `chat_api_route` resolves `llm chat` to.

`get_llm_chat_task` reaches the chat task through `extract_node`, so it reads
the tree the way the web does: a `cli_only` override is not served here.
"""

import pytest

from zrb.group.group import Group
from zrb.runner.chat.chat_api_route import get_llm_chat_task
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
