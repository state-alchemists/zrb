"""Deferred-tool-call processing for `run_agent`.

Each call in a `DeferredToolRequests` goes through the approval cascade in
`_resolve_approval`. A permission DENY is also enforced at execution time by
`gates.permission_gate`.
"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, cast

from zrb.config.config import CFG
from zrb.llm.agent.run.hook_result_extractor import (
    PreToolDecision,
    extract_permission_decision,
    extract_pre_tool_decision,
)
from zrb.llm.agent.shell_judge import judge_or_unknown, shell_command_args
from zrb.llm.approval.any_approval_channel import ApprovalContext
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.manager import HookManager
from zrb.llm.permission import ASK
from zrb.llm.shared.ambient_state import get_interactive_mode
from zrb.llm.tool_call.always_approve import (
    is_always_auto_approve,
    is_default_auto_approve,
)
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.judge_note import discard_judge_note, record_judge_note
from zrb.llm.tool_call.override_registry import discard_override, record_override
from zrb.llm.util.tool_args import parse_tool_args

if TYPE_CHECKING:
    from pydantic_ai import (
        DeferredToolRequests,
        DeferredToolResults,
        ToolApproved,
        ToolDenied,
    )
    from pydantic_ai.messages import ToolCallPart

    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.shared.agent_state import AnyToolConfirmation
    from zrb.llm.ui.any_ui import AnyUI


def _as_tool_input(args: object) -> object:
    """Parse JSON-string args into a dict for a hook's ``tool_input``, if possible."""
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


def _record_override_if_edited(call: "ToolCallPart", result: object) -> None:
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
    effective_tool_confirmation: AnyToolConfirmation,
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
        # The judge's line is released however this call ends, including a turn
        # cancelled while the prompt was waiting: the registry is process-global,
        # so a note left behind outlives the approval that never happened.
        try:
            # PreToolUse may deny, allow, or rewrite args. Auto-approved tools never
            # reach here and fire it at execution time instead (no double-fire).
            pre = await _apply_pre_tool_use_hook(call, hook_manager)
            if pre.deny:
                current_results.approvals[call.tool_call_id] = ToolDenied(
                    pre.reason or "Tool execution blocked by PreToolUse hook"
                )
                _discard_denied_call(current_results, call.tool_call_id)
                continue

            result: "ToolApproved | ToolDenied | None" = (
                ToolApproved()
                if pre.allow
                else await _resolve_approval(
                    call,
                    ui,
                    effective_tool_confirmation,
                    approval_channel,
                    hook_manager,
                    force_ask=pre.force_prompt,
                )
            )
            # A path that resolved nothing stores None: pydantic-ai reads that as
            # "no verdict", which is what the approval cascade means by falling
            # through without one.
            current_results.approvals[call.tool_call_id] = cast(
                "ToolApproved | ToolDenied", result
            )
            _record_override_if_edited(call, result)

            if isinstance(result, ToolDenied):
                _discard_denied_call(current_results, call.tool_call_id)
                CFG.LOGGER.debug("Tool denied, removed from calls")

            # PostToolUse fires at execution, not approval.
        finally:
            discard_judge_note(call.tool_call_id)

    return current_results


async def _apply_pre_tool_use_hook(
    call: "ToolCallPart", hook_manager: HookManager
) -> PreToolDecision:
    """Fire PreToolUse for *call* and apply the argument rewrite it asks for."""
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
    return pre


