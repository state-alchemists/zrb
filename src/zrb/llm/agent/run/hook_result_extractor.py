from __future__ import annotations

from dataclasses import dataclass

from zrb.llm.hook.executor import HookExecutionResult


def extract_system_message(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first systemMessage from hook results, if any.

    Claude Code hooks can return systemMessage to inject context into the
    conversation. Returns the first one found, or None if no hook set one.
    """
    for result in hook_results:
        if result.system_message:
            return result.system_message
    return None


def extract_replace_response(hook_results: list[HookExecutionResult]) -> bool:
    """Extract the replaceResponse flag from hook results.

    True if any hook returns replaceResponse=True — the extended session's
    response should then replace the original one. False (the default) keeps
    the original response.
    """
    for result in hook_results:
        if result.replace_response:
            return True
    return False


def _hook_specific(result: HookExecutionResult) -> dict:
    """Return the result's hookSpecificOutput dict (Claude nests fields here)."""
    return result.hook_specific_output or {}


def extract_additional_context(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first additionalContext from hook results, if any.

    Claude Code hooks can return additionalContext to prepend context to the
    conversation, either at the top level or (the canonical Claude shape) nested
    inside ``hookSpecificOutput``. Both are checked. Returns the first one
    found, or None if no hook set one.
    """
    for result in hook_results:
        context = result.additional_context or _hook_specific(result).get(
            "additionalContext"
        )
        if context:
            return context
    return None


@dataclass
class BlockDecision:
    """A hook's blocking decision for turn-level events (UserPromptSubmit, Stop)."""

    blocked: bool = False
    reason: str | None = None
    additional_context: str | None = None


def extract_block_decision(hook_results: list[HookExecutionResult]) -> BlockDecision:
    """Return the first block decision and preserve non-blocking context."""
    additional_context: str | None = None
    for result in hook_results:
        hso = _hook_specific(result)
        if result.blocked or result.decision == "block":
            reason = (
                result.reason
                or hso.get("reason")
                or result.message
                or "Blocked by hook"
            )
            return BlockDecision(
                blocked=True,
                reason=reason,
                additional_context=result.additional_context
                or hso.get("additionalContext"),
            )
        if additional_context is None:
            additional_context = result.additional_context or hso.get(
                "additionalContext"
            )
    return BlockDecision(blocked=False, additional_context=additional_context)


@dataclass
class ContinueDecision:
    """A hook's request to halt all processing via ``continue: false``."""

    stop: bool = False
    reason: str | None = None


def extract_continue_decision(
    hook_results: list[HookExecutionResult],
) -> ContinueDecision:
    """Return the first unconditional halt requested by ``continue: false``."""
    for result in hook_results:
        if not result.continue_execution:
            reason = (
                (result.data or {}).get("stopReason")
                or result.reason
                or "Stopped by hook (continue=false)"
            )
            return ContinueDecision(stop=True, reason=reason)
    return ContinueDecision()


def extract_permission_decision(
    hook_results: list[HookExecutionResult],
) -> str | None:
    """Return the first nested or flat ``allow``/``deny`` decision."""
    for result in hook_results:
        hso = _hook_specific(result)
        decision = hso.get("decision")
        if isinstance(decision, dict) and decision.get("behavior") in (
            "allow",
            "deny",
        ):
            return decision["behavior"]
        permission = hso.get("permissionDecision") or result.permission_decision
        if permission in ("allow", "deny"):
            return permission
    return None


@dataclass
class PreToolDecision:
    """A PreToolUse hook's decision over a single tool call."""

    deny: bool = False
    allow: bool = False
    force_prompt: bool = False
    reason: str | None = None
    updated_input: dict | None = None
    additional_context: str | None = None


def extract_pre_tool_decision(
    hook_results: list[HookExecutionResult],
) -> PreToolDecision:
    """Interpret PreToolUse decisions, including input rewrites and context."""
    updated_input: dict | None = None
    additional_context: str | None = None
    for result in hook_results:
        hso = _hook_specific(result)
        permission = hso.get("permissionDecision") or result.permission_decision
        reason = _pre_tool_reason(result, hso)
        if result.blocked or result.decision == "block" or permission == "deny":
            return PreToolDecision(
                deny=True,
                reason=reason or "Blocked by PreToolUse hook",
                updated_input=updated_input,
            )
        new_input = hso.get("updatedInput") or result.updated_input
        if new_input and updated_input is None:
            updated_input = new_input
        if additional_context is None:
            additional_context = result.additional_context or hso.get(
                "additionalContext"
            )
        # "defer" (or any unrecognized value) is no opinion: keep scanning,
        # then fall through to the normal approval flow.
        if permission in ("ask", "allow"):
            return PreToolDecision(
                force_prompt=permission == "ask",
                allow=permission == "allow",
                reason=reason,
                updated_input=updated_input,
                additional_context=additional_context,
            )
    return PreToolDecision(
        updated_input=updated_input, additional_context=additional_context
    )


def _pre_tool_reason(result: HookExecutionResult, hso: dict) -> str | None:
    """The most specific reason a PreToolUse hook gave, if any."""
    return (
        hso.get("permissionDecisionReason")
        or result.permission_decision_reason
        or result.reason
        or hso.get("reason")
    )


@dataclass
class PostToolDecision:
    """A PostToolUse hook's decision over a completed tool call."""

    block: bool = False
    reason: str | None = None
    updated_output: str | None = None
    additional_context: str | None = None


def extract_post_tool_decision(
    hook_results: list[HookExecutionResult],
) -> PostToolDecision:
    """Interpret PostToolUse blocks, output replacements, and context."""
    updated_output: str | None = None
    additional_context: str | None = None
    for result in hook_results:
        hso = _hook_specific(result)
        if result.blocked or result.decision == "block":
            return PostToolDecision(
                block=True,
                reason=result.reason
                or hso.get("reason")
                or "Blocked by PostToolUse hook",
            )
        new_output = hso.get("updatedToolOutput")
        if new_output is not None and updated_output is None:
            updated_output = new_output
        if additional_context is None:
            additional_context = result.additional_context or hso.get(
                "additionalContext"
            )
    return PostToolDecision(
        updated_output=updated_output, additional_context=additional_context
    )
