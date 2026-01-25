import json
import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.handler import ToolPolicy, UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


def auto_approve(
    tool_name: str,
    kwargs_patterns: dict[str, str] | Callable[[dict[str, Any]], bool] = {},
) -> ToolPolicy:
    """
    Returns a ToolPolicy that automatically approves tool execution
    if it matches the given tool name and keyword argument patterns.
    - tool_name: The name of the tool to match.
    - kwargs_patterns: A dictionary mapping argument names to regex patterns.
    :return: A ToolPolicy function.
    """

    async def approve_tool_call_policy(
        ui: UIProtocol,
        call: "ToolCallPart",
        next_handler: Callable[[UIProtocol, "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        from pydantic_ai import ToolApproved

        # Check if tool name matches
        if call.tool_name != tool_name:
            return await next_handler(ui, call)

        # If kwargs_patterns is empty or None, approve
        if not kwargs_patterns:
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
                return await next_handler(ui, call)

        except (json.JSONDecodeError, ValueError):
            return await next_handler(ui, call)

        # Check constraints
        # "all parameter in the call parameter has to match the ones in kwargs_patterns
        # (if that parameter defined in the kwargs_patterns)"
        if callable(kwargs_patterns):
            if kwargs_patterns(args):
                return ToolApproved()
        else:
            for arg_name, arg_value in args.items():
                if arg_name in kwargs_patterns:
                    pattern = kwargs_patterns[arg_name]
                    # Convert arg_value to string for regex matching
                    if not re.search(pattern, str(arg_value)):
                        return await next_handler(ui, call)

            return ToolApproved()
        return await next_handler(ui, call)

    return approve_tool_call_policy
