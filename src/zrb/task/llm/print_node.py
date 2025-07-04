import json
from collections.abc import Callable
from typing import Any

from zrb.util.cli.style import stylize_faint


async def print_node(print_func: Callable, agent_run: Any, node: Any):
    """Prints the details of an agent execution node using a provided print function."""
    from pydantic_ai import Agent
    from pydantic_ai.messages import (
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPartDelta,
        ToolCallPartDelta,
    )

    if Agent.is_user_prompt_node(node):
        # A user prompt node => The user has provided input
        print_func(stylize_faint(f"👤 User: {node.user_prompt}"))
    elif Agent.is_model_request_node(node):
        # A model request node => We can stream tokens from the model's request
        print_func(stylize_faint("🧠 LLM is thinking..."))
        async with node.stream(agent_run.ctx) as request_stream:
            is_streaming = False
            async for event in request_stream:
                if isinstance(event, PartStartEvent):
                    if is_streaming:
                        print_func("")
                    print_func(
                        stylize_faint(
                            f"    Starting part {event.index}: {event.part!r}"
                        ),
                    )
                    is_streaming = False
                elif isinstance(event, PartDeltaEvent):
                    if isinstance(event.delta, TextPartDelta):
                        print_func(
                            stylize_faint(f"{event.delta.content_delta}"),
                            end="",
                        )
                    elif isinstance(event.delta, ToolCallPartDelta):
                        print_func(
                            stylize_faint(f"{event.delta.args_delta}"),
                            end="",
                        )
                    is_streaming = True
                elif isinstance(event, FinalResultEvent):
                    if is_streaming:
                        print_func("")
                    print_func(
                        stylize_faint(f"    Result: tool_name={event.tool_name}"),
                    )
                    is_streaming = False
            if is_streaming:
                print_func("")
    elif Agent.is_call_tools_node(node):
        # A handle-response node => The model returned some data, potentially calls a tool
        print_func(stylize_faint("🛠️  LLM is calling a function..."))
        async with node.stream(agent_run.ctx) as handle_stream:
            async for event in handle_stream:
                if isinstance(event, FunctionToolCallEvent):
                    # Handle empty arguments across different providers
                    if event.part.args == "" or event.part.args is None:
                        event.part.args = {}
                    elif isinstance(
                        event.part.args, str
                    ) and event.part.args.strip() in ["null", "{}"]:
                        # Some providers might send "null" or "{}" as a string
                        event.part.args = {}
                    # Handle dummy property if present (from our schema sanitization)
                    if (
                        isinstance(event.part.args, dict)
                        and "_dummy" in event.part.args
                    ):
                        del event.part.args["_dummy"]
                    print_func(
                        stylize_faint(
                            f"  - Name: {event.part.tool_name}\n"
                            f'  - Arguments: {json.dumps(event.part.args, indent=2)}\n'
                            f"  - ID: {event.part.tool_call_id}"
                        )
                    )
                elif isinstance(event, FunctionToolResultEvent):
                    print_func(
                        stylize_faint(
                            f"  - Tool call {event.tool_call_id!r} returned:\n"
                            f"    {event.result.content}"
                        )
                    )
    elif Agent.is_end_node(node):
        # Once an End node is reached, the agent run is complete
        print_func(stylize_faint("✅ End of run"))
