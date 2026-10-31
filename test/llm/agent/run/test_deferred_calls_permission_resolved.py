"""An approval's answer reaches the hooks, not only the question.

`PermissionRequest` fires while the user is being asked and `PostToolUse` only once the tool
has finished, so the moment the answer arrives had no event at all. These tests pin the two
things a listener depends on: that the event arrives at all, and that "asked, nobody answered"
does not arrive as "denied".
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.deferred_calls import process_deferred_requests
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.ui.any_ui import AnyUI


class MockToolApproved:
    def __init__(self, value=None):
        self.value = value


class MockToolDenied:
    def __init__(self, message):
        self.message = message


class MockDeferredToolResults:
    def __init__(self, calls=None, approvals=None, metadata=None):
        self.calls = calls if calls is not None else {}
        self.approvals = approvals if approvals is not None else {}
        self.metadata = metadata


@pytest.fixture(autouse=True)
def mock_pydantic_ai_imports():
    with (
        patch("pydantic_ai.DeferredToolResults", MockDeferredToolResults),
        patch("pydantic_ai.ToolApproved", MockToolApproved),
        patch("pydantic_ai.ToolDenied", MockToolDenied),
    ):
        yield


def _resolved_calls(hook_manager):
    return [
        c
        for c in hook_manager.execute_hooks.call_args_list
        if c.args and c.args[0] == HookEvent.PERMISSION_RESOLVED
    ]


def _waiting_for(verdict):
    """A deferred call waiting on an approval channel that answers with *verdict*."""
    call = MagicMock()
    call.tool_name = "run_shell_command"
    call.args = json.dumps({"cmd": "ls"})
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    channel = MagicMock()
    answer = MagicMock()
    answer.to_pydantic_result.return_value = verdict
    channel.request_approval = AsyncMock(return_value=answer)

    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])
    return call, result_output, channel, hook_manager


@pytest.mark.asyncio
async def test_permission_resolved_fires_when_the_answer_arrives():
    """The wait ends when the approval comes back, not when the tool does.

    A listener that showed "waiting for you" has no other event to clear it: PostToolUse
    fires at execution, so the gap is as long as the tool runs.
    """
    ui = MagicMock(spec=AnyUI)
    call, result_output, channel, hook_manager = _waiting_for(MockToolApproved("ok"))

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=channel
    )

    resolved = _resolved_calls(hook_manager)
    assert len(resolved) == 1
    assert resolved[0].args[1] == {"tool": "run_shell_command", "approved": True}
    # It follows the request, which is what lets an observer pair them up.
    events = [c.args[0] for c in hook_manager.execute_hooks.call_args_list]
    assert events.index(HookEvent.PERMISSION_REQUEST) < events.index(
        HookEvent.PERMISSION_RESOLVED
    )


@pytest.mark.asyncio
async def test_permission_resolved_says_neither_when_the_channel_gave_no_verdict():
    """No verdict is not a denial: the policy answers next, and a listener should
    not clear a waiting pose on a "no" nobody said."""
    ui = MagicMock(spec=AnyUI)
    call, result_output, channel, hook_manager = _waiting_for(None)

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=channel
    )

    resolved = _resolved_calls(hook_manager)
    assert len(resolved) == 1
    assert resolved[0].args[1] == {"tool": "run_shell_command", "approved": None}


@pytest.mark.asyncio
async def test_permission_resolved_carries_a_denial():
    """Approved and denied reach the listener as true and false, and a denied call is
    still dropped from execution after the announcement."""
    ui = MagicMock(spec=AnyUI)
    call, result_output, channel, hook_manager = _waiting_for(MockToolDenied("because"))

    result = await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=channel
    )

    resolved = _resolved_calls(hook_manager)
    assert len(resolved) == 1
    assert resolved[0].args[1] == {"tool": "run_shell_command", "approved": False}
    assert isinstance(result.approvals["call_1"], MockToolDenied)
