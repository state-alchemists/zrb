import time
from typing import TYPE_CHECKING, Any, Callable, Literal

from zrb.llm.tool_call.args import parse_tool_args_value
from zrb.llm.util.tool_args import (
    is_empty_tool_args,
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

# Minimum seconds between "Prepare tool parameters" spinner repaints. The
# spinner is cosmetic; a slow model streaming thousands of tool-arg deltas would
# otherwise flood stdout (observed: 9k+ frames / 500KB) and the per-frame write
# syscalls add real latency to high-tool-call turns. Repaint at most ~10x/sec.
_PROGRESS_REPAINT_INTERVAL = 0.1


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
    ):
        self._print_fn = print_fn
        self._usage_callback = usage_callback
        self._indentation = indent_level * 2 * " "
        self._show_tool_call_detail = show_tool_call_detail
        self._show_tool_result = show_tool_result
        self._tool_block_recorder = tool_block_recorder
        self._on_thinking_start = on_thinking_start
        self._on_thinking_collapse = on_thinking_collapse
        self._on_text_start = on_text_start
        self._on_text_collapse = on_text_collapse
        self._on_tool_prepare_update = on_tool_prepare_update

        self._progress_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._progress_idx = 0
        self._last_progress_time = 0.0
        self._was_tool_call_delta = False
        self._was_tool_call_start = False
        # Same value `__call__` resets this to after every event — a fresh
        # handler always starts mid-turn (the tool-execution loop in
        # runner.py builds a new one on every `while True:` iteration, e.g.
        # once per tool-approval round-trip), never at a true blank buffer,
        # so there is no first-print case that should skip the separator.
        # Starting at the bare `self._indentation` (no leading "\n") made a
        # fresh handler's first line land with no blank line before it while
        # every later line in the same handler got one — the exact
        # inconsistency this line fixes.
        self._event_prefix = f"\n{self._indentation}"
        self._printed_tool_ids = set()
        self._thinking_open = False
        self._thinking_open_prefix = ""
        self._thinking_full_chunks: list[str] = []
        self._text_open = False
        self._text_open_prefix = ""
        self._text_full_chunks: list[str] = []
        # Maps a streamed part's `.index` to the `tool_call_id` it belongs
        # to (known from the part itself at `PartStartEvent` time; later
        # `PartDeltaEvent`s only carry `.index`) and each tool call's own
        # `_event_prefix` at the moment its placeholder opened — both scoped
        # to `on_tool_prepare_update`'s offset-based path (see
        # `_update_tool_prepare`). Never populated when that hook is unset,
        # so the fallback `\r`-based path below never touches them.
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
        """Print a line that may later be expanded, when a recorder is wired.

        Falls back to printing exactly `collapsed` via `fprint` when no
        recorder is set (every UI backend other than the default TUI) or the
        two variants are identical — byte-for-byte today's behavior.
        """
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

    def _open_thinking_block(self) -> None:
        if self._on_thinking_start is not None:
            self._on_thinking_start()
        self._thinking_open = True
        self._thinking_open_prefix = self._event_prefix
        self._thinking_full_chunks = []

    def _stream_thinking_content(
        self, raw: str, preserve_leading_newline: bool
    ) -> None:
        """Format, accumulate, and print one chunk of live thinking text.

        Accumulating here (not re-reading the buffer later) is deliberate:
        `append_to_output`'s carriage-return handling can rewrite/erase part
        of the *rendered* line whenever a chunk contains `\\r` — a mechanism
        built for progress spinners, but it applies to any text. Re-deriving
        "the full thinking text" from the buffer after the fact would inherit
        that erasure; keeping our own copy of exactly what was sent to
        print_fn does not.
        """
        formatted = self._format_content(raw, preserve_leading_newline)
        if self._on_thinking_collapse is not None:
            self._thinking_full_chunks.append(formatted)
        self._print_fn(formatted, "thinking")

    def _close_thinking_block(self) -> None:
        """Collapse the just-finished thinking block, if one was open.

        Called whenever a new part starts (a new thinking part, a tool call,
        or the final text response) — any of those means the previous
        thinking, if any, is done streaming.
        """
        if not self._thinking_open:
            return
        self._thinking_open = False
        chunks, self._thinking_full_chunks = self._thinking_full_chunks, []
        if self._on_thinking_collapse is None:
            return
        full = "".join(chunks)
        # Visible char count on the collapsed line itself: some providers
        # (e.g. OpenAI reasoning models without `openai_reasoning_summary`
        # set) return no human-readable reasoning text at all — only an
        # opaque signature — so there's nothing to expand into. The count
        # makes that visible at a glance instead of looking like a bug.
        char_count = len(full.strip())
        # No trailing "\n" here — whatever prints next already opens with its
        # own "\n{indentation}" (see `_event_prefix`'s reset in `__call__`),
        # so baking one into the label too would print a blank line after
        # every single collapse.
        label = (
            f"🧠 Thought ({char_count} chars)" if char_count else "🧠 Thought (empty)"
        )
        collapsed = self._format_content(
            f"{self._thinking_open_prefix}{label}", preserve_leading_newline=True
        )
        self._on_thinking_collapse(collapsed, full)

    def _open_text_block(self) -> None:
        if self._on_text_start is not None:
            self._on_text_start()
        self._text_open = True
        self._text_open_prefix = self._event_prefix
        self._text_full_chunks = []

    def _stream_text_content(self, raw: str, preserve_leading_newline: bool) -> None:
        """Format, accumulate, and print one chunk of the live final-text
        response. Mirrors `_stream_thinking_content` for the same reason:
        accumulating here (not re-reading the buffer later) survives a stray
        `\\r` in a chunk, which `append_to_output`'s carriage-return handling
        would otherwise rewrite/erase from the *rendered* line."""
        formatted = self._format_content(raw, preserve_leading_newline)
        if self._on_text_collapse is not None:
            self._text_full_chunks.append(formatted)
        self._print_fn(formatted, "streaming")

    def _close_text_block(self) -> None:
        """Collapse the just-finished final-text block, if one was open.

        Mirrors `_close_thinking_block` for the assistant's own reply
        instead of its reasoning. Called whenever a new part starts (a tool
        call or a thinking part) and when the run ends — either means the
        text streamed so far is done. `BaseUI.stream_ai_response` appends a
        markdown-rendered copy of the same text separately afterward; this
        only collapses the raw streamed copy so the two don't both sit on
        screen at once.
        """
        if not self._text_open:
            return
        self._text_open = False
        chunks, self._text_full_chunks = self._text_full_chunks, []
        if self._on_text_collapse is None:
            return
        full = "".join(chunks)
        char_count = len(full.strip())
        # No trailing "\n" — see the matching note in `_close_thinking_block`.
        label = (
            f"💬 Response ({char_count} chars)" if char_count else "💬 Response (empty)"
        )
        collapsed = self._format_content(
            f"{self._text_open_prefix}{label}", preserve_leading_newline=True
        )
        self._on_text_collapse(collapsed, full)

    def _update_tool_prepare(self, tool_call_id: str, text: str) -> None:
        """Print/replace `tool_call_id`'s own "Prepare tool parameters" line.

        Only called when `on_tool_prepare_update` is set. Reconstructs the
        full line (this tool call's own `_event_prefix`, captured when its
        placeholder first opened, plus `text`) and hands it to the UI's
        offset-tracked replace, so a later call for the same `tool_call_id`
        updates exactly that tool's own span — never "whichever line happens
        to be last," which is what the old `\\r`-based erase relied on and
        what broke the instant two tool calls' argument streams interleaved
        (each one's spinner tick could erase the *other's* line).
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

        # A part boundary means "the previous part is done" — EXCEPT when the
        # new part is itself another thinking part. Some providers (OpenAI's
        # reasoning models, via multiple summary_index chunks) stream one
        # logical thought as several separate ThinkingPart/PartStartEvents
        # rather than deltas of one part; closing on every one of those would
        # collapse each fragment into its own near-empty "🧠 Thought" line
        # instead of one block holding the whole thought.
        if isinstance(event.part, (ToolCallPart, TextPart)):
            self._close_thinking_block()
        # Same rationale, the other direction: a tool call or a new thinking
        # part means the streamed final-text response (if one was open) is
        # done. A new TextPart itself does not close it — see the merge note
        # on the thinking side, which applies here too if a provider ever
        # splits one text response across several PartStartEvents.
        if not isinstance(event.part, TextPart):
            self._close_text_block()

        if isinstance(event.part, ToolCallPart):
            # Show a static indicator so the user sees something while parameters
            # are being prepared.  Providers that stream deltas (OpenAI, Anthropic)
            # will overwrite this line with the animated spinner on the first
            # ToolCallPartDelta.  Providers that don't stream (e.g. Ollama) will
            # leave this line as-is, and the 🧰 line will appear below it.

            if not self._show_tool_call_detail:
                if self._on_tool_prepare_update is not None:
                    # Offset-tracked path: remember which tool call `.index`
                    # belongs to (deltas only carry `.index`) and the prefix
                    # in effect right now, then print the placeholder into
                    # this tool call's own span.
                    tool_call_id = event.part.tool_call_id
                    self._tool_prepare_index_map[event.index] = tool_call_id
                    self._tool_prepare_prefix[tool_call_id] = self._event_prefix
                    self._update_tool_prepare(
                        tool_call_id, "🔄 Prepare tool parameters..."
                    )
                else:
                    # Fallback for a UI that hasn't opted in: unchanged from
                    # before — a single `\r`-animated line, correct only when
                    # tool calls don't overlap.
                    self.fprint(
                        f"{self._event_prefix}🔄 Prepare tool parameters...",
                        preserve_leading_newline=True,
                        kind="progress",
                    )
                self._was_tool_call_start = True
            return True

        if isinstance(event.part, TextPart):
            content = get_event_part_content(event)
            # Mirrors the 🧠 lead-in below: marked once, on the block's first
            # chunk, so the icon survives into `full` — an expanded response
            # (Ctrl+O) keeps its 💬, not just the collapsed summary line.
            if not self._text_open:
                self._open_text_block()
                marker = "💬 "
            else:
                marker = ""
            if content or marker:
                self._stream_text_content(
                    f"{self._event_prefix}{marker}{content}",
                    preserve_leading_newline=True,
                )
        else:
            content = get_event_part_content(event)
            # Only mark and print the 🧠 lead-in for the FIRST part of a
            # thinking streak — a later summary chunk (see the comment above)
            # continues the same open block instead of restarting it.
            if not self._thinking_open:
                self._open_thinking_block()
                marker = "🧠 "
            else:
                marker = ""
            self._stream_thinking_content(
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
            # content_delta or "" mirrors the ThinkingPartDelta guard below —
            # not currently known to be None for text, but f"{None}" would
            # print the literal word "None" if a provider ever did.
            self._stream_text_content(
                event.delta.content_delta or "", preserve_leading_newline=False
            )
            self._was_tool_call_delta = False
            self._was_tool_call_start = False
        elif isinstance(event.delta, ThinkingPartDelta):
            # content_delta can be None for providers that deliver thinking
            # text out-of-band (via provider_details rather than the delta
            # itself) — f"{None}" would print the literal word "None".
            self._stream_thinking_content(
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
                    # Offset-tracked path: throttled the same as the fallback
                    # below, but replaces exactly *this* tool call's own
                    # span — never "whichever line is currently last."
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
                # Fallback for a UI that hasn't opted in: unchanged from
                # before — single-line `\r` animation, correct only when
                # tool calls don't overlap.
                if not self._was_tool_call_delta and not self._was_tool_call_start:
                    self.fprint("\n", kind="progress")
                # Set state before the throttle check so the carriage-return
                # cleanup in handle_tool_call still fires even on a throttled
                # delta.
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
        if self._on_tool_prepare_update is not None:
            # Erase exactly this tool call's own placeholder/spinner span —
            # offset-based, so whatever else printed in between (another
            # tool call's own placeholder, its own spinner ticks) is
            # untouched.
            self._update_tool_prepare(tool_call_id, "")
            self._tool_prepare_prefix.pop(tool_call_id, None)
        elif self._was_tool_call_delta and not self._show_tool_call_detail:
            self._print_fn("\r", "progress")

        tool_name = event.part.tool_name
        if tool_call_id not in self._printed_tool_ids:
            self._printed_tool_ids.add(tool_call_id)
            # AskUserQuestion renders its (large) question/options payload in the
            # interactive selection widget; echoing the raw args here is just noise.
            # No trailing "\n" on any of these — every direct writer outside this
            # handler (web.py's `_notify`, the approval-response handlers, ...)
            # now supplies its own leading "\n{indentation}", matching what
            # `_event_prefix` gives every event-driven print here. That makes
            # the separator uniformly "whoever prints next supplies exactly one
            # leading newline" — see the note on `_close_thinking_block`'s label.
            if tool_name == "AskUserQuestion":
                line = f"{self._event_prefix}🧰 {tool_call_id} | {tool_name}"
                self.fprint(line, preserve_leading_newline=True, kind="tool_call")
            else:
                args = get_truncated_event_part_args(event)
                full_args = get_full_event_part_args(event)
                collapsed = (
                    f"{self._event_prefix}🧰 {tool_call_id} | {tool_name} {args}"
                )
                full = (
                    f"{self._event_prefix}🧰 {tool_call_id} | {tool_name} {full_args}"
                )
                self._print_toggle_line(collapsed, full, preserve_leading_newline=True)
        self._was_tool_call_delta = False

    def handle_tool_result(self, event: "ToolResultEvent"):
        # No trailing "\n" — see the note in `handle_tool_call`.
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
        self._close_thinking_block()
        # The normal case: a turn ends with the final text as the last
        # streamed part, so this is where most text blocks actually collapse.
        self._close_text_block()
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
        # No trailing "\n" — see the note in `handle_tool_call`. This is the
        # last thing `StreamEventHandler` prints for the turn; what follows
        # (`BaseUI.stream_ai_response`'s own explicit blank line before the
        # rendered final answer) supplies its own separation already —
        # keeping this one too doubled that gap to two blank lines.
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
):
    """Create an event handler for agent stream events.

    Args:
        print_fn: Function to print output. Called as print_fn(text, kind) where
                  kind is one of "text", "progress", "tool_call", "usage", "thinking".
        indent_level: Indentation level for nested output.
        show_tool_call_detail: Whether to show detailed tool call parameters.
        show_tool_result: Whether to show tool result content.
        usage_callback: Called with the run's `RunUsage` when the run completes.
        tool_block_recorder: Called with (collapsed, full) instead of
            printing a collapsed-by-default tool-call/result line directly,
            so a UI that supports it can make the line expandable. UIs that
            don't support toggling leave this unset and get the identical
            collapsed-only line as before.
        on_thinking_start: Called right before the first chunk of a thinking
            block is printed, so a UI that supports it can note where the
            block begins. Thinking always streams live either way.
        on_thinking_collapse: Called with (collapsed, full) once a thinking
            block ends (the model moved on to a tool call or its final
            response) — `collapsed` is a pre-formatted placeholder line,
            `full` is every chunk actually sent to print_fn for that block
            (accumulated here, not re-read from the rendered buffer, since a
            stray carriage return in a chunk can rewrite/erase part of the
            live-rendered line — see `_stream_thinking_content`). A UI that
            supports it replaces the already-printed live text with
            `collapsed` and keeps `full` for later expansion.
        on_text_start: Called right before the first chunk of the final text
            response is printed. Mirrors `on_thinking_start` for the
            assistant's reply instead of its reasoning.
        on_text_collapse: Called with (collapsed, full) once the final text
            response is done streaming (a tool call or a new thinking part
            started, or the run ended) — same contract as
            `on_thinking_collapse`. The caller's own markdown-rendered copy
            of the same text (e.g. `BaseUI.stream_ai_response`) is appended
            separately afterward; this only collapses the raw streamed copy
            so both don't sit on screen at once.
        on_tool_prepare_update: Called with (tool_call_id, text) to print or
            replace that tool call's own "Prepare tool parameters" line —
            first call for a `tool_call_id` prints fresh, later calls (each
            argument delta's spinner tick, and the empty-string erase once
            the tool call resolves) replace exactly that line in place. Keyed
            per tool call so concurrent (parallel) tool calls' argument
            streams never corrupt each other's line — the previous `\\r`-
            "erase whatever is currently the last line" approach did exactly
            that under interleaving. A UI that doesn't support it keeps the
            original single-line `\\r` animation, correct only when tool
            calls don't overlap.
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
    )


def _last_request_usage(result: Any) -> Any:
    """The last `ModelResponse`'s per-request usage = current context size.

    `RunUsage` sums every request in the run, so it can't report window
    occupancy. Only `ModelResponse` carries `.usage`; the last one is the most
    recent prompt sent, which is what fills the context window.
    """
    for message in reversed(result.all_messages()):
        usage = getattr(message, "usage", None)
        if usage is not None:
            return usage
    return None


def get_truncated_event_part_args(event: "AgentStreamEvent | ToolCallEvent") -> Any:
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
        return truncate_tool_args_values(parsed)
    return args


def get_full_event_part_args(event: "AgentStreamEvent | ToolCallEvent") -> Any:
    """Same as `get_truncated_event_part_args`, but with untruncated values.

    `event.part.args` is never mutated by parsing/truncation, so this is
    just the same lookup with `full=True`.
    """
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
        return truncate_tool_args_values(parsed, full=True)
    return args


def get_event_part_content(event: "AgentStreamEvent") -> str:
    if not hasattr(event, "part"):
        return ""
    part = getattr(event, "part")
    if hasattr(part, "content"):
        return getattr(part, "content")
    return ""
