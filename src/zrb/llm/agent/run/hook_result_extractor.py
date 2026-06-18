from __future__ import annotations

from dataclasses import dataclass

from zrb.llm.hook.executor import HookExecutionResult


def extract_system_message(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first systemMessage from hook results, if any.

    Claude Code hooks can return systemMessage to inject context into the conversation.
    This helper extracts it from hook results for processing.

    Args:
        hook_results: List of hook execution results

    Returns:
        The first systemMessage found, or None if no hooks returned a message.
    """
    for result in hook_results:
        if result.system_message:
            return result.system_message
    return None


def extract_replace_response(hook_results: list[HookExecutionResult]) -> bool:
    """Extract the replaceResponse flag from hook results.

    If any hook returns replaceResponse=True, the extended session's response
    should replace the original response. Default is False (return original).

    Args:
        hook_results: List of hook execution results

    Returns:
        True if any hook wants to replace the response, False otherwise.
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
    inside ``hookSpecificOutput``. Both are checked.

    Args:
        hook_results: List of hook execution results

    Returns:
        The first additionalContext found, or None if no hooks returned context.
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
    """Extract a Claude-style block decision from turn-level hook results.

    A hook blocks via exit code 2 (``blocked``) or ``decision == "block"``.
    Returns the first decisive block (zrb runs hooks sequentially by priority,
    first-block-wins). ``additionalContext`` is also surfaced for the non-blocking
    feedback case.
    """
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


def extract_permission_decision(
    hook_results: list[HookExecutionResult],
) -> str | None:
    """Extract a PermissionRequest hook's auto-resolution, if any.

    Claude's PermissionRequest hook nests its verdict as
    ``hookSpecificOutput.decision.behavior`` ("allow" | "deny"). A flatter
    ``permissionDecision`` is also accepted. Returns the first "allow"/"deny", or
    None to leave the approval cascade to decide (the observe-only case).
    """
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
    reason: str | None = None
    updated_input: dict | None = None
    additional_context: str | None = None


def extract_pre_tool_decision(
    hook_results: list[HookExecutionResult],
) -> PreToolDecision:
    """Interpret PreToolUse hook results per Claude's protocol.

    Honors (top level or nested in ``hookSpecificOutput``):
    - ``permissionDecision: "deny"`` / exit-2 / ``decision: "block"`` → deny.
    - ``permissionDecision: "allow"`` → allow (auto-approve, skip the prompt).
    - ``updatedInput`` → argument rewrite (first non-empty wins).

    zrb runs hooks sequentially by priority; the first decisive deny/allow wins.
    """
    updated_input: dict | None = None
    additional_context: str | None = None
    for result in hook_results:
        hso = _hook_specific(result)
        permission = hso.get("permissionDecision") or result.permission_decision
        reason = (
            hso.get("permissionDecisionReason")
            or result.permission_decision_reason
            or result.reason
            or hso.get("reason")
        )
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
        if permission == "allow":
            return PreToolDecision(
                allow=True,
                reason=reason,
                updated_input=updated_input,
                additional_context=additional_context,
            )
    return PreToolDecision(
        updated_input=updated_input, additional_context=additional_context
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
    """Interpret PostToolUse hook results per Claude's protocol.

    Honors ``decision: "block"`` (discard the result, feed the reason back to the
    model) and ``updatedToolOutput`` (replace the model-facing content). The first
    block wins; the first non-empty ``updatedToolOutput`` wins otherwise.
    """
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
