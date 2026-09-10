from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.deferred_calls import process_deferred_requests
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


def _ask_policy():
    """A permission policy that returns ASK for any tool (the 'hard ask')."""
    from zrb.llm.permission import ASK

    policy = MagicMock()
    policy.decide.return_value = ASK
    return policy


@pytest.mark.asyncio
async def test_permission_policy_deny_blocks():
    """Priority 2: a permission policy returning DENY blocks (lines 251-255)."""
    from zrb.llm.permission import DENY

    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    policy = MagicMock()
    policy.decide.return_value = DENY

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = "{bad json"
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=policy),
        patch("zrb.llm.permission.tool_capability", return_value="cap"),
    ):
        result = await process_deferred_requests(result_output, None, ui, hook_manager)

    assert isinstance(result.approvals["call_1"], MockToolDenied)
    # A non-JSON string coerces to {} (lines 242-243) before policy.decide.
    policy.decide.assert_called_once_with("test_tool", "cap", {})


@pytest.mark.asyncio
async def test_yolo_auto_approves_with_no_policy_opinion():
    """Priority 3: YOLO=True auto-approves when no policy has an opinion (lines
    289-291)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    tool_handler = MagicMock(spec=ToolCallHandler)
    tool_handler.check_policies = AsyncMock(return_value=None)
    tool_handler.handle = AsyncMock(return_value=MockToolDenied("should not reach"))

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
        patch("zrb.llm.agent_state.get_current_yolo", return_value=True),
    ):
        result = await process_deferred_requests(
            result_output, tool_handler, ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    tool_handler.handle.assert_not_called()
    # YOLO auto-approve never prompts, so PermissionRequest must not fire.
    assert _permission_request_calls(hook_manager) == []


@pytest.mark.asyncio
async def test_approval_channel_with_invalid_json_string_args():
    """Priority 4: a non-JSON string args value yields empty tool_args on the
    ApprovalContext (lines 330-331)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = MockToolApproved("ok")
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = "not-json{"
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=None),
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
        patch("zrb.llm.agent_state.get_current_yolo", return_value=None),
    ):
        result = await process_deferred_requests(
            result_output, None, ui, hook_manager, approval_channel=approval_channel
        )

    assert isinstance(result.approvals["call_1"], MockToolApproved)
    context = approval_channel.request_approval.call_args[0][0]
    assert context.tool_args == {}


@pytest.mark.asyncio
async def test_no_approval_mechanism_with_hard_ask_denies():
    """Fallthrough: hard-ASK policy with no approval channel and no CLI
    confirmation denies rather than silently approving (lines 359-364)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    call = MagicMock()
    call.tool_name = "run_shell_command"
    call.args = {"cmd": "ls"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=_ask_policy()),
        patch("zrb.llm.permission.tool_capability", return_value=None),
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
        patch("zrb.llm.agent_state.get_current_yolo", return_value=None),
    ):
        # effective_tool_confirmation is neither a ToolCallHandler nor callable.
        result = await process_deferred_requests(
            result_output, object(), ui, hook_manager
        )

    assert isinstance(result.approvals["call_1"], MockToolDenied)


@pytest.mark.asyncio
async def test_no_approval_mechanism_without_ask_returns_none():
    """Fallthrough: no policy opinion and no approval mechanism returns None,
    which becomes the approval result for the call (line 366)."""
    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

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
        patch("zrb.llm.agent_state.get_current_yolo", return_value=None),
    ):
        result = await process_deferred_requests(
            result_output, object(), ui, hook_manager
        )

    assert result.approvals["call_1"] is None


@pytest.mark.asyncio
async def test_interactive_exit_plan_mode_still_prompts():
    """Interactive mode must NOT short-circuit the plan gate: ExitPlanMode's
    ASK still flows to the CLI confirmation handler so the user can approve."""
    ui = MagicMock(spec=AnyUI)
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
async def test_edited_approval_records_override_note_for_execution():
    """An approval channel that edits a call's args registers the change so
    `SafeToolsetWrapper.call_tool` can tell the model what actually ran
    (override_registry, see docs/adr/adr-0085.md)."""
    from zrb.llm.tool_call.override_registry import pop_override_note

    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    edited = MockToolApproved("ChannelApproved")
    edited.override_args = {"path": "b.txt"}
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = edited
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"path": "a.txt"}
    call.tool_call_id = "call_1"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    note = pop_override_note("call_1")
    assert note is not None
    assert "path" in note
    assert "b.txt" in note


@pytest.mark.asyncio
async def test_unedited_approval_does_not_record_override_note():
    """override_args left unset (approved as-is) must not touch the registry."""
    from zrb.llm.tool_call.override_registry import pop_override_note

    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = MockToolApproved("ChannelApproved")
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"path": "a.txt"}
    call.tool_call_id = "call_unedited"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    assert pop_override_note("call_unedited") is None


@pytest.mark.asyncio
async def test_edited_approval_with_unparseable_original_args_still_records_note():
    """call.args that fails to parse must not silently drop the override — the
    model still needs to learn its edited call ran with different arguments,
    even without a clean "before" baseline to diff against."""
    from zrb.llm.tool_call.override_registry import pop_override_note

    ui = MagicMock(spec=AnyUI)
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    approval_channel = MagicMock()
    edited = MockToolApproved("ChannelApproved")
    edited.override_args = {"path": "b.txt"}
    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = edited
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = "not-valid-json{"
    call.tool_call_id = "call_unparseable"

    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []

    await process_deferred_requests(
        result_output, None, ui, hook_manager, approval_channel=approval_channel
    )

    note = pop_override_note("call_unparseable")
    assert note is not None
    assert "path" in note
    assert "b.txt" in note
