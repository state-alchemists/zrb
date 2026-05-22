import json
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from pydantic_ai import AgentStreamEvent

PrintKind = Literal["text", "streaming", "progress", "tool_call", "usage", "thinking"]


class StreamEventHandler:
    """Stateful handler for agent stream events."""

    def __init__(
        self,
        print_fn: Callable[[str, str], Any],
        indent_level: int = 1,
        show_tool_call_detail: bool = False,
        show_tool_result: bool = False,
    ):
        self._print_fn = print_fn
        self._indentation = indent_level * 2 * " "
        self._show_tool_call_detail = show_tool_call_detail
        self._show_tool_result = show_tool_result

        self._progress_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._progress_idx = 0
        self._was_tool_call_delta = False
        self._was_tool_call_start = False
        self._event_prefix = self._indentation
        self._printed_tool_ids = set()

    def _fprint(
        self,
        content: str,
        preserve_leading_newline: bool = False,
        kind: PrintKind = "text",
    ):
        has_trailing_newline = content.endswith("\n")
        if has_trailing_newline:
            content = content[:-1]

        if preserve_leading_newline:
            if content.startswith("\n"):
                result = "\n" + content[1:].replace("\n", f"\n{self._indentation}   ")
            else:
                result = "\n" + content.replace("\n", f"\n{self._indentation}   ")
        else:
            result = content.replace("\n", f"\n{self._indentation}   ")

        if has_trailing_newline:
            result += "\n"

        return self._print_fn(result, kind)

    async def __call__(self, event: "AgentStreamEvent"):
        from pydantic_ai import (
            AgentRunResultEvent,
            FinalResultEvent,
            FunctionToolCallEvent,
            FunctionToolResultEvent,
            PartDeltaEvent,
            PartStartEvent,
        )

        skip_prefix_update = False

        if isinstance(event, PartStartEvent):
            skip_prefix_update = self._handle_part_start(event)
        elif isinstance(event, PartDeltaEvent):
            self._handle_part_delta(event)
        elif isinstance(event, FunctionToolCallEvent):
            self._handle_tool_call(event)
        elif isinstance(event, FunctionToolResultEvent):
            self._handle_tool_result(event)
        elif isinstance(event, AgentRunResultEvent):
            self._handle_run_result(event)
        elif isinstance(event, FinalResultEvent):
            self._was_tool_call_delta = False

        if not skip_prefix_update:
            self._event_prefix = f"\n{self._indentation}"

    def _handle_part_start(self, event: "AgentStreamEvent") -> bool:
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        if isinstance(event.part, ToolCallPart):
            # Show a static indicator so the user sees something while parameters
            # are being prepared.  Providers that stream deltas (OpenAI, Anthropic)
            # will overwrite this line with the animated spinner on the first
            # ToolCallPartDelta.  Providers that don't stream (e.g. Ollama) will
            # leave this line as-is, and the 🧰 line will appear below it.

            if not self._show_tool_call_detail:
                self._fprint(
                    f"{self._event_prefix}🔄 Prepare tool parameters...",
                    preserve_leading_newline=True,
                    kind="progress",
                )
                self._was_tool_call_start = True
            return True

        if isinstance(event.part, TextPart):
            content = _get_event_part_content(event)
            if content:
                self._fprint(
                    f"{self._event_prefix}{content}",
                    preserve_leading_newline=True,
                    kind="streaming",
                )
        else:
            content = _get_event_part_content(event)
            self._fprint(
                f"{self._event_prefix}🧠 {content}",
                preserve_leading_newline=True,
                kind="thinking",
            )
        self._was_tool_call_delta = False
        self._was_tool_call_start = False
        return False

    def _handle_part_delta(self, event: "AgentStreamEvent"):
        from pydantic_ai import TextPartDelta, ThinkingPartDelta, ToolCallPartDelta

        if isinstance(event.delta, TextPartDelta):
            self._fprint(f"{event.delta.content_delta}", kind="streaming")
            self._was_tool_call_delta = False
            self._was_tool_call_start = False
        elif isinstance(event.delta, ThinkingPartDelta):
            self._fprint(f"{event.delta.content_delta}", kind="thinking")
            self._was_tool_call_delta = False
            self._was_tool_call_start = False
        elif isinstance(event.delta, ToolCallPartDelta):
            if self._show_tool_call_detail:
                self._fprint(f"{event.delta.args_delta}", kind="tool_call")
                self._was_tool_call_delta = True
                self._was_tool_call_start = False
            else:
                progress_char = self._progress_chars[self._progress_idx]
                if not self._was_tool_call_delta and not self._was_tool_call_start:
                    self._fprint("\n", kind="progress")
                self._print_fn(
                    f"\r{self._indentation}🔄 Prepare tool parameters {progress_char}",
                    "progress",
                )
                self._progress_idx += 1
                if self._progress_idx >= len(self._progress_chars):
                    self._progress_idx = 0
                self._was_tool_call_delta = True
                self._was_tool_call_start = False

    def _handle_tool_call(self, event: "AgentStreamEvent"):
        args = _get_truncated_event_part_args(event)
        if self._was_tool_call_delta and not self._show_tool_call_detail:
            self._print_fn("\r", "progress")

        tool_call_id = event.part.tool_call_id
        if tool_call_id not in self._printed_tool_ids:
            self._printed_tool_ids.add(tool_call_id)
            self._fprint(
                f"{self._event_prefix}🧰 {tool_call_id} | {event.part.tool_name} {args}\n",
                preserve_leading_newline=True,
                kind="tool_call",
            )
        self._was_tool_call_delta = False

    def _handle_tool_result(self, event: "AgentStreamEvent"):
        if self._show_tool_result:
            self._fprint(
                f"{self._event_prefix}🔠 {event.tool_call_id} | Return {event.result.content}\n",
                preserve_leading_newline=True,
                kind="tool_call",
            )
        else:
            self._fprint(
                f"{self._event_prefix}🔠 {event.tool_call_id} Executed\n",
                preserve_leading_newline=True,
                kind="tool_call",
            )
        self._was_tool_call_delta = False

    def _handle_run_result(self, event: "AgentStreamEvent"):
        usage = event.result.usage
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
        self._fprint(
            f"{self._event_prefix}{usage_msg}\n",
            preserve_leading_newline=True,
            kind="usage",
        )
        self._was_tool_call_delta = False


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
    return StreamEventHandler(
        print_fn=print_fn,
        indent_level=indent_level,
        show_tool_call_detail=show_tool_call_detail,
        show_tool_result=show_tool_result,
    )


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
