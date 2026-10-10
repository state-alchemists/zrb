import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from zrb.llm.tool_call.args import (
    is_empty_tool_args,
    parse_tool_args_value,
    truncate_tool_args_values,
)

if TYPE_CHECKING:
    from zrb.llm.agent.types import (
        AgentRunResultEvent,
        AgentStreamEvent,
        PartDeltaEvent,
        PartStartEvent,
        ToolCallEvent,
        ToolResultEvent,
    )

PrintKind = Literal[
    "text", "streaming", "progress", "tool_call", "usage", "thinking", "todo_progress"
]

# Minimum seconds between "Prepare tool parameters" spinner repaints: thousands
# of tool-arg deltas would otherwise flood stdout and add write latency.
_PROGRESS_REPAINT_INTERVAL = 0.1


class StreamedBlock:
    """One live-streamed, later-collapsed block: the model's thinking or its
    final-text reply. `StreamEventHandler` holds one of each.

    `kind` is the `print_fn` kind of every chunk; `label` heads the collapsed
    placeholder line.
    """

    def __init__(
        self,
        kind: PrintKind,
        label: str,
        on_start: Callable[[], None] | None,
        on_collapse: Callable[[str, str], None] | None,
        format_content: Callable[[str, bool], str],
        print_fn: Callable[[str, str], Any],
    ):
        self._kind: PrintKind = kind
        self._label = label
        self._on_start = on_start
        self._on_collapse = on_collapse
        self._format_content = format_content
        self._print_fn = print_fn
        self._open = False
        self._open_prefix = ""
        self._full_chunks: list[str] = []

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self, prefix: str) -> None:
        """Start a block whose collapsed line will begin with `prefix`."""
        if self._on_start is not None:
            self._on_start()
        self._open = True
        self._open_prefix = prefix
        self._full_chunks = []

    def stream(self, raw: str, preserve_leading_newline: bool) -> None:
        """Format, accumulate, and print one chunk of the block.

        Accumulated here rather than re-read from the rendered buffer, where
        `\\r` handling may have erased part of a line.
        """
        formatted = self._format_content(raw, preserve_leading_newline)
        if self._on_collapse is not None:
            self._full_chunks.append(formatted)
        self._print_fn(formatted, self._kind)

    def close(self) -> None:
        """Collapse the just-finished block, if one was open.

        For the final-text block this collapses only the raw streamed copy;
        `BaseUI.stream_ai_response` appends the rendered one.
        """
        if not self._open:
            return
        self._open = False
        chunks, self._full_chunks = self._full_chunks, []
        if self._on_collapse is None:
            return
        full = "".join(chunks)
        # Some providers return only an opaque reasoning signature; the
        # count shows an empty block as such rather than as a bug.
        char_count = len(full.strip())
        # No trailing "\n": whatever prints next supplies its own leading one.
        label = (
            f"{self._label} ({char_count} chars)"
            if char_count
            else f"{self._label} (empty)"
        )
        collapsed = self._format_content(f"{self._open_prefix}{label}", True)
        self._on_collapse(collapsed, full)


