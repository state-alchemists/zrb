"""Sandbox-escape requests must never be auto-approved by any policy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.tool_call.tool_policy.auto_approve import auto_approve
from zrb.llm.tool_call.tool_policy.bash_validation import bash_safe_command_policy


def _call(tool_name, args):
    call = MagicMock()
    call.tool_name = tool_name
    call.args = args
    return call


@pytest.mark.asyncio
async def test_bash_policy_never_auto_approves_escape():
    """Even a read-only command must reach a human when escaping the sandbox."""
    policy = bash_safe_command_policy()
    call = _call("Bash", {"command": "ls -la", "dangerously_skip_sandbox": True})
    next_handler = AsyncMock(return_value="ask_user")

    result = await policy(MagicMock(), call, next_handler)

    assert result == "ask_user"
    assert next_handler.called is True


@pytest.mark.asyncio
async def test_bash_policy_still_approves_safe_command_without_escape():
    from pydantic_ai import ToolApproved

    policy = bash_safe_command_policy()
    call = _call("Bash", {"command": "ls -la", "dangerously_skip_sandbox": False})
    next_handler = AsyncMock(return_value="ask_user")

    result = await policy(MagicMock(), call, next_handler)

    assert isinstance(result, ToolApproved)


@pytest.mark.asyncio
async def test_auto_approve_never_approves_escape():
    policy = auto_approve("Shell")
    call = _call("Shell", {"command": "ls", "dangerously_skip_sandbox": True})
    next_handler = AsyncMock(return_value="ask_user")

    result = await policy(MagicMock(), call, next_handler)

    assert result == "ask_user"
    assert next_handler.called is True


@pytest.mark.asyncio
async def test_auto_approve_still_approves_without_escape():
    from pydantic_ai import ToolApproved

    policy = auto_approve("Shell")
    call = _call("Shell", {"command": "ls"})
    next_handler = AsyncMock(return_value="ask_user")

    result = await policy(MagicMock(), call, next_handler)

    assert isinstance(result, ToolApproved)


@pytest.mark.asyncio
async def test_auto_approve_escape_in_json_string_args():
    policy = auto_approve("Shell")
    call = _call("Shell", '{"command": "ls", "dangerously_skip_sandbox": true}')
    next_handler = AsyncMock(return_value="ask_user")

    result = await policy(MagicMock(), call, next_handler)

    assert result == "ask_user"
