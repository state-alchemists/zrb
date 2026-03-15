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
    status_event: Callable[..., None] | None = None,
):
    """Create an event handler for agent stream events.

    Args:
        print_event: Function to print regular output (buffered for subagents).
        indent_level: Indentation level for nested output.
        show_tool_call_detail: Whether to show detailed tool call parameters.
        show_tool_result: Whether to show tool result content.
        status_event: Optional function to print status messages (bypasses buffer for subagents).
                      If None, falls back to print_event.
    """
    from pydantic_ai import (
        AgentRunResultEvent,
        FinalResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPartDelta,
        ThinkingPartDelta,
        ToolCallPartDelta,
    )

    # Use status_event if provided, otherwise fall back to print_event
    status_fn = status_event if status_event is not None else print_event

    indentation = indent_level * 2 * " "
    progress_char_list = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    progress_char_index = 0
    was_tool_call_delta = False
    event_prefix = indentation

    def fprint(content: str, preserve_leading_newline: bool = False, use_status: bool = False):
        """Format and print content with proper indentation.

        Args:
            content: The content to print.
            preserve_leading_newline: Whether to preserve leading newlines.
            use_status: If True, use status_fn (bypasses buffer); otherwise use print_event.
        """
        # Handle trailing newline specially
        has_trailing_newline = content.endswith("\n")
        if has_trailing_newline:
            content = content[:-1]

        if preserve_leading_newline:
            if content.startswith("\n"):
                # Already has newline, preserve it
                result = "\n" + content[1:].replace("\n", f"\n{indentation}   ")
            else:
                # Need to add newline
                result = "\n" + content.replace("\n", f"\n{indentation}   ")
        else:
            result = content.replace("\n", f"\n{indentation}   ")

        # Add back trailing newline without indentation
        if has_trailing_newline:
            result += "\n"

        # Choose the appropriate function based on use_status
        print_fn = status_fn if use_status else print_event
        return print_fn(result)

    async def handle_event(event: "AgentStreamEvent"):
        from pydantic_ai import ToolCallPart

        nonlocal progress_char_index, was_tool_call_delta, event_prefix
        if isinstance(event, PartStartEvent):
            # Skip ToolCallPart start, we handle it in Deltas/CallEvent
            if isinstance(event.part, ToolCallPart):
                return
            content = _get_event_part_content(event)
            # Use preserve_leading_newline=True because event_prefix contains the correctly indented newline
            fprint(f"{event_prefix}🧠 {content}", preserve_leading_newline=True)
            was_tool_call_delta = False
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                # Standard fprint for deltas to ensure wrapping indentation
                fprint(f"{event.delta.content_delta}")
                was_tool_call_delta = False
            elif isinstance(event.delta, ThinkingPartDelta):
                fprint(f"{event.delta.content_delta}")
                was_tool_call_delta = False
            elif isinstance(event.delta, ToolCallPartDelta):
                if show_tool_call_detail:
                    fprint(f"{event.delta.args_delta}")
                    was_tool_call_delta = True
                else:
                    progress_char = progress_char_list[progress_char_index]
                    if not was_tool_call_delta:
                        # Print newline for tool param spinner
                        fprint("\n")

                    # Combine \r with text to ensure proper handling by UI._append_to_output
                    # Use status_fn for progress updates (should bypass buffer)
                    status_fn(
                        f"\r{indentation}🔄 Prepare tool parameters {progress_char}"
                    )
                    progress_char_index += 1
                    if progress_char_index >= len(progress_char_list):
                        progress_char_index = 0
                    was_tool_call_delta = True
        elif isinstance(event, FunctionToolCallEvent):
            args = _get_truncated_event_part_args(event)
            # If we were showing 'prepare parameters', clear that line first
            if was_tool_call_delta and not show_tool_call_detail:
                # Clear the line with \r before printing tool call
                status_fn("\r")
                # event_prefix will naturally overwrite it if it's on the same line

            # Use status_fn for tool call notifications (bypass buffer for subagent visibility)
            fprint(
                f"{event_prefix}🧰 {event.part.tool_call_id} | {event.part.tool_name} {args}\n",
                preserve_leading_newline=True,
                use_status=True,
            )
            was_tool_call_delta = False
        elif isinstance(event, FunctionToolResultEvent):
            if show_tool_result:
                fprint(
                    f"{event_prefix}🔠 {event.tool_call_id} | Return {event.result.content}\n",
                    preserve_leading_newline=True,
                    use_status=True,
                )
            else:
                fprint(
                    f"{event_prefix}🔠 {event.tool_call_id} Executed\n",
                    preserve_leading_newline=True,
                    use_status=True,
                )
            was_tool_call_delta = False
        elif isinstance(event, AgentRunResultEvent):
            usage = event.result.usage()
            usage_msg = " ".join(
                [
                    "💸",
                    f"(Requests: {usage.requests} |",
                    f"Tool Calls: {usage.tool_calls} |",
                    f"Total: {usage.total_tokens})",
                    f"Input: {usage.input_tokens} |",
                    f"Audio Input: {usage.input_audio_tokens} |",
                    f"Output: {usage.output_tokens} |",
                    f"Audio Output: {usage.output_audio_tokens} |",
                    f"Cache Read: {usage.cache_read_tokens} |",
                    f"Cache Write: {usage.cache_write_tokens} |",
                    f"Details: {usage.details}",
                ]
            )
            fprint(
                f"{event_prefix}{stylize_faint(usage_msg)}\n",
                preserve_leading_newline=True,
                use_status=True,
            )
            was_tool_call_delta = False
        elif isinstance(event, FinalResultEvent):
            was_tool_call_delta = False
        event_prefix = f"\n{indentation}"

    return handle_event


def create_faint_printer(print_fn: Callable[..., None]):
    def faint_print(content: str, end: str = ""):
        message = stylize_faint(content)
        print_fn(message, end=end)

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
        return ""
    part = getattr(event, "part")
    if hasattr(part, "content"):
        return getattr(part, "content")
    # For parts without content (like ToolCallPart, though we skip it now), return empty or simple repr
    return ""