class StreamEventHandler:
    """Stateful handler for agent stream events."""

    def __init__(
        self,
        print_fn: Callable[[str, str], Any],
        indent_level: int = 1,
        show_tool_call_detail: bool = False,
        show_tool_result: bool = False,
        usage_callback: Callable[..., None] | None = None,
        tool_block_recorder: Callable[[str, str], None] | None = None,
        on_thinking_start: Callable[[], None] | None = None,
        on_thinking_collapse: Callable[[str, str], None] | None = None,
        on_text_start: Callable[[], None] | None = None,
        on_text_collapse: Callable[[str, str], None] | None = None,
        on_tool_prepare_update: Callable[[str, str], None] | None = None,
        on_tool_call_start: Callable[[str, str], None] | None = None,
        on_tool_call_end: Callable[[str | None], None] | None = None,
    ):
        self._print_fn = print_fn
        self._usage_callback = usage_callback
        self._indentation = indent_level * 2 * " "
        self._show_tool_call_detail = show_tool_call_detail
        self._show_tool_result = show_tool_result
        self._tool_block_recorder = tool_block_recorder
        self._on_tool_prepare_update = on_tool_prepare_update
        self._on_tool_call_start = on_tool_call_start
        self._on_tool_call_end = on_tool_call_end

        self._progress_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._progress_idx = 0
        self._last_progress_time = 0.0
        self._was_tool_call_delta = False
        self._was_tool_call_start = False
        # A handler is rebuilt on every tool-approval round-trip, so it starts
        # mid-turn and its first line needs the separator too.
        self._event_prefix = f"\n{self._indentation}"
        self._printed_tool_ids = set()
        self._thinking = StreamedBlock(
            "thinking",
            "🧠 Thought",
            on_thinking_start,
            on_thinking_collapse,
            self._format_content,
            print_fn,
        )
        self._text = StreamedBlock(
            "streaming",
            "💬 Response",
            on_text_start,
            on_text_collapse,
            self._format_content,
            print_fn,
        )
        # Part `.index` -> `tool_call_id` (deltas carry only `.index`), and
        # each call's prefix when its placeholder opened.
        self._tool_prepare_index_map: dict[int, str] = {}
        self._tool_prepare_prefix: dict[str, str] = {}

    @property
    def indentation(self) -> str:
        return self._indentation

    @property
    def show_tool_call_detail(self) -> bool:
        return self._show_tool_call_detail

    @property
    def show_tool_result(self) -> bool:
        return self._show_tool_result

    @property
    def progress_idx(self) -> int:
        return self._progress_idx

    @progress_idx.setter
    def progress_idx(self, value: int) -> None:
        self._progress_idx = value

    @property
    def was_tool_call_delta(self) -> bool:
        return self._was_tool_call_delta

    @was_tool_call_delta.setter
    def was_tool_call_delta(self, value: bool) -> None:
        self._was_tool_call_delta = value

    @property
    def was_tool_call_start(self) -> bool:
        return self._was_tool_call_start

    @property
    def event_prefix(self) -> str:
        return self._event_prefix

    @property
    def printed_tool_ids(self) -> set:
        return self._printed_tool_ids

    def _format_content(
        self, content: str, preserve_leading_newline: bool = False
    ) -> str:
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

        return result

    def fprint(
        self,
        content: str,
        preserve_leading_newline: bool = False,
        kind: PrintKind = "text",
    ):
        result = self._format_content(content, preserve_leading_newline)
        return self._print_fn(result, kind)

    def _print_toggle_line(
        self,
        collapsed: str,
        full: str,
        preserve_leading_newline: bool = False,
        kind: PrintKind = "tool_call",
    ):
        """Print a line that may later be expanded, when a recorder is wired;
        otherwise print `collapsed`."""
        if self._tool_block_recorder is not None and collapsed != full:
            formatted_collapsed = self._format_content(
                collapsed, preserve_leading_newline
            )
            formatted_full = self._format_content(full, preserve_leading_newline)
            self._tool_block_recorder(formatted_collapsed, formatted_full)
            return
        self.fprint(
            collapsed, preserve_leading_newline=preserve_leading_newline, kind=kind
        )

    async def __call__(self, event: "AgentStreamEvent"):
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import (
            AgentRunResultEvent,
            FinalResultEvent,
            PartDeltaEvent,
            PartStartEvent,
            ToolCallEvent,
            ToolResultEvent,
        )

        skip_prefix_update = False

        if isinstance(event, PartStartEvent):
            skip_prefix_update = self.handle_part_start(event)
        elif isinstance(event, PartDeltaEvent):
            self.handle_part_delta(event)
        elif isinstance(event, ToolCallEvent):
            self.handle_tool_call(event)
        elif isinstance(event, ToolResultEvent):
            self.handle_tool_result(event)
        elif isinstance(event, AgentRunResultEvent):
            self.handle_run_result(event)
        elif isinstance(event, FinalResultEvent):
            self._was_tool_call_delta = False

        if not skip_prefix_update:
            self._event_prefix = f"\n{self._indentation}"

    def _update_tool_prepare(self, tool_call_id: str, text: str) -> None:
        """Print/replace `tool_call_id`'s own "Prepare tool parameters" line.

        Keyed per tool call so interleaved argument streams of parallel calls
        never overwrite each other's line.
        """
        if self._on_tool_prepare_update is None:
            return
        prefix = self._tool_prepare_prefix.get(tool_call_id, self._event_prefix)
        formatted = self._format_content(
            f"{prefix}{text}" if text else "", preserve_leading_newline=bool(text)
        )
        self._on_tool_prepare_update(tool_call_id, formatted)

    def handle_part_start(self, event: "PartStartEvent") -> bool:
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import TextPart, ToolCallPart

        # A part boundary closes the previous part, except thinking-after-
        # thinking: some providers stream one thought as several ThinkingParts,
        # which should collapse into one block.
        if isinstance(event.part, (ToolCallPart, TextPart)):
            self._thinking.close()
        # Likewise a non-text part closes an open text response; a new
        # TextPart merges into it.
        if not isinstance(event.part, TextPart):
            self._text.close()

        if isinstance(event.part, ToolCallPart):
            # Static placeholder; streaming providers overwrite it with the
            # spinner on the first ToolCallPartDelta, others leave it as-is.
            if not self._show_tool_call_detail:
                if self._on_tool_prepare_update is not None:
                    tool_call_id = event.part.tool_call_id
                    self._tool_prepare_index_map[event.index] = tool_call_id
                    self._tool_prepare_prefix[tool_call_id] = self._event_prefix
                    self._update_tool_prepare(
                        tool_call_id, "🔄 Prepare tool parameters..."
                    )
                else:
                    # A `\r`-animated line; correct only for non-overlapping calls.
                    self.fprint(
                        f"{self._event_prefix}🔄 Prepare tool parameters...",
                        preserve_leading_newline=True,
                        kind="progress",
                    )
                self._was_tool_call_start = True
            return True

        if isinstance(event.part, TextPart):
            content = get_event_part_content(event)
            # Marked on the first chunk so the icon survives into `full`.
            if not self._text.is_open:
                self._text.open(self._event_prefix)
                marker = "💬 "
            else:
                marker = ""
            if content or marker:
                self._text.stream(
                    f"{self._event_prefix}{marker}{content}",
                    preserve_leading_newline=True,
                )
        else:
            content = get_event_part_content(event)
            # Only the first part of a thinking streak gets the 🧠 lead-in.
            if not self._thinking.is_open:
                self._thinking.open(self._event_prefix)
                marker = "🧠 "
            else:
                marker = ""
            self._thinking.stream(
                f"{self._event_prefix}{marker}{content}", preserve_leading_newline=True
            )
        self._was_tool_call_delta = False
        self._was_tool_call_start = False
        return False

    def handle_part_delta(self, event: "PartDeltaEvent"):
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import (
            TextPartDelta,
            ThinkingPartDelta,
            ToolCallPartDelta,
        )

        if isinstance(event.delta, TextPartDelta):
            self._text.stream(
                event.delta.content_delta or "", preserve_leading_newline=False
            )
            self._was_tool_call_delta = False
            self._was_tool_call_start = False
        elif isinstance(event.delta, ThinkingPartDelta):
            # None when a provider delivers thinking via provider_details.
            self._thinking.stream(
                event.delta.content_delta or "", preserve_leading_newline=False
            )
            self._was_tool_call_delta = False
            self._was_tool_call_start = False
        elif isinstance(event.delta, ToolCallPartDelta):
            if self._show_tool_call_detail:
                self.fprint(f"{event.delta.args_delta}", kind="tool_call")
                self._was_tool_call_delta = True
                self._was_tool_call_start = False
            else:
                tool_call_id = self._tool_prepare_index_map.get(event.index)
                if (
                    tool_call_id is not None
                    and self._on_tool_prepare_update is not None
                ):
                    now = time.monotonic()
                    if now - self._last_progress_time < _PROGRESS_REPAINT_INTERVAL:
                        return
                    self._last_progress_time = now
                    progress_char = self._progress_chars[self._progress_idx]
                    self._progress_idx = (self._progress_idx + 1) % len(
                        self._progress_chars
                    )
                    self._update_tool_prepare(
                        tool_call_id, f"🔄 Prepare tool parameters {progress_char}"
                    )
                    return
                if not self._was_tool_call_delta and not self._was_tool_call_start:
                    self.fprint("\n", kind="progress")
                # Set before the throttle so handle_tool_call's `\r` cleanup
                # still fires after a throttled delta.
                self._was_tool_call_delta = True
                self._was_tool_call_start = False
                now = time.monotonic()
                if now - self._last_progress_time < _PROGRESS_REPAINT_INTERVAL:
                    return
                self._last_progress_time = now
                progress_char = self._progress_chars[self._progress_idx]
                self._print_fn(
                    f"\r{self._indentation}🔄 Prepare tool parameters {progress_char}",
                    "progress",
                )
                self._progress_idx = (self._progress_idx + 1) % len(
                    self._progress_chars
                )

    def handle_tool_call(self, event: "ToolCallEvent"):
        tool_call_id = event.part.tool_call_id
        if self._on_tool_call_start is not None:
            self._on_tool_call_start(event.part.tool_name, tool_call_id)
        if self._on_tool_prepare_update is not None:
            self._update_tool_prepare(tool_call_id, "")
            self._tool_prepare_prefix.pop(tool_call_id, None)
        elif self._was_tool_call_delta and not self._show_tool_call_detail:
            self._print_fn("\r", "progress")

        tool_name = event.part.tool_name
        if tool_call_id not in self._printed_tool_ids:
            self._printed_tool_ids.add(tool_call_id)
            # AskUserQuestion's args are rendered by the selection widget.
            # No trailing "\n": whatever prints next supplies its own.
            if tool_name == "AskUserQuestion":
                line = f"{self._event_prefix}🧰 {tool_call_id} | {tool_name}"
                self.fprint(line, preserve_leading_newline=True, kind="tool_call")
            else:
                args = get_event_part_args(event)
                full_args = get_event_part_args(event, full=True)
                collapsed = (
                    f"{self._event_prefix}🧰 {tool_call_id} | {tool_name} {args}"
                )
                full = (
                    f"{self._event_prefix}🧰 {tool_call_id} | {tool_name} {full_args}"
                )
                self._print_toggle_line(collapsed, full, preserve_leading_newline=True)
        self._was_tool_call_delta = False

    def handle_tool_result(self, event: "ToolResultEvent"):
        if self._on_tool_call_end is not None:
            self._on_tool_call_end(event.tool_call_id)
        if self._show_tool_result:
            self.fprint(
                f"{self._event_prefix}🔠 {event.tool_call_id} | Return {event.part.content}",
                preserve_leading_newline=True,
                kind="tool_call",
            )
        else:
            collapsed = f"{self._event_prefix}🔠 {event.tool_call_id} Executed"
            full = (
                f"{self._event_prefix}🔠 {event.tool_call_id} | "
                f"Return {event.part.content}"
            )
            self._print_toggle_line(collapsed, full, preserve_leading_newline=True)
        self._was_tool_call_delta = False

    def handle_run_result(self, event: "AgentRunResultEvent"):
        # Clear any tool that never got a result event.
        if self._on_tool_call_end is not None:
            self._on_tool_call_end(None)
        self._thinking.close()
        self._text.close()
        usage = event.result.usage
        if self._usage_callback is not None:
            self._usage_callback(usage, _last_request_usage(event.result))
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
        self.fprint(
            f"{self._event_prefix}{usage_msg}",
            preserve_leading_newline=True,
            kind="usage",
        )
        self._was_tool_call_delta = False


