"""Tests for run-setup dependency resolution (yolo inheritance semantics)."""

import pytest

from zrb.llm.agent.run.setup import resolve_context_dependencies
from zrb.llm.agent_state import current_hook_manager, current_yolo
from zrb.llm.hook.manager import HookManager


def test_yolo_none_inherits_parent_context():
    token = current_yolo.set(True)
    try:
        _, _, effective_yolo, _, _ = resolve_context_dependencies(
            None, None, None, None, None
        )
        assert effective_yolo is True
    finally:
        current_yolo.reset(token)


def test_yolo_explicit_false_stays_false():
    """An explicit False must opt out of an inherited YOLO context."""
    token = current_yolo.set(True)
    try:
        _, _, effective_yolo, _, _ = resolve_context_dependencies(
            None, None, False, None, None
        )
        assert effective_yolo is False
    finally:
        current_yolo.reset(token)


def test_yolo_explicit_true_wins_over_unyolo_parent():
    _, _, effective_yolo, _, _ = resolve_context_dependencies(
        None, None, True, None, None
    )
    assert effective_yolo is True


def test_yolo_defaults_to_false_without_context():
    _, _, effective_yolo, _, _ = resolve_context_dependencies(
        None, None, None, None, None
    )
    assert effective_yolo is False


@pytest.mark.asyncio
async def test_terminal_approval_asks_the_multi_ui_primary_child():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from zrb.llm.approval.any_approval_channel import ApprovalContext
    from zrb.llm.ui.multi_ui import MultiUI

    first, primary = MagicMock(), MagicMock()
    for child in (first, primary):
        child.tool_call_handler = None
        child.ask_user = AsyncMock(return_value="n")
    remote = MagicMock()
    remote.request_approval = AsyncMock(side_effect=lambda _: asyncio.Future())

    _, _, _, channel, _ = resolve_context_dependencies(
        MultiUI([first, primary], main_ui_index=1), None, None, remote, None
    )
    result = await channel.request_approval(
        ApprovalContext(tool_name="Write", tool_args={}, tool_call_id="1")
    )

    assert result.approved is False
    primary.ask_user.assert_awaited_once()
    first.ask_user.assert_not_awaited()


def test_hook_manager_none_inherits_parent_context():
    """A nested run uses the manager its parent runs on, the way it already
    inherits the UI and the authorization state. Falling through to the
    singleton instead meant a deny rule a task registered with
    `append_hook_factory` did not bind a delegated sub-agent's tools."""
    parent = HookManager(search_dirs=[])
    token = current_hook_manager.set(parent)
    try:
        *_, effective_hook_manager = resolve_context_dependencies(
            None, None, None, None, None
        )
        assert effective_hook_manager is parent
    finally:
        current_hook_manager.reset(token)


def test_hook_manager_explicit_wins_over_inherited_context():
    parent, explicit = HookManager(search_dirs=[]), HookManager(search_dirs=[])
    token = current_hook_manager.set(parent)
    try:
        *_, effective_hook_manager = resolve_context_dependencies(
            None, None, None, None, explicit
        )
        assert effective_hook_manager is explicit
    finally:
        current_hook_manager.reset(token)


def test_hook_manager_falls_back_to_the_singleton_without_context():
    from zrb.llm.agent.run import setup

    *_, effective_hook_manager = resolve_context_dependencies(
        None, None, None, None, None
    )
    assert effective_hook_manager is setup.default_hook_manager
