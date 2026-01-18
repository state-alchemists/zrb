import json
import re
from typing import Any, Awaitable, Callable, Dict, Optional

from pydantic_ai import ToolApproved

from zrb.llm.app.confirmation.handler import ConfirmationMiddleware, UIProtocol


def allow_tool_usage(
    tool_name: str, kwargs: Optional[Dict[str, str]] = None
) -> ConfirmationMiddleware:
    """
    Creates a confirmation middleware that automatically approves a tool execution
    if it matches the specified tool_name and argument constraints.

    :param tool_name: The name of the tool to allow.
    :param kwargs: A dictionary of regex patterns for arguments.
                   If None or empty, the tool is allowed regardless of arguments.
                   If provided, arguments in the tool call must match the regex patterns
                   specified in kwargs (only for arguments present in both).
    :return: A ConfirmationMiddleware function.
    """

    async def middleware(
        ui: UIProtocol,
        call: Any,
        response: str,
        next_handler: Callable[[UIProtocol, Any, str], Awaitable[Any]],
    ) -> Any:
        # Check if tool name matches
        if call.tool_name != tool_name:
            return await next_handler(ui, call, response)

        # If kwargs is empty or None, approve
        if not kwargs:
            ui.append_to_output(f"\n✅ Auto-approved tool: {tool_name}")
            return ToolApproved()

        # Parse arguments
        try:
            args = call.args
            if isinstance(args, str):
                args = json.loads(args)

            if not isinstance(args, dict):
                # If args is not a dict (e.g. primitive), and kwargs is not empty,
                # we assume it doesn't match complex constraints (or we can't check keys).
                # So we delegate to the next handler.
                return await next_handler(ui, call, response)

        except (json.JSONDecodeError, ValueError):
            return await next_handler(ui, call, response)

        # Check constraints
        # "all parameter in the call parameter has to match the ones in kwargs (if that parameter defined in the kwargs)"
        for arg_name, arg_value in args.items():
            if arg_name in kwargs:
                pattern = kwargs[arg_name]
                # Convert arg_value to string for regex matching
                if not re.search(pattern, str(arg_value)):
                    return await next_handler(ui, call, response)

        ui.append_to_output(f"\n✅ Auto-approved tool: {tool_name} with matching args")
        return ToolApproved()

    return middleware
