from __future__ import annotations

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


def extract_additional_context(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first additionalContext from hook results, if any.

    Claude Code hooks can return additionalContext to prepend context to the conversation.
    This helper extracts it from hook results for processing.

    Args:
        hook_results: List of hook execution results

    Returns:
        The first additionalContext found, or None if no hooks returned context.
    """
    for result in hook_results:
        if result.additional_context:
            return result.additional_context
    return None
