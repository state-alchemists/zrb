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


def _permission_request_calls(hook_manager):
    return [
        c
        for c in hook_manager.execute_hooks.call_args_list
        if c.args and c.args[0] == HookEvent.PERMISSION_REQUEST
    ]


def _route_execute_hooks(mapping):
    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


def _ask_policy():
    """A permission policy that returns ASK for any tool (the 'hard ask')."""
    from zrb.llm.permission import ASK

    policy = MagicMock()
    policy.decide.return_value = ASK
    return policy


@pytest.mark.asyncio
async def test_process_deferred_requests_always_auto_approve_bypasses_handler():
    """Priority 0: intrinsically auto-approved tools never reach the handler.

    AskUserQuestion *is* the user interaction; a separate approval prompt is
    redundant. The cascade must approve it before any tool-policy check or CLI
    fallback, in every path. See ADR-0062.
    """
    from zrb.llm.tool_call.always_approve import register_always_auto_approve

    register_always_auto_approve("MyInteractiveTool")

    ui = MagicMock(spec=AnyUI)
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


def test_rebuild_for_denials_discards_overrides_for_cleared_calls():
    """A call that was edited-and-approved but shares a batch with a denied
    call must not leak in override_registry once its whole batch is cleared
    (see docs/adr/adr-0085.md and override_registry.discard_override)."""
    from zrb.llm.tool_call.override_registry import pop_override_note, record_override

    record_override("call_edited", {"path": "a.txt"}, {"path": "b.txt"})

    approvals = {
        "call_edited": MockToolApproved("edited"),
        "call_denied": MockToolDenied("Denied"),
    }
    current_results = MockDeferredToolResults(
        approvals=approvals,
        calls={"call_edited": "some_call", "call_denied": "some_call"},
    )

    rebuild_for_denials(current_results)

    assert pop_override_note("call_edited") is None


@pytest.mark.asyncio
async def test_process_deferred_requests_denied_removes_from_calls():
    ui = MagicMock(spec=AnyUI)
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


@pytest.mark.asyncio
async def test_noninteractive_exit_plan_mode_is_auto_approved():
    """Non-interactive + hard-ASK on ExitPlanMode auto-approves instead of
    blocking on a stdin prompt no one can answer. The plan gate is a no-op
    without a user to read the plan. See ADR-0062."""
    ui = MagicMock(spec=AnyUI)
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
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=False
        ),
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
    See ADR-0062."""
    ui = MagicMock(spec=AnyUI)
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
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=False
        ),
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
    ui = MagicMock(spec=AnyUI)
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
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert result.approvals["call_1"] == cli_result
    tool_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_pretooluse_hook_with_invalid_json_string_args():
    """_as_tool_input: when call.args is a non-JSON string, it is passed to the
    hook unchanged (lines 54-55)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    approved = MockToolApproved("ok")
    tool_handler.check_policies = AsyncMock(return_value=approved)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = "not-valid-json{"
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    result = await process_deferred_requests(
        result_output, tool_handler, ui, hook_manager
    )

    assert result.approvals["call_1"] == approved
    # The raw string was forwarded as tool_input (not parsed).
    hook_manager.execute_hooks.assert_any_call(
        HookEvent.PRE_TOOL_USE,
        {"tool": "test_tool", "args": "not-valid-json{", "call_id": "call_1"},
        tool_name="test_tool",
        tool_input="not-valid-json{",
    )


@pytest.mark.asyncio
async def test_hook_deny_removes_preexisting_call_entry():
    """A PreToolUse deny drops a matching entry from current_results.calls
    (line 108)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_result = HookExecutionResult(
        success=True, permission_decision="deny", permission_decision_reason="no"
    )
    hook_manager.execute_hooks = AsyncMock(return_value=[hook_result])

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    # Seed current_results.calls so the del branch executes. DeferredToolResults
    # is constructed inside process_deferred_requests; patch it to pre-populate.
    class _SeededResults(MockDeferredToolResults):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.calls = {"call_1": "preexisting"}

    with patch("pydantic_ai.DeferredToolResults", _SeededResults):
        result = await process_deferred_requests(result_output, None, ui, hook_manager)

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    assert "call_1" not in result.calls


@pytest.mark.asyncio
async def test_policy_deny_removes_preexisting_call_entry():
    """A cascade DENY drops a matching entry from current_results.calls
    (line 134)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=MockToolDenied("nope"))

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"arg1": "val1"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    class _SeededResults(MockDeferredToolResults):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.calls = {"call_1": "preexisting"}

    with patch("pydantic_ai.DeferredToolResults", _SeededResults):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    assert "call_1" not in result.calls


@pytest.mark.asyncio
async def test_permission_policy_allow_auto_approves():
    """Priority 2: a permission policy returning ALLOW auto-approves (lines
    240-250), including coercing string args to a dict."""
    from zrb.llm.permission import ALLOW

    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    policy = MagicMock()
    policy.decide.return_value = ALLOW

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = json.dumps({"arg1": "val1"})
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=policy),
        patch("zrb.llm.permission.tool_capability", return_value="cap"),
    ):
        result = await process_deferred_requests(result_output, None, ui, hook_manager)

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    # The JSON string args were decoded to a dict before policy.decide.
    policy.decide.assert_called_once_with("test_tool", "cap", {"arg1": "val1"})
