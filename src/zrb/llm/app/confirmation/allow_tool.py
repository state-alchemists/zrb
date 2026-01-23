import json
import re
from typing import Any, Awaitable, Callable

from pydantic_ai import ToolApproved, ToolCallPart

from zrb.llm.app.confirmation.handler import PostConfirmationMiddleware, UIProtocol


def allow_tool_usage(
    tool_name: str, kwargs_patterns: dict[str, str] = {}
) -> PostConfirmationMiddleware:
    """
    Returns a PostConfirmationMiddleware that automatically approves tool execution
    if it matches the given tool name and keyword argument patterns.
    - tool_name: The name of the tool to match.
    - kwargs_patterns: A dictionary mapping argument names to regex patterns.
    :return: A PostConfirmationMiddleware function.
    """

    async def middleware(
        ui: UIProtocol,
        call: ToolCallPart,
        user_response: str,
        next_handler: Callable[[UIProtocol, ToolCallPart, str], Awaitable[Any]],
    ) -> Any:
        # Check if tool name matches
        if call.tool_name != tool_name:
            return await next_handler(ui, call, user_response)

        # If kwargs_patterns is empty or None, approve
        if not kwargs_patterns:
            ui.append_to_output(f"\n✅ Auto-approved tool: {tool_name}")
            return ToolApproved()

        # Parse arguments
        try:
            args = call.args
            if isinstance(args, str):
                args = json.loads(args)

            if not isinstance(args, dict):
                # If args is not a dict (e.g. primitive), and kwargs_patterns is not empty,
                # we assume it doesn't match complex constraints (or we can't check keys).
                # So we delegate to the next handler.
                return await next_handler(ui, call, user_response)

        except (json.JSONDecodeError, ValueError):
            return await next_handler(ui, call, user_response)

        # Check constraints
        # "all parameter in the call parameter has to match the ones in kwargs_patterns
        # (if that parameter defined in the kwargs_patterns)"
        for arg_name, arg_value in args.items():
            if arg_name in kwargs_patterns:
                pattern = kwargs_patterns[arg_name]
                # Convert arg_value to string for regex matching
                if not re.search(pattern, str(arg_value)):
                    return await next_handler(ui, call, user_response)

        ui.append_to_output(f"\n✅ Auto-approved tool: {tool_name} with matching args")
        return ToolApproved()

    return middleware
