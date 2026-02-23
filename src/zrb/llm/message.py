from typing import Any, Sequence

from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_yellow


def ensure_alternating_roles(messages: list[Any]) -> list[Any]:
    """
    Ensures that the message history has alternating roles (User/Model -> Model/User).
    Consecutive messages of the same role are merged.
    """
    if not messages:
        return messages

    from pydantic_ai.messages import ModelRequest, ModelResponse

    new_messages: list[Any] = []
    for msg in messages:
        if not new_messages:
            new_messages.append(msg)
            continue

        last_msg = new_messages[-1]

        # Case 1: Sequential ModelRequests (User -> User) - MERGE
        if isinstance(msg, ModelRequest) and isinstance(last_msg, ModelRequest):
            new_last_msg = ModelRequest(parts=list(last_msg.parts) + list(msg.parts))
            new_messages[-1] = new_last_msg
            continue

        # Case 2: Sequential ModelResponses (Assistant -> Assistant) - MERGE
        if isinstance(msg, ModelResponse) and isinstance(last_msg, ModelResponse):
            from dataclasses import replace

            new_last_msg = replace(
                last_msg, parts=list(last_msg.parts) + list(msg.parts)
            )
            new_messages[-1] = new_last_msg
            continue

        new_messages.append(msg)

    return new_messages


def get_tool_pairs(messages: list[Any]) -> dict[str, dict[str, int | None]]:
    """
    Extract tool call/return pairs from messages.

    Returns a dict mapping tool_call_id to {"call_idx": index, "return_idx": index}
    where indices are message indices containing the call/return.
    """
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    tool_pairs = {}
    for i, msg in enumerate(messages):
        # Safely get message parts
        try:
            msg_parts = getattr(msg, "parts", [])
        except AttributeError:
            # Not a message with parts, skip
            continue

        for part in msg_parts:
            if isinstance(part, ToolCallPart):
                try:
                    tool_call_id = part.tool_call_id
                    if tool_call_id:
                        if tool_call_id not in tool_pairs:
                            tool_pairs[tool_call_id] = {
                                "call_idx": i,
                                "return_idx": None,
                            }
                        else:
                            # Update existing entry (in case return was seen first)
                            tool_pairs[tool_call_id]["call_idx"] = i
                except AttributeError:
                    # ToolCallPart without tool_call_id (shouldn't happen but be defensive)
                    continue

            elif isinstance(part, ToolReturnPart):
                try:
                    tool_call_id = part.tool_call_id
                    if tool_call_id:
                        if tool_call_id in tool_pairs:
                            tool_pairs[tool_call_id]["return_idx"] = i
                        else:
                            # Return seen before call (orphaned or call in summarized messages)
                            tool_pairs[tool_call_id] = {
                                "call_idx": None,
                                "return_idx": i,
                            }
                except AttributeError:
                    # ToolReturnPart without tool_call_id (shouldn't happen but be defensive)
                    continue

    return tool_pairs


def validate_tool_pair_integrity(messages: list[Any]) -> tuple[bool, list[str]]:
    """
    Check if all tool calls in the messages have corresponding returns.

    Returns (is_valid, list_of_problems)
    """
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    problems = []
    tool_calls_without_returns = []
    tool_returns_without_calls = []

    # Track tool calls and returns
    tool_calls = {}
    tool_returns = {}

    for i, msg in enumerate(messages):
        try:
            msg_parts = getattr(msg, "parts", [])
        except AttributeError:
            continue

        for part in msg_parts:
            if isinstance(part, ToolCallPart):
                try:
                    tool_call_id = part.tool_call_id
                    if tool_call_id:
                        tool_calls[tool_call_id] = i
                except AttributeError:
                    continue
            elif isinstance(part, ToolReturnPart):
                try:
                    tool_call_id = part.tool_call_id
                    if tool_call_id:
                        tool_returns[tool_call_id] = i
                except AttributeError:
                    continue

    # Check for calls without returns
    for tool_call_id, call_idx in tool_calls.items():
        if tool_call_id not in tool_returns:
            tool_calls_without_returns.append(
                f"Tool call {tool_call_id} at message {call_idx} has no return"
            )

    # Check for returns without calls (orphaned)
    for tool_call_id, return_idx in tool_returns.items():
        if tool_call_id not in tool_calls:
            tool_returns_without_calls.append(
                f"Tool return {tool_call_id} at message {return_idx} has no call"
            )

    if tool_calls_without_returns:
        problems.extend(tool_calls_without_returns)

    if tool_returns_without_calls:
        problems.extend(tool_returns_without_calls)

    is_valid = len(problems) == 0
    return is_valid, problems
