"""Deferred-tool-call processing for `run_agent`.

Each call in a `DeferredToolRequests` goes through the approval cascade in
`_resolve_approval`. A permission DENY is also enforced at execution time by
`gates.permission_gate`.
"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.agent.run.hook_result_extractor import (
    extract_permission_decision,
    extract_pre_tool_decision,
)
from zrb.llm.approval.any_approval_channel import ApprovalContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.permission import ASK
from zrb.llm.tool.ambient_state import get_interactive_mode
from zrb.llm.tool_call.always_approve import is_always_auto_approve
from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.override_registry import discard_override, record_override

if TYPE_CHECKING:
    from pydantic_ai import DeferredToolRequests, DeferredToolResults

    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.ui.any_ui import AnyUI


def _as_tool_input(args: Any) -> Any:
    """Parse JSON-string args into a dict for a hook's ``tool_input``, if possible."""
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


def _record_override_if_edited(call, result: Any) -> None:
    """Record an edited `ToolApproved` so the tool result tells the model its args changed.

    `getattr` because some approval paths return a duck-typed stand-in
    without `override_args`.
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    if not isinstance(result, ToolApproved):
        return
    override_args = getattr(result, "override_args", None)
    if override_args is None:
        return
    # Unparseable args: an empty baseline still reports every edited key.
    original_args = parse_tool_args(call) or {}
    record_override(call.tool_call_id, original_args, override_args)


async def process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: Any,
    ui: AnyUI,
    hook_manager: HookManager,
    approval_channel: "AnyApprovalChannel | None" = None,
) -> "DeferredToolResults | None":
    """Run approval flow for each deferred call. Returns None if there are no requests."""
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

    for call in all_requests:
        # PreToolUse may deny, allow, or rewrite args. Auto-approved tools never
        # reach here and fire it at execution time instead (no double-fire).
        hook_results = await hook_manager.execute_hooks(
            HookEvent.PRE_TOOL_USE,
            {
                "tool": call.tool_name,
                "args": call.args,
                "call_id": call.tool_call_id,
            },
            tool_name=call.tool_name,
            tool_input=_as_tool_input(call.args),
        )
        pre = extract_pre_tool_decision(hook_results)
        if pre.updated_input and isinstance(call.args, dict):
            call.args.update(pre.updated_input)
        if pre.deny:
            current_results.approvals[call.tool_call_id] = ToolDenied(
                pre.reason or "Tool execution blocked by PreToolUse hook"
            )
            if (
                hasattr(current_results, "calls")
                and call.tool_call_id in current_results.calls
            ):
                del current_results.calls[call.tool_call_id]
            continue

        if pre.allow:
            result: Any = ToolApproved()
        else:
            result = await _resolve_approval(
                call,
                ui,
                effective_tool_confirmation,
                approval_channel,
                hook_manager,
                force_ask=pre.force_prompt,
            )
        current_results.approvals[call.tool_call_id] = result
        _record_override_if_edited(call, result)

        if isinstance(result, ToolDenied):
            if (
                hasattr(current_results, "calls")
                and call.tool_call_id in current_results.calls
            ):
                del current_results.calls[call.tool_call_id]
            CFG.LOGGER.debug("Tool denied, removed from calls")

        # PostToolUse fires at execution, not approval.

    return current_results


def rebuild_for_denials(
    current_results: "DeferredToolResults",
) -> "DeferredToolResults":
    """Return a copy with `calls={}` if any approval was denied, else the same object."""
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolResults, ToolDenied

    has_denials = any(
        isinstance(v, ToolDenied) for v in current_results.approvals.values()
    )
    if not has_denials:
        return current_results

    CFG.LOGGER.debug("Tool was denied, clearing calls in deferred results")
    # Dropped calls never execute, so their recorded overrides would leak.
    for tool_call_id in current_results.calls:
        discard_override(tool_call_id)
    return DeferredToolResults(
        calls={},
        approvals=current_results.approvals,
        metadata=current_results.metadata,
    )


async def _resolve_approval(
    call,
    ui: AnyUI,
    effective_tool_confirmation: Any,
    approval_channel: "AnyApprovalChannel | None",
    hook_manager: "HookManager | None" = None,
    force_ask: bool = False,
):
    """Run the approval cascade for a single deferred call.

    Precedence:
      0. Always-approve (intrinsically interactive tools, e.g. AskUserQuestion)
      1. Tool policy
      2. Permission policy (ALLOW→approve, DENY→deny, ASK→force ask)
      3. YOLO (only with no policy ASK)
      4. Approval channel
      5. CLI prompt

    ``force_ask`` (PreToolUse ``permissionDecision: "ask"``) skips the
    auto-approvals at 1-3 but still honors DENY and priority 0. Each stage
    returns a verdict, or None to fall through.
    """
    verdict = _approve_always_auto_approve_tools(call)
    if verdict is not None:
        return verdict

    verdict = await _apply_tool_policies(
        call, ui, effective_tool_confirmation, force_ask
    )
    if verdict is not None:
        return verdict

    policy_decision, verdict = _apply_permission_policy(call, force_ask)
    if verdict is not None:
        return verdict

    verdict = _resolve_non_interactive_ask(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = _approve_via_yolo(policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = await _apply_permission_request_hook(call, hook_manager)
    if verdict is not None:
        return verdict

    if approval_channel is not None:
        return await _request_via_approval_channel(call, approval_channel)

    verdict = await _confirm_via_cli(call, ui, effective_tool_confirmation)
    if verdict is not None:
        return verdict

    # No approval mechanism: a required ASK must not silently approve.
    if policy_decision == ASK or force_ask:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        return ToolDenied(
            "Policy requires approval but no approval channel is configured"
        )
    return None


def _approve_always_auto_approve_tools(call):
    """Priority 0: tools that are the user interaction (e.g. `AskUserQuestion`)."""
    if not is_always_auto_approve(call.tool_name):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_tool_policies(call, ui, effective_tool_confirmation, force_ask):
    """Priority 1: tool policies, from a `ToolCallHandler` or a UI method bound to one."""
    handler = None
    if isinstance(effective_tool_confirmation, ToolCallHandler):
        handler = effective_tool_confirmation
    elif (bound := getattr(effective_tool_confirmation, "__self__", None)) is not None:
        handler = getattr(bound, "tool_call_handler", None)
    if not isinstance(handler, ToolCallHandler):
        return None
    policy_result = await handler.check_policies(ui, call)
    if policy_result is None:
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolDenied

    if not force_ask or isinstance(policy_result, ToolDenied):
        return policy_result
    return None


def _apply_permission_policy(call, force_ask):
    """Priority 2: the permission ruleset.

    Returns the raw decision too: an ASK stops YOLO further down.
    """
    # lazy: tests patch zrb.llm.permission.get_effective_policy and .tool_capability; hoisting bypasses the mock
    from zrb.llm.permission import ALLOW, DENY, get_effective_policy, tool_capability
    from zrb.llm.permission.observability import record_policy_decision

    policy = get_effective_policy()
    if policy is None:
        record_policy_decision(
            layer="permission", decision="none", tool_name=call.tool_name
        )
        return None, None
    raw_args = getattr(call, "args", None) or {}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            raw_args = {}
    decision = policy.decide(call.tool_name, tool_capability(call), raw_args)
    record_policy_decision(
        layer="permission", decision=str(decision), tool_name=call.tool_name
    )
    if decision == ALLOW and not force_ask:
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return decision, ToolApproved()
    if decision == DENY:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        return decision, ToolDenied("Blocked by permission policy")
    return decision, None


def _resolve_non_interactive_ask(call, policy_decision, force_ask):
    """Priority 2b: settle a hard ASK when non-interactive.

    Otherwise it would block forever on the stdin prompt. `ExitPlanMode` is
    approved (nobody reads the plan); anything else is denied.
    """
    if not (policy_decision == ASK or force_ask) or get_interactive_mode():
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved, ToolDenied

    if call.tool_name == "ExitPlanMode":
        return ToolApproved()
    return ToolDenied(
        "Non-interactive mode: approval-gated tool blocked (no user to "
        "confirm). Re-run with --interactive true to approve interactively."
    )


def _approve_via_yolo(policy_decision, force_ask):
    """Priority 3: YOLO auto-approval; never overrides a policy or hook ASK."""
    # lazy: tests patch zrb.llm.agent_state.get_current_yolo; hoisting bypasses the mock
    from zrb.llm.agent_state import get_current_yolo

    if get_current_yolo() is not True or policy_decision == ASK or force_ask:
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_permission_request_hook(call, hook_manager):
    """Fire PermissionRequest once every auto-resolve path is exhausted.

    The hook may resolve the prompt via `hookSpecificOutput.decision.behavior`.
    """
    if hook_manager is None:
        return None
    perm_results = await hook_manager.execute_hooks(
        HookEvent.PERMISSION_REQUEST,
        {"tool": call.tool_name, "args": getattr(call, "args", None)},
        tool_name=call.tool_name,
        tool_input=_as_tool_input(getattr(call, "args", None)),
        message=f"Approval requested to run {call.tool_name}",
    )
    perm_decision = extract_permission_decision(perm_results)
    if perm_decision == "allow":
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return ToolApproved()
    if perm_decision == "deny":
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        return ToolDenied("Denied by PermissionRequest hook")
    return None


async def _request_via_approval_channel(call, approval_channel):
    """Priority 4: ask over the approval channel; the first response wins."""
    CFG.LOGGER.debug(f"Using approval channel for {call.tool_name}")
    args: dict = {}
    raw_args = getattr(call, "args", None)
    if isinstance(raw_args, dict):
        args = raw_args
    elif isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            pass
    context = ApprovalContext(
        tool_name=call.tool_name,
        tool_args=args,
        tool_call_id=call.tool_call_id,
    )
    CFG.LOGGER.debug("Calling approval_channel.request_approval()...")
    approval_result = await approval_channel.request_approval(context)
    CFG.LOGGER.debug(f"Approval channel returned: approved={approval_result.approved}")
    return approval_result.to_pydantic_result()


async def _confirm_via_cli(call, ui, effective_tool_confirmation):
    """Priority 5: fall back to the interactive CLI prompt."""
    CFG.LOGGER.debug(f"Using CLI fallback for {call.tool_name}")
    if isinstance(effective_tool_confirmation, ToolCallHandler):
        result = await effective_tool_confirmation.handle(ui, call)
        CFG.LOGGER.debug(f"CLI handler returned: {result}")
        return result
    if callable(effective_tool_confirmation):
        res = effective_tool_confirmation(call)
        if inspect.isawaitable(res):
            res = await res
        CFG.LOGGER.debug(f"CLI callable returned: {res}")
        return res
    return None
