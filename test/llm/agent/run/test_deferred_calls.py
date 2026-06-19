import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests,
    rebuild_for_denials,
)
from zrb.llm.hook.executor import HookExecutionResult
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
    with (
        patch("pydantic_ai.DeferredToolResults", MockDeferredToolResults),
        patch("pydantic_ai.ToolApproved", MockToolApproved),
        patch("pydantic_ai.ToolDenied", MockToolDenied),
    ):
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
        tool_name="test_tool",
        tool_input={"arg1": "val1"},
    )
    # PostToolUse no longer fires from the approval path — it fires at execution
    # time in SafeToolsetWrapper.call_tool. So only PRE_TOOL_USE is seen here.
    fired_events = [c.args[0] for c in hook_manager.execute_hooks.call_args_list]
    assert HookEvent.POST_TOOL_USE not in fired_events


@pytest.mark.asyncio
async def test_process_deferred_requests_denied_by_hook():
    """A PreToolUse hook with permissionDecision="deny" cancels the call."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookExecutionResult(
        success=True,
        permission_decision="deny",
        permission_decision_reason="blocked by policy",
    )
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
    assert result.approvals["call_1"].message == "blocked by policy"


@pytest.mark.asyncio
async def test_process_deferred_requests_allowed_by_hook():
    """A PreToolUse hook with permissionDecision="allow" skips the approval
    cascade entirely (the tool handler is never consulted)."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookExecutionResult(success=True, permission_decision="allow")
    hook_manager.execute_hooks = AsyncMock(return_value=[hook_result])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=MockToolDenied("would deny"))

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

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    tool_handler.check_policies.assert_not_called()


@pytest.mark.asyncio
async def test_process_deferred_requests_modified_by_hook():
    """A PreToolUse hook with updatedInput rewrites the tool arguments."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookExecutionResult(success=True, updated_input={"arg1": "modified"})
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


def _permission_request_calls(hook_manager):
    return [
        c
        for c in hook_manager.execute_hooks.call_args_list
        if c.args and c.args[0] == HookEvent.PERMISSION_REQUEST
    ]


@pytest.mark.asyncio
async def test_permission_request_fired_when_user_is_prompted():
    """Reaching an interactive approval (here, the approval channel) fires
    PermissionRequest so input-required hooks/sounds ring."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = MockToolApproved("ok")
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "run_shell_command"
    call.args = {"cmd": "ls"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    perm_calls = _permission_request_calls(hook_manager)
    assert len(perm_calls) == 1
    assert perm_calls[0].args[1]["tool"] == "run_shell_command"


@pytest.mark.asyncio
async def test_permission_request_not_fired_when_auto_approved():
    """An auto-approved call (tool policy) never prompts, so PermissionRequest
    must NOT fire — no false "needs approval" ding."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=MockToolApproved("ok"))

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(result_output, tool_handler, ui, hook_manager)

    assert _permission_request_calls(hook_manager) == []


def _route_execute_hooks(mapping):
    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


@pytest.mark.asyncio
async def test_permission_request_hook_auto_allows():
    """A PermissionRequest hook returning decision.behavior="allow" approves the
    call without consulting the interactive approval channel."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    allow = HookExecutionResult(
        success=True, hook_specific_output={"decision": {"behavior": "allow"}}
    )
    hook_manager.execute_hooks = _route_execute_hooks(
        {HookEvent.PERMISSION_REQUEST: [allow]}
    )

    approval_channel = MagicMock()
    approval_channel.request_approval = AsyncMock()

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    approval_channel.request_approval.assert_not_called()


@pytest.mark.asyncio
async def test_permission_request_hook_auto_denies():
    """A PermissionRequest hook returning decision.behavior="deny" denies the
    call without consulting the interactive approval channel."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    deny = HookExecutionResult(
        success=True, hook_specific_output={"decision": {"behavior": "deny"}}
    )
    hook_manager.execute_hooks = _route_execute_hooks(
        {HookEvent.PERMISSION_REQUEST: [deny]}
    )

    approval_channel = MagicMock()
    approval_channel.request_approval = AsyncMock()

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    approval_channel.request_approval.assert_not_called()


@pytest.mark.asyncio
async def test_permission_request_not_fired_when_auto_approved_via_bound_method():
    """Interactive mode: BaseUI._confirm_tool_execution wraps a ToolCallHandler.
    When the underlying handler auto-approves, PermissionRequest must NOT fire
    even though effective_tool_confirmation is a bound method, not a
    ToolCallHandler directly."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    # Simulate BaseUI with tool_call_handler property
    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=MockToolApproved("ok"))

    class _FakeBaseUI:
        tool_call_handler = tool_handler

    bound_ui = _FakeBaseUI()

    # bound method: __self__ points to the FakeBaseUI instance
    async def _confirm(call):
        return await bound_ui.tool_call_handler.handle(ui, call)

    _confirm.__self__ = bound_ui

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(result_output, _confirm, ui, hook_manager)

    assert _permission_request_calls(hook_manager) == []


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


