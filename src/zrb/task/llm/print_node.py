import json
from collections.abc import Callable
from typing import Any

from zrb.util.cli.style import stylize_faint


async def print_node(
    print_func: Callable, agent_run: Any, node: Any, log_indent_level: int = 0
):
    """Prints the details of an agent execution node using a provided print function."""
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from pydantic_ai.messages import (
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPartDelta,
        ThinkingPartDelta,
        ToolCallPartDelta,
    )

    meta = getattr(node, "id", None) or getattr(node, "request_id", None)
    if Agent.is_user_prompt_node(node):
        print_func(_format_header("🔠 Receiving input...", log_indent_level))
    elif Agent.is_model_request_node(node):
        # A model request node => We can stream tokens from the model's request
        print_func(_format_header("🧠 Processing...", log_indent_level))
        # Reference: https://ai.pydantic.dev/agents/#streaming-all-events-and-output
        try:
            async with node.stream(agent_run.ctx) as request_stream:
                is_streaming = False
                async for event in request_stream:
                    if isinstance(event, PartStartEvent) and event.part:
                        if is_streaming:
                            print_func("")
                        content = _get_event_part_content(event)
                        print_func(_format_content(content, log_indent_level), end="")
                        is_streaming = True
                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            content_delta = event.delta.content_delta
                            print_func(
                                _format_stream_content(content_delta, log_indent_level),
                                end="",
                            )
                        elif isinstance(event.delta, ThinkingPartDelta):
                            content_delta = event.delta.content_delta
                            print_func(
                                _format_stream_content(content_delta, log_indent_level),
                                end="",
                            )
                        elif isinstance(event.delta, ToolCallPartDelta):
                            args_delta = event.delta.args_delta
                            print_func(
                                _format_stream_content(args_delta, log_indent_level),
                                end="",
                            )
                        is_streaming = True
                    elif isinstance(event, FinalResultEvent) and event.tool_name:
                        if is_streaming:
                            print_func("")
                        tool_name = event.tool_name
                        print_func(
                            _format_content(
                                f"Result: tool_name={tool_name}", log_indent_level
                            )
                        )
                        is_streaming = False
                if is_streaming:
                    print_func("")
        except UnexpectedModelBehavior as e:
            print_func("")  # ensure newline consistency
            print_func(
                _format_content(
                    (
                        f"🟡 Unexpected Model Behavior: {e}. "
                        f"Cause: {e.__cause__}. Node.Id: {meta}"
                    ),
                    log_indent_level,
                )
            )
    elif Agent.is_call_tools_node(node):
        # A handle-response node => The model returned some data, potentially calls a tool
        print_func(_format_header("🧰 Calling Tool...", log_indent_level))
        try:
            async with node.stream(agent_run.ctx) as handle_stream:
                async for event in handle_stream:
                    if isinstance(event, FunctionToolCallEvent):
                        args = _get_event_part_args(event)
                        call_id = event.part.tool_call_id
                        tool_name = event.part.tool_name
                        print_func(
                            _format_content(
                                f"{call_id} | Call {tool_name} {args}", log_indent_level
                            )
                        )
                    elif isinstance(event, FunctionToolResultEvent):
                        call_id = event.tool_call_id
                        result_content = event.result.content
                        print_func(
                            _format_content(
                                f"{call_id} | {result_content}", log_indent_level
                            )
                        )
        except UnexpectedModelBehavior as e:
            print_func("")  # ensure newline consistency
            print_func(
                _format_content(
                    (
                        f"🟡 Unexpected Model Behavior: {e}. "
                        f"Cause: {e.__cause__}. Node.Id: {meta}"
                    ),
                    log_indent_level,
                )
            )
    elif Agent.is_end_node(node):
        # Once an End node is reached, the agent run is complete
        print_func(_format_header("✅ Completed...", log_indent_level))


def _format_header(text: str | None, log_indent_level: int = 0) -> str:
    return _format(
        text,
        base_indent=2,
        first_indent=0,
        indent=0,
        log_indent_level=log_indent_level,
    )


def _format_content(text: str | None, log_indent_level: int = 0) -> str:
    return _format(
        text,
        base_indent=2,
        first_indent=3,
        indent=3,
        log_indent_level=log_indent_level,
    )


def _format_stream_content(text: str | None, log_indent_level: int = 0) -> str:
    return _format(
        text,
        base_indent=2,
        indent=3,
        log_indent_level=log_indent_level,
        is_stream=True,
    )


def _format(
    text: str | None,
    base_indent: int = 0,
    first_indent: int = 0,
    indent: int = 0,
    log_indent_level: int = 0,
    is_stream: bool = False,
) -> str:
    if text is None:
        text = ""
    line_prefix = (base_indent * (log_indent_level + 1) + indent) * " "
    processed_text = text.replace("\n", f"\n{line_prefix}")
    if is_stream:
        return stylize_faint(processed_text)
    first_line_prefix = (base_indent * (log_indent_level + 1) + first_indent) * " "
    return stylize_faint(f"{first_line_prefix}{processed_text}")


def _get_event_part_args(event: Any) -> Any:
    # Handle empty arguments across different providers
    if event.part.args == "" or event.part.args is None:
        return {}
    if isinstance(event.part.args, str):
        # Some providers might send "null" or "{}" as a string
        if event.part.args.strip() in ["null", "{}"]:
            return {}
        try:
            obj = json.loads(event.part.args)
            if isinstance(obj, dict):
                return _truncate_kwargs(obj)
        except json.JSONDecodeError:
            pass
    # Handle dummy property if present (from our schema sanitization)
    if isinstance(event.part.args, dict):
        return _truncate_kwargs(event.part.args)
    print(type(event.part.args))
    return event.part.args


def _truncate_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: _truncate_arg(val) for key, val in kwargs.items()}


def _truncate_arg(arg: str, length: int = 19) -> str:
    if isinstance(arg, str) and len(arg) > length:
        return f"{arg[:length-4]} ..."
    return arg


def _get_event_part_content(event: Any) -> str:
    if not hasattr(event, "part"):
        return f"{event}"
    if not hasattr(event.part, "content"):
        return f"{event.part}"
    return getattr(event.part, "content")
