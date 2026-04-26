"""Deferred-tool-call processing for `run_agent`.

When pydantic-ai produces a `DeferredToolRequests`, we route each call
through three approval strategies in priority order:

1. Tool policy via `ToolCallHandler.check_policies` (auto approve/deny)
2. Approval channel (remote / multi-channel; first response wins)
3. CLI fallback via the tool confirmation handler

After the loop we rebuild `current_results` with `calls={}` if any tool was
denied, so pydantic-ai does not execute denied calls. Returns `None` if
there are no requests.
"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import DeferredToolRequests, DeferredToolResults

    from zrb.llm.approval.approval_channel import ApprovalChannel


async def process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: Any,
    ui: UIProtocol,
    hook_manager: HookManager,
    approval_channel: "ApprovalChannel | None" = None,
) -> "DeferredToolResults | None":
    """Run approval flow for each deferred call. Returns None if there are no requests."""
    from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied

    from zrb.llm.approval.approval_channel import ApprovalContext

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

    for call in all_requests:
        # Hook: PreToolUse — hooks may modify args or cancel the call entirely.
        hook_results = await hook_manager.execute_hooks(
            HookEvent.PRE_TOOL_USE,
            {
                "tool": call.tool_name,
                "args": call.args,
                "call_id": call.tool_call_id,
            },
        )
        cancelled_by_hook = False
        for hr in hook_results:
            if hr.modifications.get("tool_args") and isinstance(call.args, dict):
                call.args.update(hr.modifications["tool_args"])
            if hr.modifications.get("cancel_tool"):
                current_results.approvals[call.tool_call_id] = ToolDenied(
                    "Tool execution cancelled by hook"
                )
                cancelled_by_hook = True
                break
        if cancelled_by_hook:
            continue

        result = await _resolve_approval(
            call,
            ui,
            effective_tool_confirmation,
            approval_channel,
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

        # Hook: PostToolUse / PostToolUseFailure
        if isinstance(result, ToolApproved):
            await hook_manager.execute_hooks(
                HookEvent.POST_TOOL_USE,
                {"tool": call.tool_name, "args": call.args, "result": result},
            )
        elif isinstance(result, ToolDenied):
            await hook_manager.execute_hooks(
                HookEvent.POST_TOOL_USE_FAILURE,
                {
                    "tool": call.tool_name,
                    "args": call.args,
                    "error": result.message,
                },
            )

    return current_results


def rebuild_for_denials(
    current_results: "DeferredToolResults",
) -> "DeferredToolResults":
    """Return a new `DeferredToolResults` with `calls={}` if any approval was denied.

    pydantic-ai expects calls/approvals to be consistent: if a tool is denied
    we must clear `calls` so it is not invoked. Returns the same object if
    there are no denials.
    """
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
):
    """Run the three-tier approval cascade for a single deferred call."""
    from zrb.llm.approval.approval_channel import ApprovalContext

    # Priority 1: Tool policy (automatic approval based on rules)
    if isinstance(effective_tool_confirmation, ToolCallHandler):
        policy_result = await effective_tool_confirmation.check_policies(ui, call)
        if policy_result is not None:
            return policy_result

    # Priority 2: Approval channel (multi-channel, first response wins)
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

    # Priority 3: CLI fallback via tool confirmation
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