@pytest.mark.asyncio
async def test_process_deferred_requests_always_auto_approve_bypasses_handler():
    """Priority 0: intrinsically auto-approved tools never reach the handler.

    AskUserQuestion *is* the user interaction; a separate approval prompt is
    redundant. The cascade must approve it before any tool-policy check or CLI
    fallback, in every path. See ADR-0062.
    """
    from zrb.llm.tool_call.always_approve import register_always_auto_approve

    register_always_auto_approve("MyInteractiveTool")

    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    # A handler that would *deny* if consulted — proves Priority 0 short-circuits.
    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(
        return_value=MockToolDenied("should not run")
    )
    tool_handler.handle = AsyncMock(return_value=MockToolDenied("should not run"))

    call = MagicMock()
    call.tool_name = "MyInteractiveTool"
    call.args = {"questions": []}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, tool_handler, ui, hook_manager
    )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    tool_handler.check_policies.assert_not_called()
    tool_handler.handle.assert_not_called()


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
    # PostToolUseFailure no longer fires from the approval path: a denied call is
    # a permission outcome, not an execution failure. It fires only when a tool
    # actually raises, in SafeToolsetWrapper.call_tool.
    fired_events = [c.args[0] for c in hook_manager.execute_hooks.call_args_list]
    assert HookEvent.POST_TOOL_USE_FAILURE not in fired_events


def _ask_policy():
    """A permission policy that returns ASK for any tool (the 'hard ask')."""
    from zrb.llm.permission import ASK

    policy = MagicMock()
    policy.decide.return_value = ASK
    return policy


@pytest.mark.asyncio
async def test_noninteractive_exit_plan_mode_is_auto_approved():
    """Non-interactive + hard-ASK on ExitPlanMode auto-approves instead of
    blocking on a stdin prompt no one can answer. The plan gate is a no-op
    without a user to read the plan. See ADR-0067."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    # A CLI handler that would (wrongly) run if reached — proves we short-circuit.
    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=None)
    tool_handler.handle = AsyncMock(return_value=MockToolDenied("should not reach"))

    call = MagicMock()
    call.tool_name = "ExitPlanMode"
    call.args = {"plan": "do the thing"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=_ask_policy()),
        patch("zrb.llm.permission.tool_capability", return_value=None),
        patch("zrb.llm.tool.ask.get_interactive_mode", return_value=False),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    tool_handler.handle.assert_not_called()
    # The gate auto-resolves, so it must not ding a "needs approval" hook.
    assert _permission_request_calls(hook_manager) == []


@pytest.mark.asyncio
async def test_noninteractive_other_ask_tool_is_denied():
    """Non-interactive + hard-ASK on a non-plan tool denies rather than running
    it unattended (preserving the hard-ASK safety design) or blocking forever.
    See ADR-0067."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=None)
    tool_handler.handle = AsyncMock(return_value=MockToolApproved("should not reach"))

    call = MagicMock()
    call.tool_name = "run_shell_command"
    call.args = {"cmd": "rm -rf /"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=_ask_policy()),
        patch("zrb.llm.permission.tool_capability", return_value=None),
        patch("zrb.llm.tool.ask.get_interactive_mode", return_value=False),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    tool_handler.handle.assert_not_called()


@pytest.mark.asyncio
async def test_pretooluse_ask_forces_prompt_over_auto_approve():
    """A PreToolUse hook returning permissionDecision="ask" forces the interactive
    prompt even when a tool policy would otherwise auto-approve the call."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    ask = HookExecutionResult(success=True, permission_decision="ask")
    hook_manager.execute_hooks = _route_execute_hooks({HookEvent.PRE_TOOL_USE: [ask]})

    # Tool policy WOULD auto-approve, but the hook's "ask" must override it and
    # route to the interactive CLI handler.
    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=MockToolApproved("auto"))
    cli_result = MockToolApproved("user approved")
    tool_handler.handle = AsyncMock(return_value=cli_result)

    call = MagicMock()
    call.tool_name = "run_shell_command"
    call.args = {"cmd": "ls"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=None),
        patch("zrb.llm.tool.ask.get_interactive_mode", return_value=True),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert result.approvals["call_1"] == cli_result
    tool_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_interactive_exit_plan_mode_still_prompts():
    """Interactive mode must NOT short-circuit the plan gate: ExitPlanMode's
    ASK still flows to the CLI confirmation handler so the user can approve."""
    ui = MagicMock(spec=UIProtocol)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=None)
    cli_result = MockToolApproved("user approved")
    tool_handler.handle = AsyncMock(return_value=cli_result)

    call = MagicMock()
    call.tool_name = "ExitPlanMode"
    call.args = {"plan": "do the thing"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=_ask_policy()),
        patch("zrb.llm.permission.tool_capability", return_value=None),
        patch("zrb.llm.tool.ask.get_interactive_mode", return_value=True),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert result.approvals["call_1"] == cli_result
    tool_handler.handle.assert_called_once()
