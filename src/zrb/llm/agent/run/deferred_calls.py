"""Deferred-tool-call processing for `run_agent`.

When pydantic-ai produces a `DeferredToolRequests`, we route each call
through the approval precedence chain:

0. Always-approve      — tools that ARE the interaction (e.g. AskUserQuestion);
   auto-approve in every path, independent of any policy list
1. Permission policy   — allow→auto-approve, deny→block, ask→defer
   (enforced here in `_resolve_approval`; DENY is additionally blocked at
   execution time by `gates.permission_gate`)
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
from zrb.llm.permission import ASK
from zrb.llm.tool.ask import get_interactive_mode
from zrb.llm.tool_call.always_approve import is_always_auto_approve
from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.override_registry import discard_override, record_override
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


def _record_override_if_edited(call, result: Any) -> None:
    """Register an edited call with `override_registry`, so the model finds
    out (via a note `SafeToolsetWrapper.call_tool` appends to the tool
    result) that its arguments changed before execution.

    A no-op unless `result` is an edited `ToolApproved` — the common case
    (approved as-is, or denied) never touches the registry. `getattr` rather
    than a direct attribute read: some approval paths return a duck-typed
    stand-in (this module's own tests among them) that doesn't define
    `override_args` at all, which must read the same as "no override."
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    if not isinstance(result, ToolApproved):
        return
    override_args = getattr(result, "override_args", None)
    if override_args is None:
        return
    # `None` means unparseable (not a dict, or invalid JSON), not "no edit" —
    # fall back to an empty baseline so the diff still reports every edited
    # key as changed rather than silently dropping the override entirely.
    original_args = parse_tool_args(call) or {}
    record_override(call.tool_call_id, original_args, override_args)


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
        _record_override_if_edited(call, result)

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
    # Every call being dropped here (including edited-and-approved siblings of
    # the denied call) will never reach execution, so any override recorded
    # for it would otherwise leak in `_pending` forever.
    for tool_call_id in current_results.calls:
        discard_override(tool_call_id)
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

    Approval precedence chain:
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

    # Each stage returns a verdict to stop the cascade, or None to fall through
    # to the next. The order below IS the documented precedence chain.
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

    # Fallthrough: no approval mechanism configured. If the policy said ASK (or a
    # hook forced ASK) we must not silently approve — deny instead.
    if policy_decision == ASK or force_ask:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        return ToolDenied(
            "Policy requires approval but no approval channel is configured"
        )
    return None


def _approve_always_auto_approve_tools(call):
    """Priority 0: tools that ARE the user interaction.

    A separate prompt for `AskUserQuestion` would render before the question
    itself, so these approve on every path regardless of per-runner policy.
    """
    if not is_always_auto_approve(call.tool_name):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_tool_policies(call, ui, effective_tool_confirmation, force_ask):
    """Priority 1: pre-confirmation tool policies.

    `effective_tool_confirmation` may be a `ToolCallHandler` directly
    (non-interactive) or a `BaseUI` bound method wrapping one (interactive) —
    unwrap either.
    """
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
    # A hook-requested ASK forces the prompt: ignore an auto-APPROVE here, but
    # still honor an explicit DENY.
    # lazy: heavy third-party
    from pydantic_ai import ToolDenied

    if not force_ask or isinstance(policy_result, ToolDenied):
        return policy_result
    return None


def _apply_permission_policy(call, force_ask):
    """Priority 2: the permission ruleset.

    Returns the raw decision alongside any verdict, because a decision of ASK
    stops YOLO from auto-approving further down the cascade even though it
    resolves nothing here.
    """
    # lazy: tests patch zrb.llm.permission.get_effective_policy and
    # .tool_capability; hoisting would bind these names at this module's
    # load time and bypass the mocks.
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
    """Priority 2b: settle a hard ASK when there is nobody to ask.

    Without a human, a hard ASK can neither be prompted nor overridden by YOLO,
    so it would fall through to the stdin prompt at Priority 5 and block forever
    (the root cause of the `--interactive false` plan-mode hang). Resolve it
    deterministically instead: auto-approve the plan gate (`ExitPlanMode`'s
    approval is a no-op with no user to read the plan, mirroring
    `AskUserQuestion`) and deny any other approval-gated tool rather than
    running it unattended.
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
    """Priority 3: YOLO auto-approval.

    An explicit policy ASK, or a hook-requested ASK, is a hard ask that YOLO
    does not override.
    """
    # lazy: tests patch zrb.llm.agent_state.get_current_yolo;
    # hoisting would bind the name at this module's load time and bypass it.
    from zrb.llm.agent_state import get_current_yolo

    if get_current_yolo() is not True or policy_decision == ASK or force_ask:
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


async def _apply_permission_request_hook(call, hook_manager):
    """Fire PermissionRequest, now that the cascade has decided to ask.

    Every auto-resolve path is exhausted by this point, so the call *will* block
    on a prompt. Firing here means "needs your approval" notifications ring
    exactly when the user is asked, never for an auto-approved call.

    Claude-compatible: the hook may resolve the prompt itself via
    `hookSpecificOutput.decision.behavior`.
    """
    if hook_manager is None:
        return None
    perm_results = await hook_manager.execute_hooks(
        HookEvent.PERMISSION_REQUEST,
        {"tool": call.tool_name, "args": getattr(call, "args", None)},
        tool_name=call.tool_name,
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
