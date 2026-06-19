"""Deferred-tool-call processing for `run_agent`.

When pydantic-ai produces a `DeferredToolRequests`, we route each call
through the approval precedence chain (ADR-0055, ADR-0062):

0. Always-approve      — tools that ARE the interaction (e.g. AskUserQuestion);
   auto-approve in every path, independent of any policy list
1. Permission policy   — allow→auto-approve, deny→block, ask→defer
   (checked at check_yolo time; deny pre-checked again before prompting)
2. Tool policy         — allow→auto-approve, deny→block, no-opinion→defer
3. Yolo                — True→auto-approve, False→continue
4. Approval channel    — remote / multi-channel; first response wins
5. CLI fallback        — prompt the user

After the loop we rebuild `current_results` with `calls={}` if any tool was
denied, so pydantic-ai does not execute denied calls. Returns `None` if
there are no requests.
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
from zrb.llm.approval.approval_channel import ApprovalContext
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.tool_call.always_approve import is_always_auto_approve
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import DeferredToolRequests, DeferredToolResults

    from zrb.llm.approval.approval_channel import ApprovalChannel


def _as_tool_input(args: Any) -> Any:
    """Coerce a deferred call's args to a Claude-shaped ``tool_input`` dict.

    pydantic-ai may hand us args as a dict or as a JSON string. A hook reads
    ``tool_input`` as an object, so parse a JSON string when we can; otherwise
    pass the value through unchanged.
    """
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args


async def process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: Any,
    ui: UIProtocol,
    hook_manager: HookManager,
    approval_channel: "ApprovalChannel | None" = None,
) -> "DeferredToolResults | None":
    """Run approval flow for each deferred call. Returns None if there are no requests."""
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

    for call in all_requests:
        # Hook: PreToolUse (pre-approval). Claude-compatible: a hook may deny the
        # call, auto-allow it, or rewrite its arguments (`updatedInput`). This is
        # the pre-approval fire for tools that require approval; auto-approved
        # tools (which never reach here) fire PreToolUse at execution time in
        # SafeToolsetWrapper.call_tool, guarded by ctx.tool_call_approved so the
        # two paths never double-fire.
        hook_results = await hook_manager.execute_hooks(
            HookEvent.PRE_TOOL_USE,
            {
                "tool": call.tool_name,
                "args": call.args,
                "call_id": call.tool_call_id,
            },
            # Claude-standard context fields so tool-name matchers and stdin
            # reads work on the deferred-approval path (mirrors the execution-time
            # fire in agent.common._fire_pre_tool_use). call.args may arrive as a
            # JSON string; hand the hook a dict when possible.
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
            # permissionDecision="allow" skips the approval prompt entirely.
            result: Any = ToolApproved()
        else:
            # permissionDecision="ask" (pre.force_prompt) forces the interactive
            # prompt, overriding lower-priority auto-approves (tool/permission
            # ALLOW, YOLO) while still honoring an explicit DENY.
            result = await _resolve_approval(
                call,
                ui,
                effective_tool_confirmation,
                approval_channel,
                hook_manager,
                force_ask=pre.force_prompt,
            )
        current_results.approvals[call.tool_call_id] = result

        if isinstance(result, ToolDenied):
            # Drop the denied call so pydantic-ai doesn't execute it.
            if (
                hasattr(current_results, "calls")
                and call.tool_call_id in current_results.calls
            ):
                del current_results.calls[call.tool_call_id]
            CFG.LOGGER.debug("Tool denied, removed from calls")

        # PostToolUse / PostToolUseFailure are NOT fired here: approval is not
        # execution. They fire from SafeToolsetWrapper.call_tool once the tool
        # actually runs (success) or raises (failure), matching Claude Code.

    return current_results


def rebuild_for_denials(
    current_results: "DeferredToolResults",
) -> "DeferredToolResults":
    """Return a new `DeferredToolResults` with `calls={}` if any approval was denied.

    pydantic-ai expects calls/approvals to be consistent: if a tool is denied
    we must clear `calls` so it is not invoked. Returns the same object if
    there are no denials.
    """
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolResults, ToolDenied

    has_denials = any(
        isinstance(v, ToolDenied) for v in current_results.approvals.values()
    )
    if not has_denials:
        return current_results

    CFG.LOGGER.debug("Tool was denied, clearing calls in deferred results")
    return DeferredToolResults(
        calls={},
        approvals=current_results.approvals,
        metadata=current_results.metadata,
    )


async def _resolve_approval(
    call,
    ui: UIProtocol,
    effective_tool_confirmation: Any,
    approval_channel: "ApprovalChannel | None",
    hook_manager: "HookManager | None" = None,
    force_ask: bool = False,
):
    """Run the approval cascade for a single deferred call.

    Approval precedence chain (ADR-0055, ADR-0062):
      0. Always-approve (intrinsically interactive tools, e.g. AskUserQuestion)
      1. Tool policy (Pre-confirmation)
      2. Permission policy (Strict mode: ALLOW→Approve, DENY→Deny, ASK→Force Ask)
      3. YOLO (Only if no strict policy opinion AND YOLO is explicitly True)
      4. Approval channel (Multi-channel)
      5. CLI fallback (User prompt)

    ``force_ask`` (a PreToolUse hook returning ``permissionDecision: "ask"``) makes
    the call behave like a hard policy ASK: auto-APPROVE outcomes at priorities 1-3
    are skipped so the interactive prompt always shows, while an explicit DENY and
    the always-approve tools (priority 0) are still honored.
    """

    # Priority 0: Intrinsically auto-approved tools. These ARE the user
    # interaction (e.g. AskUserQuestion), so a separate approval prompt is
    # redundant and would render before the question itself. Approve in every
    # path, independent of any per-runner policy list. See ADR-0062.
    if is_always_auto_approve(call.tool_name):
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return ToolApproved()

    # Priority 1: Tool policies (Pre-confirmation). Auto-approved tools skip
    # the PermissionRequest hook entirely. The effective_tool_confirmation may
    # be a ToolCallHandler directly (non-interactive) or wrapped by a BaseUI
    # bound method (interactive) — unwrap either.
    _tch = None
    if isinstance(effective_tool_confirmation, ToolCallHandler):
        _tch = effective_tool_confirmation
    elif (bound := getattr(effective_tool_confirmation, "__self__", None)) is not None:
        _tch = getattr(bound, "tool_call_handler", None)
    if isinstance(_tch, ToolCallHandler):
        policy_result = await _tch.check_policies(ui, call)
        if policy_result is not None:
            # A hook-requested ASK forces the prompt: ignore an auto-APPROVE here,
            # but still honor an explicit DENY.
            # lazy: heavy third-party
            from pydantic_ai import ToolDenied

            if not force_ask or isinstance(policy_result, ToolDenied):
                return policy_result

    # lazy: permission is a leaf module.
    from zrb.llm.permission import (
        ALLOW,
        ASK,
        DENY,
        get_effective_policy,
        tool_capability,
    )

    # Priority 2: Permission policy (Ruleset)
    policy = get_effective_policy()
    policy_decision: str | None = None
    if policy is not None:
        cap = tool_capability(call)
        raw_args = getattr(call, "args", None) or {}
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError:
                raw_args = {}
        policy_decision = policy.decide(call.tool_name, cap, raw_args)

        if policy_decision == ALLOW and not force_ask:
            # lazy: heavy third-party
            from pydantic_ai import ToolApproved

            return ToolApproved()
        if policy_decision == DENY:
            # lazy: heavy third-party
            from pydantic_ai import ToolDenied

            return ToolDenied("Blocked by permission policy")

        # if policy_decision == ASK, we continue but skip Priority 3 (YOLO).

    # Priority 2b: Non-interactive hard-ASK resolution. With no human to
    # confirm, a hard ASK can neither be prompted nor overridden by YOLO, so it
    # would otherwise fall through to the stdin prompt at Priority 5 and block
    # forever (the root cause of the --interactive false plan-mode hang).
    # Resolve it deterministically instead: auto-approve the plan gate
    # (ExitPlanMode's approval is a no-op without a user to read the plan —
    # mirrors AskUserQuestion / ADR-0062) and deny any other approval-gated
    # tool rather than running it unattended. See ADR-0067.
    # lazy: circular — run-loop approval path ↔ zrb.llm.tool.ask
    from zrb.llm.tool.ask import get_interactive_mode

    if (policy_decision == ASK or force_ask) and not get_interactive_mode():
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved, ToolDenied

        if call.tool_name == "ExitPlanMode":
            return ToolApproved()
        return ToolDenied(
            "Non-interactive mode: approval-gated tool blocked (no user to "
            "confirm). Re-run with --interactive true to approve interactively."
        )

    # Priority 3: YOLO (Auto-approve)
    # lazy: runtime_state is a thin re-export of runner ContextVars.
    from zrb.llm.agent.run.runtime_state import get_current_yolo

    yolo_val = get_current_yolo()
    # Explicit policy ASK (or a hook-requested ASK) is a 'hard ask' that bypasses YOLO.
    if yolo_val is True and policy_decision != ASK and not force_ask:
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return ToolApproved()

    # We've exhausted every auto-resolve path (always-approve, tool/permission
    # policy, YOLO): the call WILL block on an interactive prompt below. Fire
    # PermissionRequest so "needs your approval" notifications/sounds (e.g.
    # peon-ping) ring exactly when the user is asked — not for auto-approved
    # calls. Fired here, after the cascade decides to ask, so it never
    # false-positives on allowed tools.
    if hook_manager is not None:
        perm_results = await hook_manager.execute_hooks(
            HookEvent.PERMISSION_REQUEST,
            {"tool": call.tool_name, "args": getattr(call, "args", None)},
            tool_name=call.tool_name,
            message=f"Approval requested to run {call.tool_name}",
        )
        # Claude-compatible: a PermissionRequest hook may auto-resolve the prompt
        # via hookSpecificOutput.decision.behavior ("allow"/"deny").
        perm_decision = extract_permission_decision(perm_results)
        if perm_decision == "allow":
            # lazy: heavy third-party
            from pydantic_ai import ToolApproved

            return ToolApproved()
        if perm_decision == "deny":
            # lazy: heavy third-party
            from pydantic_ai import ToolDenied

            return ToolDenied("Denied by PermissionRequest hook")

    # Priority 4: Approval channel (multi-channel, first response wins)
    if approval_channel is not None:
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
        CFG.LOGGER.debug(
            f"Approval channel returned: approved={approval_result.approved}"
        )
        return approval_result.to_pydantic_result()

    # Priority 5: CLI fallback via tool confirmation
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
    # Fallthrough: no approval mechanism configured.  If the policy said ASK (or a
    # hook forced ASK) we must not silently approve — deny instead.
    if policy_decision == ASK or force_ask:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        return ToolDenied(
            "Policy requires approval but no approval channel is configured"
        )
    return None
