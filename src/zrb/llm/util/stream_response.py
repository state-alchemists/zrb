import json
from typing import TYPE_CHECKING, Any, Callable, Literal

from zrb.context.any_context import AnyContext
from zrb.util.cli.style import stylize_faint

if TYPE_CHECKING:
    from pydantic_ai import AgentStreamEvent

PrintKind = Literal["text", "streaming", "progress", "tool_call", "usage", "thinking"]


def create_event_handler(
    print_fn: Callable[[str, str], Any],
    indent_level: int = 1,
    show_tool_call_detail: bool = False,
    show_tool_result: bool = False,
):
    """Create an event handler for agent stream events.

    Args:
        print_fn: Function to print output. Called as print_fn(text, kind) where
                  kind is one of "text", "progress", "tool_call", "usage", "thinking".
        indent_level: Indentation level for nested output.
        show_tool_call_detail: Whether to show detailed tool call parameters.
        show_tool_result: Whether to show tool result content.
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

    indentation = indent_level * 2 * " "
    progress_char_list = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    progress_char_index = 0
    was_tool_call_delta = False
    # True after PartStartEvent(ToolCallPart) prints the static indicator.
    # Lets the first ToolCallPartDelta skip the extra newline (line already exists)
    # and overwrite the static text. Cleared when was_tool_call_delta goes True.
    was_tool_call_start = False
    event_prefix = indentation
    # Track printed tool calls to avoid duplicate prints in deferred tool flow
    # (FunctionToolCallEvent fires twice: once when deferred, once when executed)
    printed_tool_call_ids: set[str] = set()

    def fprint(
        content: str,
        preserve_leading_newline: bool = False,
        kind: PrintKind = "text",
    ):
        """Format and print content with proper indentation."""
        # Handle trailing newline specially
        has_trailing_newline = content.endswith("\n")
        if has_trailing_newline:
            content = content[:-1]

        if preserve_leading_newline:
            if content.startswith("\n"):
                result = "\n" + content[1:].replace("\n", f"\n{indentation}   ")
            else:
                result = "\n" + content.replace("\n", f"\n{indentation}   ")
        else:
            result = content.replace("\n", f"\n{indentation}   ")

        if has_trailing_newline:
            result += "\n"

        return print_fn(result, kind)

    async def handle_event(event: "AgentStreamEvent"):
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        nonlocal progress_char_index, was_tool_call_delta, was_tool_call_start, event_prefix
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, ToolCallPart):
                # Show a static indicator so the user sees something while parameters
                # are being prepared.  Providers that stream deltas (OpenAI, Anthropic)
                # will overwrite this line with the animated spinner on the first
                # ToolCallPartDelta.  Providers that don't stream (e.g. Ollama) will
                # leave this line as-is, and the 🧰 line will appear below it.
                if not show_tool_call_detail:
                    fprint(
                        f"{event_prefix}🔄 Prepare tool parameters...",
                        preserve_leading_newline=True,
                        kind="progress",
                    )
                    was_tool_call_start = True
                return
            if isinstance(event.part, TextPart):
                content = _get_event_part_content(event)
                if content:
                    fprint(
                        f"{event_prefix}{content}",
                        preserve_leading_newline=True,
                        kind="streaming",
                    )
            else:
                content = _get_event_part_content(event)
                fprint(
                    f"{event_prefix}🧠 {content}",
                    preserve_leading_newline=True,
                    kind="thinking",
                )
            was_tool_call_delta = False
            was_tool_call_start = False

        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                fprint(f"{event.delta.content_delta}", kind="streaming")
                was_tool_call_delta = False
                was_tool_call_start = False
            elif isinstance(event.delta, ThinkingPartDelta):
                fprint(f"{event.delta.content_delta}", kind="thinking")
                was_tool_call_delta = False
                was_tool_call_start = False
            elif isinstance(event.delta, ToolCallPartDelta):
                if show_tool_call_detail:
                    fprint(f"{event.delta.args_delta}", kind="tool_call")
                    was_tool_call_delta = True
                    was_tool_call_start = False
                else:
                    progress_char = progress_char_list[progress_char_index]
                    if not was_tool_call_delta and not was_tool_call_start:
                        # Neither static indicator nor prior delta: add a newline
                        # first so the spinner starts on its own line.
                        fprint("\n", kind="progress")
                    # Overwrite the current line (static indicator or prior spinner)
                    # with the animated spinner character.
                    print_fn(
                        f"\r{indentation}🔄 Prepare tool parameters {progress_char}",
                        "progress",
                    )
                    progress_char_index += 1
                    if progress_char_index >= len(progress_char_list):
                        progress_char_index = 0
                    was_tool_call_delta = True
                    was_tool_call_start = False
        elif isinstance(event, FunctionToolCallEvent):
            args = _get_truncated_event_part_args(event)
            if was_tool_call_delta and not show_tool_call_detail:
                # Clear the animated spinner line before printing the tool call.
                print_fn("\r", "progress")

            tool_call_id = event.part.tool_call_id
            if tool_call_id not in printed_tool_call_ids:
                printed_tool_call_ids.add(tool_call_id)
                fprint(
                    f"{event_prefix}🧰 {tool_call_id} | {event.part.tool_name} {args}\n",
                    preserve_leading_newline=True,
                    kind="tool_call",
                )
            was_tool_call_delta = False
        elif isinstance(event, FunctionToolResultEvent):
            if show_tool_result:
                fprint(
                    f"{event_prefix}🔠 {event.tool_call_id} | Return {event.result.content}\n",
                    preserve_leading_newline=True,
                    kind="tool_call",
                )
            else:
                fprint(
                    f"{event_prefix}🔠 {event.tool_call_id} Executed\n",
                    preserve_leading_newline=True,
                    kind="tool_call",
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
                f"{event_prefix}{usage_msg}\n",
                preserve_leading_newline=True,
                kind="usage",
            )
            was_tool_call_delta = False
        elif isinstance(event, FinalResultEvent):
            was_tool_call_delta = False
        event_prefix = f"\n{indentation}"

    return handle_event


def _get_truncated_event_part_args(event: "AgentStreamEvent") -> Any:
    if not hasattr(event, "part"):
        return {}
    part = getattr(event, "part")
    if not hasattr(part, "args"):
        return {}
    args = getattr(part, "args")
    if args == "" or args is None:
        return {}
    if isinstance(args, str):
        if args.strip() in ["null", "{}"]:
            return {}
        try:
            obj = json.loads(args)
            if isinstance(obj, dict):
                return _truncate_kwargs(obj)
        except json.JSONDecodeError:
            pass
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
    return ""
