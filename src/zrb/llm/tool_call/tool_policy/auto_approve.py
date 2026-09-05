import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import ToolPolicy

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


def auto_approve(  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    tool_name: str,
    kwargs_patterns: dict[str, str] | Callable[[dict[str, Any]], bool] | None = None,
) -> ToolPolicy:
    """
    Returns a ToolPolicy that automatically approves tool execution
    if it matches the given tool name and keyword argument patterns.
    - tool_name: The name of the tool to match.
    - kwargs_patterns: A dictionary mapping argument names to regex patterns.
    :return: A ToolPolicy function.
    """
    if kwargs_patterns is None:
        kwargs_patterns = {}

    async def approve_tool_call_policy(
        ui: "AnyAgentOutput",
        call: "ToolCallPart",
        next_handler: Callable[["AnyAgentOutput", "ToolCallPart"], Awaitable[Any]],
    ) -> Any:
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolApproved

        if call.tool_name != tool_name:
            return await next_handler(ui, call)

        # Parse arguments (best effort) — needed for the sandbox-escape check
        # even when no kwargs_patterns are configured.
        args = parse_tool_args(call)

        # A sandbox-escape request must always reach a human, regardless of
        # any auto-approval configuration.
        if isinstance(args, dict) and args.get("dangerously_skip_sandbox"):
            return await next_handler(ui, call)

        if not kwargs_patterns:
            return ToolApproved()

        if not isinstance(args, dict):
            # If args is not a dict (e.g. primitive), and kwargs_patterns is not empty,
            # we assume it doesn't match complex constraints (or we can't check keys).
            # So we delegate to the next handler.
            return await next_handler(ui, call)

        # "all parameter in the call parameter has to match the ones in kwargs_patterns
        # (if that parameter defined in the kwargs_patterns)"
        if callable(kwargs_patterns):
            if kwargs_patterns(args):
                return ToolApproved()
        else:
            for arg_name, arg_value in args.items():
                if arg_name in kwargs_patterns:
                    pattern = kwargs_patterns[arg_name]
                    if not re.search(pattern, str(arg_value)):
                        return await next_handler(ui, call)

            return ToolApproved()
        return await next_handler(ui, call)

    return approve_tool_call_policy
