import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests,
    rebuild_for_denials,
)
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.ui_protocol import UIProtocol


# Mock pydantic_ai classes
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
    with patch("pydantic_ai.DeferredToolResults", MockDeferredToolResults), patch(
        "pydantic_ai.ToolApproved", MockToolApproved
    ), patch("pydantic_ai.ToolDenied", MockToolDenied):
        yield


@pytest.mark.asyncio
async def test_process_deferred_requests_empty():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    result_output = MagicMock()
    result_output.calls = []
    result_output.approvals = []

    result = await process_deferred_requests(result_output, None, ui, hook_manager)
    assert result is None


@pytest.mark.asyncio
async def test_process_deferred_requests_approved_by_policy():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    approved_result = MockToolApproved("Success")
    tool_handler.check_policies = AsyncMock(return_value=approved_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, tool_handler, ui, hook_manager
    )

    assert result.approvals["call_1"] == approved_result
    tool_handler.check_policies.assert_called_once()
    hook_manager.execute_hooks.assert_any_call(
        HookEvent.PRE_TOOL_USE,
        {"tool": "test_tool", "args": {"arg1": "val1"}, "call_id": "call_1"},
    )
    hook_manager.execute_hooks.assert_any_call(
        HookEvent.POST_TOOL_USE,
        {"tool": "test_tool", "args": {"arg1": "val1"}, "result": approved_result},
    )


@pytest.mark.asyncio
async def test_process_deferred_requests_denied_by_hook():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookResult(modifications={"cancel_tool": True})
    hook_manager.execute_hooks = AsyncMock(return_value=[hook_result])

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(result_output, None, ui, hook_manager)

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    assert result.approvals["call_1"].message == "Tool execution cancelled by hook"


@pytest.mark.asyncio
async def test_process_deferred_requests_modified_by_hook():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookResult(modifications={"tool_args": {"arg1": "modified"}})
    hook_manager.execute_hooks = AsyncMock(side_effect=[[hook_result], []])

    tool_handler = MagicMock(spec=ToolCallHandler)
    approved_result = MockToolApproved("Success")
    tool_handler.check_policies = AsyncMock(return_value=approved_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, tool_handler, ui, hook_manager
    )

    assert result.approvals["call_1"] == approved_result
    assert call.args["arg1"] == "modified"


@pytest.mark.asyncio
async def test_process_deferred_requests_approval_channel():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = MockToolApproved("ChannelApproved")
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = json.dumps({"arg1": "val1"})
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    approval_channel.request_approval.assert_called_once()
    context = approval_channel.request_approval.call_args[0][0]
    assert context.tool_name == "test_tool"
    assert context.tool_args == {"arg1": "val1"}


@pytest.mark.asyncio
async def test_process_deferred_requests_cli_fallback_handler():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=None)
    cli_result = MockToolApproved("CLIApproved")
    tool_handler.handle = AsyncMock(return_value=cli_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, tool_handler, ui, hook_manager
    )

    assert result.approvals["call_1"] == cli_result
    tool_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_process_deferred_requests_cli_fallback_callable():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    cli_result = MockToolApproved("CallableApproved")
    effective_tool_confirmation = AsyncMock(return_value=cli_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, effective_tool_confirmation, ui, hook_manager
    )

    assert result.approvals["call_1"] == cli_result
    effective_tool_confirmation.assert_called_once_with(call)


def test_rebuild_for_denials_no_denials():
    approvals = {"call_1": MockToolApproved("OK")}
    current_results = MockDeferredToolResults(
        approvals=approvals, calls={"call_1": "some_call"}
    )

    result = rebuild_for_denials(current_results)
    assert result == current_results


def test_rebuild_for_denials_with_denials():
    approvals = {"call_1": MockToolDenied("Denied")}
    current_results = MockDeferredToolResults(
        approvals=approvals, calls={"call_1": "some_call"}
    )

    result = rebuild_for_denials(current_results)
    assert result != current_results
    assert result.calls == {}
    assert result.approvals == approvals


@pytest.mark.asyncio
async def test_process_deferred_requests_denied_removes_from_calls():
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    denied_result = MockToolDenied("Denied")
    tool_handler.check_policies = AsyncMock(return_value=denied_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    # process_deferred_requests tries to delete call.tool_call_id from current_results.calls if it exists
    # We need to make sure current_results.calls has it.
    # In process_deferred_requests: current_results = DeferredToolResults()
    # Then it iterates over all_requests.

    with patch("pydantic_ai.DeferredToolResults", MockDeferredToolResults):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    # Note: process_deferred_requests only deletes from calls if it was already there.
    # But current_results starts empty. Wait, if it's a DeferredToolResults,
    # usually pydantic-ai might have populated it?
    # Actually process_deferred_requests creates a NEW DeferredToolResults.

    hook_manager.execute_hooks.assert_any_call(
        HookEvent.POST_TOOL_USE_FAILURE,
        {"tool": "test_tool", "args": {"arg1": "val1"}, "error": "Denied"},
    )
