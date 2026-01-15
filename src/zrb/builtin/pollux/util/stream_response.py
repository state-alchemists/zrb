import json
from typing import TYPE_CHECKING, Any, Callable

from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from pydantic_ai import AgentStreamEvent


def create_event_handler(
    print_event: Callable[..., None],
    indent_level: int = 1,
    show_tool_call_detail: bool = False,
    show_tool_result: bool = False,
):
    from pydantic_ai import (
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPartDelta,
        ThinkingPartDelta,
        ToolCallPartDelta,
    )

    indentation = indent_level * 2 * " "
    progress_char_list = ["|", "/", "-", "\\"]
    progress_char_index = 0
    was_tool_call_delta = False

    def fprint(content: str):
        if content.startswith("\n"):
            return print_event("\n" + content[1:].replace("\n", f"\n{indentation}   "))
        return print_event(content.replace("\n", f"\n{indentation}   "))

    async def handle_event(event: "AgentStreamEvent"):
        nonlocal progress_char_index, was_tool_call_delta
        if isinstance(event, PartStartEvent):
            content = _get_event_part_content(event)
            fprint(f"\n{indentation}🧠 {content}")
            was_tool_call_delta = False
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                fprint(f"{event.delta.content_delta}")
                was_tool_call_delta = False
            elif isinstance(event.delta, ThinkingPartDelta):
                fprint(f"{event.delta.content_delta}")
                was_tool_call_delta = False
            elif isinstance(event.delta, ToolCallPartDelta):
                if show_tool_call_detail:
                    fprint(f"{event.delta.args_delta}")
                else:
                    progress_char = progress_char_list[progress_char_index]
                    line_start = "\r" if was_tool_call_delta else "\n"
                    print_event(
                        f"{line_start}{indentation} Prepare tool parameters {progress_char}"
                    )
                    progress_char_index += 1
                    if progress_char_index >= len(progress_char_list):
                        progress_char_index = 0
                    was_tool_call_delta = True
        elif isinstance(event, FunctionToolCallEvent):
            args = _get_truncated_event_part_args(event)
            fprint(
                f"\n{indentation}🧰 {event.part.tool_call_id} | {event.part.tool_name} {args}\n"
            )
            was_tool_call_delta = False
        elif isinstance(event, FunctionToolResultEvent):
            if show_tool_result:
                fprint(
                    f"\n{indentation}🔠 {event.tool_call_id} | Return {event.result.content}\n"
                )
            else:
                fprint(f"\n{indentation}🔠 {event.tool_call_id} Executed\n")
            was_tool_call_delta = False
        elif isinstance(event, FinalResultEvent):
            was_tool_call_delta = False

    return handle_event


def create_faint_printer(ctx: AnyContext):
    def faint_print(*values: object):
        message = stylize_faint(" ".join([f"{value}" for value in values]))
        ctx.print(message, end="", plain=True)

    return faint_print


def _get_truncated_event_part_args(event: "AgentStreamEvent") -> Any:
    # Handle empty arguments across different providers
    if not hasattr(event, "part"):
        return {}
    part = getattr(event, "part")
    if not hasattr(part, "args"):
        return {}
    args = getattr(part, "args")
    if args == "" or args is None:
        return {}
    if isinstance(args, str):
        # Some providers might send "null" or "{}" as a string
        if args.strip() in ["null", "{}"]:
            return {}
        try:
            obj = json.loads(args)
            if isinstance(obj, dict):
                return _truncate_kwargs(obj)
        except json.JSONDecodeError:
            pass
    # Handle dummy property if present (from our schema sanitization)
    if isinstance(args, dict):
        return _truncate_kwargs(args)
    return args


def _truncate_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: _truncate_arg(val) for key, val in kwargs.items()}


def _truncate_arg(arg: str, length: int = 30) -> str:
    if isinstance(arg, str) and len(arg) > length:
        return f"{arg[:length-4]} ..."
    return arg


def _get_event_part_content(event: "AgentStreamEvent") -> str:
    if not hasattr(event, "part"):
        return f"{event}"
    part = getattr(event, "part")
    if not hasattr(part, "content"):
        return f"{part}"
    return getattr(part, "content")
