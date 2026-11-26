"""Deferred-tool-call processing for `run_agent`.

Each call in a `DeferredToolRequests` goes through the approval cascade in
`_resolve_approval`. A permission DENY is also enforced at execution time by
`gates.permission_gate`.
"""

from __future__ import annotations

import inspect
import json
import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.capabilities.approval.any_approval_channel import ApprovalContext
from zrb.llm.capabilities.approval.judge_state import (
    is_shell_judge_auto_approve_enabled,
    is_shell_judge_enabled,
)
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.capabilities.hook.manager import HookManager
from zrb.llm.capabilities.permission import ASK, DENY, Capability
from zrb.llm.capabilities.permission.policy import PATH_ARG_KEYS
from zrb.llm.capabilities.tool_call.always_approve import (
    is_always_auto_approve,
    is_default_auto_approve,
)
from zrb.llm.capabilities.tool_call.handler import ToolCallHandler
from zrb.llm.capabilities.tool_call.judge_note import (
    discard_judge_note,
    record_judge_note,
)
from zrb.llm.capabilities.tool_call.override_registry import (
    discard_override,
    record_override,
)
from zrb.llm.capabilities.tool_call.shell_call import (
    is_sandbox_off,
    shell_command,
    shell_command_args,
)
from zrb.llm.contracts.shared.ambient_state import get_interactive_mode
from zrb.llm.contracts.util.tool_args import parse_tool_args
from zrb.llm.engine.agent.run.hook_result_extractor import (
    PreToolDecision,
    extract_permission_decision,
    extract_pre_tool_decision,
)
from zrb.llm.engine.agent.shell_judge import judge_or_unknown