def create_event_handler(
    print_fn: Callable[[str, str], Any],
    indent_level: int = 1,
    show_tool_call_detail: bool = False,
    show_tool_result: bool = False,
    usage_callback: Callable[..., None] | None = None,
    tool_block_recorder: Callable[[str, str], None] | None = None,
    on_thinking_start: Callable[[], None] | None = None,
    on_thinking_collapse: Callable[[str, str], None] | None = None,
    on_text_start: Callable[[], None] | None = None,
    on_text_collapse: Callable[[str, str], None] | None = None,
    on_tool_prepare_update: Callable[[str, str], None] | None = None,
    on_tool_call_start: Callable[[str, str], None] | None = None,
    on_tool_call_end: Callable[[str | None], None] | None = None,
):
    """Create an event handler for agent stream events.

    Args:
        print_fn: Function to print output. Called as print_fn(text, kind) where
                  kind is one of "text", "progress", "tool_call", "usage", "thinking".
        indent_level: Indentation level for nested output.
        show_tool_call_detail: Whether to show detailed tool call parameters.
        show_tool_result: Whether to show tool result content.
        usage_callback: Called with the run's `RunUsage` when the run completes.
        tool_block_recorder: Called with (collapsed, full) instead of printing
            a tool-call/result line, so the UI can make it expandable.
        on_thinking_start: Called before a thinking block's first chunk.
        on_thinking_collapse: Called with (collapsed, full) when a thinking
            block ends; `full` is every chunk sent to print_fn for it.
        on_text_start: Called before the final text response's first chunk.
        on_text_collapse: Called with (collapsed, full) when the final text
            response ends; same contract as `on_thinking_collapse`.
        on_tool_prepare_update: Called with (tool_call_id, text) to print or
            replace that call's own "Prepare tool parameters" line (empty
            text erases it). Without it, a single `\\r`-animated line is used,
            correct only when tool calls don't overlap.
        on_tool_call_start: Called with (tool_name, tool_call_id) when a tool
            call is about to execute.
        on_tool_call_end: Called with the finished call's id, and with
            ``None`` (clear whatever is running) when the run ends.
    """
    return StreamEventHandler(
        print_fn=print_fn,
        indent_level=indent_level,
        show_tool_call_detail=show_tool_call_detail,
        show_tool_result=show_tool_result,
        usage_callback=usage_callback,
        tool_block_recorder=tool_block_recorder,
        on_thinking_start=on_thinking_start,
        on_thinking_collapse=on_thinking_collapse,
        on_text_start=on_text_start,
        on_text_collapse=on_text_collapse,
        on_tool_prepare_update=on_tool_prepare_update,
        on_tool_call_start=on_tool_call_start,
        on_tool_call_end=on_tool_call_end,
    )


def _last_request_usage(result: Any) -> Any:
    """The last `ModelResponse`'s per-request usage = current context size.

    `RunUsage` sums the whole run, so it cannot report window occupancy.
    """
    for message in reversed(result.all_messages()):
        usage = getattr(message, "usage", None)
        if usage is not None:
            return usage
    return None


def get_event_part_args(
    event: "AgentStreamEvent | ToolCallEvent", full: bool = False
) -> Any:
    """The event part's tool-call args, values truncated unless `full`."""
    if not hasattr(event, "part"):
        return {}
    part = getattr(event, "part")
    if not hasattr(part, "args"):
        return {}
    args = getattr(part, "args")
    if is_empty_tool_args(args):
        return {}
    parsed = parse_tool_args_value(args)
    if parsed is not None:
        return truncate_tool_args_values(parsed, full=full)
    return args


def get_event_part_content(event: "AgentStreamEvent") -> str:
    if not hasattr(event, "part"):
        return ""
    part = getattr(event, "part")
    if hasattr(part, "content"):
        return getattr(part, "content")
    return ""
