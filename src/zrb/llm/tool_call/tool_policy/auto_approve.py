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
    """ToolPolicy approving `tool_name` calls whose args match `kwargs_patterns`.

    `kwargs_patterns` maps arg names to regexes, or is a predicate over the args.
    With a mapping, every named arg must be present and match its regex.
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

        args = parse_tool_args(call)
        # A sandbox-escape request must always reach a human.
        if isinstance(args, dict) and args.get("dangerously_skip_sandbox"):
            return await next_handler(ui, call)

        if not kwargs_patterns:
            return ToolApproved()

        if not isinstance(args, dict):
            return await next_handler(ui, call)

        if callable(kwargs_patterns):
            if kwargs_patterns(args):
                return ToolApproved()
        else:
            for arg_name, pattern in kwargs_patterns.items():
                if arg_name not in args or not re.search(
                    pattern, str(args[arg_name])
                ):
                    return await next_handler(ui, call)

            return ToolApproved()
        return await next_handler(ui, call)

    return approve_tool_call_policy