if TYPE_CHECKING:
    from pydantic_ai import (
        DeferredToolRequests,
        DeferredToolResults,
        ToolApproved,
        ToolDenied,
    )
    from pydantic_ai.messages import ToolCallPart

    from zrb.llm.capabilities.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.contracts.shared.agent_state import AnyToolConfirmation
    from zrb.llm.presentation.ui.any_ui import AnyUI


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

            result: "ToolApproved | ToolDenied" = (
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
            current_results.approvals[call.tool_call_id] = result
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
) -> "ToolApproved | ToolDenied":
    """Run the approval cascade for a single deferred call.

    Precedence:
      0. Always-approve (intrinsically interactive tools, e.g. AskUserQuestion)
      1. Tool policy
      2. Permission policy (ALLOW→approve, DENY→deny, ASK→force ask)
      2a. A write to the MCP loader's config — a hard ASK, the only kind that
          outranks YOLO (ADR-0062)
      2b. A hard ASK settled when non-interactive
      2c. Default-approve (the harness's bounded tools; a rule still wins)
      3. YOLO (only with no policy ASK, and never for a sandbox escape)
      3b. The shell judge — a `safe` command may skip the prompt when the
          auto-approve knob is on; otherwise it only annotates one
      4. The `PermissionRequest` hook — fires *now that the call will prompt*,
          which is why 3b settles first: a prompt the judge removed must not be
          announced
      5. Approval channel
      6. CLI prompt

    ``force_ask`` (PreToolUse ``permissionDecision: "ask"``) skips the
    auto-approvals at 1-3 but still honors DENY and priority 0. Each stage
    returns a verdict, or None to fall through; the call left unanswered by
    every stage is denied, so this always returns a real verdict.
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
    if _is_mcp_config_write(call) and policy_decision != DENY:
        policy_decision, verdict = ASK, None
    if verdict is not None:
        return verdict

    verdict = _resolve_non_interactive_ask(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = _approve_by_default(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = _approve_via_yolo(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = await _apply_shell_judge(call, policy_decision, force_ask)
    if verdict is not None:
        return verdict

    verdict = await _apply_permission_request_hook(call, hook_manager)
    if verdict is not None:
        return verdict

    if approval_channel is not None:
        verdict = await _request_via_approval_channel(call, approval_channel)
        await _announce_permission_resolved(call, verdict, hook_manager)
        return verdict

    verdict = await _confirm_via_cli(call, ui, effective_tool_confirmation)
    # No approval mechanism answered the call, so it cannot run: approving it
    # silently is the one outcome the cascade exists to prevent. The verdict has
    # to be real — `DeferredToolResults` accepts only `bool`, `ToolApproved`, or
    # `ToolDenied`, and a `None` here kills the resumed turn and loses the call.
    # It is decided before the announcement, so the hook hears the verdict that
    # is stored instead of the `None` the fall-through replaces.
    if verdict is None:
        # lazy: heavy third-party
        from pydantic_ai import ToolDenied

        verdict = ToolDenied(
            "Policy requires approval but no approval mechanism is configured"
        )
    # Nothing else reports this moment — see _announce_permission_resolved.
    await _announce_permission_resolved(call, verdict, hook_manager)
    return verdict


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
    # lazy: tests patch zrb.llm.capabilities.permission.get_effective_policy; hoisting bypasses the mock
    from zrb.llm.capabilities.permission import (
        ALLOW,
        DENY,
        get_effective_policy,
    )
    from zrb.llm.capabilities.permission.observability import record_policy_decision
    from zrb.llm.engine.agent.run.tool_capabilities import get_tool_capability

    policy = get_effective_policy()
    if policy is None:
        record_policy_decision(
            layer="permission", decision="none", tool_name=call.tool_name
        )
        return None, None
    # By name, never from the call part: a deferred `ToolCallPart` carries no
    # capability tag, so asking the part answers UNKNOWN and a capability-keyed
    # rule (`edit:ask`) silently falls through to a later `*:allow`.
    decision = policy.decide(
        call.tool_name, get_tool_capability(call.tool_name), parse_tool_args(call) or {}
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
    if isinstance(args, dict) and is_sandbox_off(args):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


def _approve_via_yolo(
    call: "ToolCallPart", policy_decision: str | None, force_ask: bool
) -> "ToolApproved | None":
    """Priority 3: YOLO auto-approval; never overrides a policy or hook ASK.

    Nor a request to leave the sandbox: the escape hatch is never auto-approved
    (ADR-0065), and YOLO is the mode where nobody is watching anyway. The
    arguments are needed here for that one question — a `Shell` call carrying
    `dangerously_skip_sandbox` is a human's decision however ordinary the
    command looks.
    """
    # lazy: tests patch zrb.llm.contracts.shared.agent_state.get_current_yolo; hoisting bypasses the mock
    from zrb.llm.contracts.shared.agent_state import get_current_yolo

    if get_current_yolo() is not True or policy_decision == ASK or force_ask:
        return None
    args = parse_tool_args(call)
    if isinstance(args, dict) and is_sandbox_off(args):
        return None
    # lazy: heavy third-party
    from pydantic_ai import ToolApproved

    return ToolApproved()


def _is_mcp_config_write(call: "ToolCallPart") -> bool:
    """Priority 2a: whether *call* would write the file the MCP loader reads.

    `capabilities/tool/mcp.py` starts every server the config file names, so a
    write to one decides what a later session runs with — a human's decision,
    not the model's. It is a hard ASK rather than a DENY because the file is a
    normal part of a user's workspace: they may well mean to edit it, and only
    they can say.

    Judge a write only, and only the capabilities `sandbox_gate` write-checks: a
    tool that mutates files, and an untagged one that might. A shell command's
    redirect stays out of reach here, as it does for that gate.
    """
    # lazy: tests patch zrb.llm.engine.agent.run.tool_capabilities.get_tool_capability; hoisting bypasses the mock
    from zrb.llm.engine.agent.run.tool_capabilities import get_tool_capability

    if get_tool_capability(call.tool_name).value not in (
        Capability.EDIT.value,
        Capability.UNKNOWN.value,
    ):
        return False
    args = parse_tool_args(call)
    return isinstance(args, dict) and _has_mcp_config_arg(args)


def _has_mcp_config_arg(args: dict[str, object]) -> bool:
    """Whether a path-shaped argument of *args* names a config the loader reads."""
    config_paths = _mcp_config_paths()
    for key in PATH_ARG_KEYS:
        value = args.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if os.path.realpath(os.path.expanduser(value)) in config_paths:
            return True
    return False


def _mcp_config_paths() -> frozenset[str]:
    """Every absolute path `load_mcp_config` reads its config from.

    The loader takes `CFG.MCP_CONFIG_FILE` from the working directory and, when
    that sits under the home directory, from each directory between it and home
    (`capabilities/tool/mcp.py::_get_config_files`). The walk is mirrored rather
    than called: that module imports the MCP client, and the approval cascade
    must not pay for it to answer a path question. A config that does not exist
    yet counts — creating one is what this guard is for.
    """
    cwd = os.path.realpath(os.getcwd())
    home = os.path.realpath(os.path.expanduser("~"))
    config_file_name = CFG.MCP_CONFIG_FILE
    if not config_file_name:
        # A blank name reads nothing: `_get_config_files` would test the
        # directory itself and find no file.
        return frozenset()
    directories = {cwd}
    if cwd == home or cwd.startswith(home + os.sep):
        # Every directory between the working directory and home; `home` is an
        # ancestor, so the walk always ends there.
        current = cwd
        while current != home:
            current = os.path.dirname(current)
            directories.add(current)
    return frozenset(
        os.path.realpath(os.path.join(directory, config_file_name))
        for directory in directories
    )


async def _apply_shell_judge(
    call: "ToolCallPart", policy_decision: str | None, force_ask: bool
) -> "ToolApproved | None":
    """Priority 3b: one model's opinion on a shell command, and nothing more.

    It sits above the `PermissionRequest` hook rather than below it, because
    that hook's own contract is "fires now that the call will prompt": a hook
    that announces a prompt — the speech feature reads it aloud — must not be
    told about one a `safe` verdict is about to remove.

    It can approve a command the judge calls `safe`, and only when
    `LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED` is on, no rule of the user's said
    ask, no hook forced the ask, and the call is not asking to leave the
    sandbox. Otherwise it records one line for the prompt, so whoever answers
    sees what the judge saw.

    A judge that failed records `unknown`, which is not safe: the prompt is
    still asked, now saying the command went unjudged.
    """
    if not is_shell_judge_enabled():
        return None
    args = shell_command_args(call)
    if args is None:
        return None
    # The invariant every other approval path in this cascade keeps: a request
    # to leave the sandbox is a request for a human, however ordinary the
    # command is. `ls /etc` with `dangerously_skip_sandbox` is not "safe".
    sandbox_off = is_sandbox_off(args)
    verdict = await judge_or_unknown(
        shell_command(args),
        cwd=str(args.get("cwd") or ""),
        sandbox_off=sandbox_off,
    )
    if (
        verdict.is_safe
        and not sandbox_off
        and is_shell_judge_auto_approve_enabled()
        and not force_ask
        and policy_decision != ASK
    ):
        CFG.LOGGER.debug(f"Shell judge approved a call: {verdict.reason}")
        discard_judge_note(call.tool_call_id)
        # lazy: heavy third-party
        from pydantic_ai import ToolApproved

        return ToolApproved()
    record_judge_note(call.tool_call_id, verdict.level, verdict.reason, verdict.facts)
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
    approved outright fires nothing. ``approved`` is True for an approval and False for a
    denial — the CLI fall-through denies the call nobody answered *before* this call, so a
    listener hears the verdict that is stored. None remains for an approval channel that
    returns no verdict: "the user was asked and did not say", which is not the same as
    "denied". Observe-only: whatever a hook returns here is ignored, so a listener cannot
    change what was decided.
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