def _discard_denied_call(
    current_results: "DeferredToolResults", tool_call_id: str
) -> None:
    """Drop the call slot a denied call would have executed from."""
    current_results.calls.pop(tool_call_id, None)


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
    call: "ToolCallPart",
    ui: AnyUI,
    effective_tool_confirmation: AnyToolConfirmation,
    approval_channel: "AnyApprovalChannel | None",
    hook_manager: "HookManager | None" = None,
    force_ask: bool = False,
) -> "ToolApproved | ToolDenied | None":
    """Run the approval cascade for a single deferred call.

    Precedence:
      0. Always-approve (intrinsically interactive tools, e.g. AskUserQuestion)
      1. Tool policy
      2. Permission policy (ALLOW→approve, DENY→deny, ASK→force ask)
      2b. A hard ASK settled when non-interactive
      2c. Default-approve (the harness's bounded tools; a rule still wins)
      3. YOLO (only with no policy ASK)
      3b. The shell judge (may skip the prompt for a `safe` command, when the
          auto-approve knob is on; otherwise only annotates the prompt)
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

    verdict = _approve_by_default(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = _approve_via_yolo(policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = await _apply_permission_request_hook(call, hook_manager)
    if verdict is not None:
        return verdict

    verdict = await _apply_shell_judge(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    if approval_channel is not None:
        verdict = await _request_via_approval_channel(call, approval_channel)
        await _announce_permission_resolved(call, verdict, hook_manager)
        return verdict

    verdict = await _confirm_via_cli(call, ui, effective_tool_confirmation)
    # Before the fall-through: with no verdict the policy decides next, and the wait is over
    # either way. Nothing else reports this moment — see _announce_permission_resolved.
    await _announce_permission_resolved(call, verdict, hook_manager)
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


def _approve_always_auto_approve_tools(call: "ToolCallPart") -> "ToolApproved | None":
    """Priority 0: tools that are the user interaction (e.g. `AskUserQuestion`)."""
    if not is_always_auto_approve(call.tool_name):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_tool_policies(
    call: "ToolCallPart",
    ui,
    effective_tool_confirmation: AnyToolConfirmation,
    force_ask: bool,
) -> "ToolApproved | ToolDenied | None":
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


def _apply_permission_policy(
    call: "ToolCallPart", force_ask: bool
) -> "tuple[str | None, ToolApproved | ToolDenied | None]":
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
    decision = policy.decide(
        call.tool_name, tool_capability(call), parse_tool_args(call) or {}
    )
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


def _resolve_non_interactive_ask(
    call: "ToolCallPart", policy_decision: str | None, force_ask: bool
) -> "ToolApproved | ToolDenied | None":
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


def _approve_by_default(
    call: "ToolCallPart", policy_decision: str | None, force_ask: bool
) -> "ToolApproved | None":
    """Priority 2c: the harness's bounded tools, approved unless a rule says otherwise.

    Below the permission policy on purpose: a user's `ask` is still a hard ask
    and a PreToolUse `ask` still forces the prompt, so this removes a prompt
    nobody wanted rather than a decision somebody made. Above YOLO because the
    prompt it removes is the one a careful user answers by hand every turn, and
    YOLO is the mode where nobody is watching anyway.
    """
    if force_ask or policy_decision == ASK:
        return None
    args = parse_tool_args(call)
    if not is_default_auto_approve(
        call.tool_name, args if isinstance(args, dict) else None
    ):
        return None
    # The same invariant the tool policies keep: a request to leave the sandbox
    # is a request for a human, however ordinary the tool is.
    if isinstance(args, dict) and args.get("dangerously_skip_sandbox"):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


def _approve_via_yolo(
    policy_decision: str | None, force_ask: bool
) -> "ToolApproved | None":
    """Priority 3: YOLO auto-approval; never overrides a policy or hook ASK."""
    # lazy: tests patch zrb.llm.shared.agent_state.get_current_yolo; hoisting bypasses the mock
    from zrb.llm.shared.agent_state import get_current_yolo

    if get_current_yolo() is not True or policy_decision == ASK or force_ask:
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_shell_judge(
    call: "ToolCallPart", policy_decision: str | None, force_ask: bool
) -> "ToolApproved | None":
    """Priority 3b: one model's opinion on a shell command, and nothing more.

    The last thing consulted before a person is asked. It can approve a command
    the judge calls `safe` — and only when `LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED`
    is on, no rule of the user's said ask, and the call is not asking to leave
    the sandbox. Otherwise it records one line for the prompt, so whoever
    answers sees what the judge saw.

    A judge that failed records `unknown`, which is not safe: the prompt is
    still asked, now saying the command went unjudged.
    """
    if not CFG.LLM_SHELL_JUDGE_ENABLED:
        return None
    args = shell_command_args(call)
    if args is None:
        return None
    # The invariant every other approval path in this cascade keeps: a request
    # to leave the sandbox is a request for a human, however ordinary the
    # command is. `ls /etc` with `dangerously_skip_sandbox` is not "safe".
    sandbox_off = bool(args.get("dangerously_skip_sandbox"))
    verdict = await judge_or_unknown(
        str(args.get("command", "")),
        cwd=str(args.get("cwd") or ""),
        sandbox_off=sandbox_off,
    )
    if (
        verdict.is_safe
        and not sandbox_off
        and CFG.LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED
        and not force_ask
        and policy_decision != ASK
    ):
        CFG.LOGGER.debug(f"Shell judge approved a call: {verdict.reason}")
        discard_judge_note(call.tool_call_id)
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return ToolApproved()
    record_judge_note(call.tool_call_id, verdict.level, verdict.reason)
    return None


async def _apply_permission_request_hook(
    call: "ToolCallPart", hook_manager: "HookManager | None"
) -> "ToolApproved | ToolDenied | None":
    """Fire PermissionRequest once every auto-resolve path is exhausted.

    The hook may resolve the prompt via `hookSpecificOutput.decision.behavior`.
    """
    if hook_manager is None:
        return None
    perm_results = await hook_manager.execute_hooks(
        HookEvent.PERMISSION_REQUEST,
        {"tool": call.tool_name, "args": call.args},
        tool_name=call.tool_name,
        tool_input=_as_tool_input(call.args),
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


async def _announce_permission_resolved(
    call: "ToolCallPart",
    verdict: "ToolApproved | ToolDenied | None",
    hook_manager: "HookManager | None",
) -> None:
    """Tell the hooks the wait is over, once the answer is known.

    Only the paths that reached an interactive approval call this, so a tool the policy
    approved outright fires nothing. ``approved`` is True, False, or None when the channel
    gave no verdict and the policy is about to answer — "the user was asked and did not
    say", which is not the same as "denied". Observe-only: whatever a hook returns here is
    ignored, so a listener cannot change what was decided.
    """
    if hook_manager is None:
        return
    # lazy: heavy third-party
    from pydantic_ai import ToolDenied

    await hook_manager.execute_hooks(
        HookEvent.PERMISSION_RESOLVED,
        {
            "tool": call.tool_name,
            "approved": (
                None if verdict is None else not isinstance(verdict, ToolDenied)
            ),
        },
        tool_name=call.tool_name,
    )


async def _request_via_approval_channel(
    call: "ToolCallPart", approval_channel: "AnyApprovalChannel"
) -> "ToolApproved | ToolDenied":
    """Priority 4: ask over the approval channel; the first response wins."""
    CFG.LOGGER.debug(f"Using approval channel for {call.tool_name}")
    context = ApprovalContext(
        tool_name=call.tool_name,
        tool_args=parse_tool_args(call) or {},
        tool_call_id=call.tool_call_id,
    )
    CFG.LOGGER.debug("Calling approval_channel.request_approval()...")
    approval_result = await approval_channel.request_approval(context)
    CFG.LOGGER.debug(f"Approval channel returned: approved={approval_result.approved}")
    return approval_result.to_pydantic_result()


async def _confirm_via_cli(
    call: "ToolCallPart", ui: AnyUI, effective_tool_confirmation: AnyToolConfirmation
) -> "ToolApproved | ToolDenied | None":
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
