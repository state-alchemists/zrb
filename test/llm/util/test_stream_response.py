from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.util.stream_response import (
    StreamEventHandler,
    create_event_handler,
    get_event_part_content,
    get_full_event_part_args,
    get_truncated_event_part_args,
)


class TestStreamEventHandlerInit:
    def test_init_default_values(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        assert handler.indentation == "  "
        assert handler.show_tool_call_detail is False
        assert handler.show_tool_result is False
        assert handler.progress_idx == 0
        assert handler.was_tool_call_delta is False
        assert handler.was_tool_call_start is False
        # Same value `__call__` resets to after every event — a fresh handler
        # always starts mid-turn (see the field's own comment), never at a
        # true blank buffer.
        assert handler.event_prefix == "\n  "
        assert handler.printed_tool_ids == set()

    def test_fresh_handler_first_print_has_a_leading_newline(self):
        """Regression: the tool-execution loop (runner.py) builds a brand new
        `StreamEventHandler` on every re-entry (e.g. once per tool-approval
        round-trip), never at a genuinely blank buffer. Without a leading
        newline on the very first thing it prints, that first line landed
        with no separation from whatever the *previous* handler had already
        printed, while every later line in the same handler got one."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.handle_tool_call(mock_event)
        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert printed.startswith("\n")

    def test_init_custom_values(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            indent_level=3,
            show_tool_call_detail=True,
            show_tool_result=True,
        )
        assert handler.indentation == "      "
        assert handler.show_tool_call_detail is True
        assert handler.show_tool_result is True


class TestStreamEventHandlerFprint:
    def test_fprint_simple_text(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler.fprint("Hello", kind="text")
        print_fn.assert_called_once_with("Hello", "text")

    def test_fprint_with_trailing_newline(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler.fprint("Hello\n", kind="text")
        print_fn.assert_called_once_with("Hello\n", "text")

    def test_fprint_preserve_leading_newline(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler.fprint("\nHello", preserve_leading_newline=True, kind="text")
        print_fn.assert_called_once_with("\nHello", "text")

    def test_fprint_multiline_indent(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler.fprint("Line1\nLine2", kind="text")
        print_fn.assert_called_once()
        args = print_fn.call_args[0]
        assert "Line1\n     Line2" in args[0]


class TestStreamEventHandlerPartStart:
    def test_handle_part_start_tool_call_no_detail(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        mock_event = MagicMock()
        mock_event.part = MagicMock()
        mock_event.part.__class__.__name__ = "ToolCallPart"
        from pydantic_ai import ToolCallPart

        mock_event.part = ToolCallPart(tool_name="test", args={}, tool_call_id="1")
        result = handler.handle_part_start(mock_event)
        assert result is True
        assert handler.was_tool_call_start is True

    def test_handle_part_start_text_part(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai.messages import TextPart

        mock_event = MagicMock()
        mock_event.part = TextPart(content="Hello world")
        result = handler.handle_part_start(mock_event)
        assert result is False
        print_fn.assert_called()

    def test_handle_part_start_thinking_part(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai.messages import ThinkingPart

        mock_event = MagicMock()
        mock_event.part = ThinkingPart(content="Let me think...")
        result = handler.handle_part_start(mock_event)
        assert result is False
        print_fn.assert_called()


class TestStreamEventHandlerPartDelta:
    def test_handle_part_delta_text(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import TextPartDelta

        mock_event = MagicMock()
        mock_event.delta = TextPartDelta(content_delta="Hello")
        handler.handle_part_delta(mock_event)
        print_fn.assert_called()
        assert handler.was_tool_call_delta is False
        assert handler.was_tool_call_start is False

    def test_handle_part_delta_thinking(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ThinkingPartDelta

        mock_event = MagicMock()
        mock_event.delta = ThinkingPartDelta(content_delta="Thinking...")
        handler.handle_part_delta(mock_event)
        print_fn.assert_called()

    def test_handle_part_delta_tool_call_with_detail(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=True)
        from pydantic_ai import ToolCallPartDelta

        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler.handle_part_delta(mock_event)
        print_fn.assert_called()
        assert handler.was_tool_call_delta is True

    def test_handle_part_delta_tool_call_without_detail(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler.handle_part_delta(mock_event)
        assert handler.was_tool_call_delta is True
        assert handler.progress_idx == 1

    def test_handle_part_delta_tool_call_progress_wraparound(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        handler.progress_idx = 9
        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler.handle_part_delta(mock_event)
        assert handler.progress_idx == 0


class TestStreamEventHandlerThinkingCollapse:
    def test_consecutive_thinking_parts_merge_into_one_block(self):
        """Regression: OpenAI reasoning models stream a single thought as
        several separate ThinkingPart/PartStartEvents (one per summary_index)
        rather than deltas of one part. Closing on every PartStartEvent
        collapsed each fragment into its own near-empty block instead of one
        block holding the whole thought — this is that bug, pinned."""
        print_fn = MagicMock()
        on_start = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            on_thinking_start=on_start,
            on_thinking_collapse=on_collapse,
        )
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import ThinkingPart

        first = MagicMock()
        first.part = ThinkingPart(content="First paragraph of reasoning.")
        handler.handle_part_start(first)

        second = MagicMock()
        second.part = ThinkingPart(content="Second paragraph of reasoning.")
        handler.handle_part_start(second)

        third = MagicMock()
        third.part = ThinkingPart(content="Third paragraph of reasoning.")
        handler.handle_part_start(third)

        # Only one open/close pair across the whole streak — not one per part.
        on_start.assert_called_once_with()
        on_collapse.assert_not_called()

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_called_once()
        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert "First paragraph" in printed
        assert "Second paragraph" in printed
        assert "Third paragraph" in printed
        # Only the first chunk gets the 🧠 lead-in; later chunks continue it.
        assert printed.count("🧠") == 1

        # The accumulated "full" text handed to the collapse hook must also
        # hold all three paragraphs — this is what a later expand shows.
        _collapsed, full = on_collapse.call_args[0]
        assert "First paragraph" in full
        assert "Second paragraph" in full
        assert "Third paragraph" in full

    def test_thinking_part_opens_block_when_hook_set(self):
        print_fn = MagicMock()
        on_start = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_thinking_start=on_start)
        from pydantic_ai.messages import ThinkingPart

        mock_event = MagicMock()
        mock_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(mock_event)

        on_start.assert_called_once_with()
        print_fn.assert_called()  # thinking still streams live either way

    def test_tool_call_after_thinking_closes_and_collapses_it(self):
        print_fn = MagicMock()
        on_start = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            on_thinking_start=on_start,
            on_thinking_collapse=on_collapse,
        )
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import ThinkingPart

        thinking_event = MagicMock()
        thinking_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(thinking_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_called_once()
        collapsed_text, full_text = on_collapse.call_args[0]
        assert "🧠 Thought" in collapsed_text
        assert "Let me think..." in full_text

    def test_none_content_delta_does_not_print_literal_none(self):
        """Some providers deliver thinking text out-of-band (provider_details
        rather than content_delta, e.g. gpt-oss raw CoT), leaving
        content_delta as None. f"{None}" would print the literal word "None"
        into the transcript — must not."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ThinkingPartDelta

        mock_event = MagicMock()
        mock_event.delta = ThinkingPartDelta(content_delta=None)
        handler.handle_part_delta(mock_event)  # must not raise

        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert "None" not in printed

    def test_carriage_return_in_a_delta_does_not_truncate_the_full_text(self):
        """Regression: `append_to_output`'s `\\r` handling (built for progress
        spinners) rewrites/erases part of the *rendered* line whenever a
        chunk contains `\\r`. A naive "read back what's on screen" full-text
        reconstruction would inherit that erasure and silently lose most of
        the thought. Accumulating chunks at the source (here) must not."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_thinking_collapse=on_collapse
        )
        from pydantic_ai import ThinkingPartDelta, ToolCallPart
        from pydantic_ai.messages import ThinkingPart

        start_event = MagicMock()
        start_event.part = ThinkingPart(content="Reasoning about the problem")
        handler.handle_part_start(start_event)

        # A stray \r inside a later delta — plausible raw-token noise from a
        # reasoning stream, and exactly what append_to_output's spinner
        # handling would otherwise erase back-to-line-start for.
        delta_event = MagicMock()
        delta_event.delta = ThinkingPartDelta(
            content_delta="\rmore reasoning after a stray CR"
        )
        handler.handle_part_delta(delta_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_called_once()
        _collapsed, full = on_collapse.call_args[0]
        assert "Reasoning about the problem" in full
        assert "more reasoning after a stray CR" in full

    def test_text_part_after_thinking_closes_and_collapses_it(self):
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_thinking_collapse=on_collapse
        )
        from pydantic_ai.messages import TextPart, ThinkingPart

        thinking_event = MagicMock()
        thinking_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(thinking_event)

        text_event = MagicMock()
        text_event.part = TextPart(content="Here's the answer")
        handler.handle_part_start(text_event)

        on_collapse.assert_called_once()

    def test_no_open_thinking_block_never_calls_collapse(self):
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_thinking_collapse=on_collapse
        )
        from pydantic_ai import ToolCallPart

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_not_called()

    def test_run_result_closes_a_still_open_thinking_block(self):
        """Edge case: the run ends with thinking as the last streamed part
        (no subsequent tool call or text)."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_thinking_collapse=on_collapse
        )
        from pydantic_ai.messages import ThinkingPart

        thinking_event = MagicMock()
        thinking_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(thinking_event)

        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

        on_collapse.assert_called_once()

    def test_without_hooks_thinking_still_streams_and_nothing_raises(self):
        """Regression guard: a UI that never opts in (std_ui, Telegram, ...)
        behaves exactly as before — thinking just streams, nothing collapses."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import ThinkingPart

        thinking_event = MagicMock()
        thinking_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(thinking_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)  # must not raise


class TestStreamEventHandlerTextCollapse:
    """Mirrors TestStreamEventHandlerThinkingCollapse: the final text
    response gets the same live-stream-then-collapse treatment as thinking,
    so the "fainted" streamed copy doesn't sit on screen next to the
    markdown-rendered final copy `BaseUI.stream_ai_response` appends."""

    def test_text_part_opens_block_when_hook_set(self):
        print_fn = MagicMock()
        on_start = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_start=on_start)
        from pydantic_ai.messages import TextPart

        mock_event = MagicMock()
        mock_event.part = TextPart(content="Here's the answer")
        handler.handle_part_start(mock_event)

        on_start.assert_called_once_with()
        print_fn.assert_called()  # text still streams live either way

    def test_tool_call_after_text_closes_and_collapses_it(self):
        """The realistic mid-turn case: text streamed, then a further tool
        call starts (the response wasn't actually final yet)."""
        print_fn = MagicMock()
        on_start = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            on_text_start=on_start,
            on_text_collapse=on_collapse,
        )
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        text_event = MagicMock()
        text_event.part = TextPart(content="Let me check that for you")
        handler.handle_part_start(text_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_called_once()
        collapsed_text, full_text = on_collapse.call_args[0]
        assert "💬 Response" in collapsed_text
        assert "Let me check that for you" in full_text

    def test_carriage_return_in_a_delta_does_not_truncate_the_full_text(self):
        """Same regression as thinking's: `full` must be accumulated at the
        source, not re-read from a buffer a stray `\\r` may have mangled."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)
        from pydantic_ai import TextPartDelta, ToolCallPart
        from pydantic_ai.messages import TextPart

        start_event = MagicMock()
        start_event.part = TextPart(content="Answering the question")
        handler.handle_part_start(start_event)

        delta_event = MagicMock()
        delta_event.delta = TextPartDelta(content_delta="\rmore of the answer")
        handler.handle_part_delta(delta_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_called_once()
        _collapsed, full = on_collapse.call_args[0]
        assert "Answering the question" in full
        assert "more of the answer" in full

    def test_no_open_text_block_never_calls_collapse(self):
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)
        from pydantic_ai import ToolCallPart

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_collapse.assert_not_called()

    def test_run_result_closes_a_still_open_text_block(self):
        """The common case: a turn ends with the final text as the last
        streamed part — no subsequent tool call to trigger the close."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)
        from pydantic_ai.messages import TextPart

        text_event = MagicMock()
        text_event.part = TextPart(content="Here's the final answer")
        handler.handle_part_start(text_event)

        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

        on_collapse.assert_called_once()
        collapsed_text, full_text = on_collapse.call_args[0]
        assert "💬 Response" in collapsed_text
        assert "Here's the final answer" in full_text

    def test_thinking_then_text_each_get_their_own_open_and_collapse(self):
        """A turn with both: thinking closes on the text part start, text
        closes on run result. Each hook pair fires exactly once."""
        print_fn = MagicMock()
        on_thinking_start = MagicMock()
        on_thinking_collapse = MagicMock()
        on_text_start = MagicMock()
        on_text_collapse = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            on_thinking_start=on_thinking_start,
            on_thinking_collapse=on_thinking_collapse,
            on_text_start=on_text_start,
            on_text_collapse=on_text_collapse,
        )
        from pydantic_ai.messages import TextPart, ThinkingPart

        thinking_event = MagicMock()
        thinking_event.part = ThinkingPart(content="Let me think...")
        handler.handle_part_start(thinking_event)

        text_event = MagicMock()
        text_event.part = TextPart(content="Here's the answer")
        handler.handle_part_start(text_event)

        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

        on_thinking_start.assert_called_once_with()
        on_thinking_collapse.assert_called_once()
        on_text_start.assert_called_once_with()
        on_text_collapse.assert_called_once()

    def test_without_hooks_text_still_streams_and_nothing_raises(self):
        """Regression guard: a UI that never opts in (std_ui, Telegram, ...)
        behaves exactly as before — text just streams, nothing collapses."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        text_event = MagicMock()
        text_event.part = TextPart(content="Here's the answer")
        handler.handle_part_start(text_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)  # must not raise


class TestStreamEventHandlerToolCall:
    def test_handle_tool_call_first_time(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.handle_tool_call(mock_event)
        assert "call_123" in handler.printed_tool_ids
        print_fn.assert_called()

    def test_handle_tool_call_duplicate_id(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.printed_tool_ids.add("call_123")
        handler.handle_tool_call(mock_event)
        assert print_fn.call_count == 0

    def test_handle_tool_call_after_delta(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.was_tool_call_delta = True
        handler.handle_tool_call(mock_event)
        print_fn.assert_called()

    def test_handle_tool_call_suppresses_ask_user_question_args(self):
        """AskUserQuestion's large payload is shown in the widget, not dumped here."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="AskUserQuestion",
            args={"questions": [{"question": "Pick?", "options": [{"label": "A"}]}]},
            tool_call_id="call_abc",
        )
        handler.handle_tool_call(mock_event)

        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert "AskUserQuestion" in printed
        assert "call_abc" in printed
        # The questions/options payload must not be echoed.
        assert "options" not in printed
        assert "Pick?" not in printed

    def test_handle_tool_call_uses_recorder_when_set(self):
        print_fn = MagicMock()
        recorder = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, tool_block_recorder=recorder)
        from pydantic_ai import ToolCallPart

        long_value = "x" * 50
        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": long_value}, tool_call_id="call_123"
        )
        handler.handle_tool_call(mock_event)

        print_fn.assert_not_called()
        recorder.assert_called_once()
        collapsed, full = recorder.call_args[0]
        assert long_value not in collapsed
        assert long_value in full

    def test_handle_tool_call_falls_back_to_print_fn_without_recorder(self):
        """Regression guard: a UI that doesn't opt in (std_ui, buffered_ui,
        Telegram, SSE, ...) must see the same line as before this feature."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.handle_tool_call(mock_event)
        print_fn.assert_called_once()

    def test_handle_tool_call_has_no_trailing_newline(self):
        """Regression: a baked-in trailing "\\n" here doubled up with the next
        printed line's own leading "\\n{indentation}", printing a blank line
        after every tool call. Separation comes from the *next* thing printed
        only — see the note in `handle_tool_call`."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler.handle_tool_call(mock_event)
        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert not printed.endswith("\n")

    def test_handle_tool_call_ask_user_question_ignores_recorder(self):
        """The AskUserQuestion line has nothing to expand into (its payload
        renders in the selection widget, not here) — always print directly."""
        print_fn = MagicMock()
        recorder = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, tool_block_recorder=recorder)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="AskUserQuestion",
            args={"questions": [{"question": "Pick?", "options": [{"label": "A"}]}]},
            tool_call_id="call_abc",
        )
        handler.handle_tool_call(mock_event)

        recorder.assert_not_called()
        print_fn.assert_called()


class TestStreamEventHandlerToolPrepareOffsetTracking:
    """Regression suite for the offset-tracked `on_tool_prepare_update` path.

    Before this, the "Prepare tool parameters" placeholder used `\\r` to
    erase "whichever line is currently last" — correct only when tool calls
    never overlap. The moment two tool calls' argument streams interleaved
    (parallel tool calls), one's spinner tick erased the *other's* line,
    leaving orphaned placeholder lines on screen permanently (this is the
    literal bug reported: duplicate "🔄 Prepare tool parameters" lines).
    """

    def test_placeholder_uses_offset_hook_when_provided(self):
        print_fn = MagicMock()
        on_prepare = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_tool_prepare_update=on_prepare
        )
        from pydantic_ai import ToolCallPart

        event = MagicMock()
        event.index = 0
        event.part = ToolCallPart(tool_name="Shell", args={}, tool_call_id="call_1")
        handler.handle_part_start(event)

        on_prepare.assert_called_once()
        key, text = on_prepare.call_args[0]
        assert key == "call_1"
        assert "Prepare tool parameters" in text
        print_fn.assert_not_called()  # went through the hook, not the raw \r print

    def test_delta_updates_the_same_key_not_the_raw_r_print(self):
        print_fn = MagicMock()
        on_prepare = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_tool_prepare_update=on_prepare
        )
        from pydantic_ai import ToolCallPart, ToolCallPartDelta

        start_event = MagicMock()
        start_event.index = 0
        start_event.part = ToolCallPart(
            tool_name="Shell", args={}, tool_call_id="call_1"
        )
        handler.handle_part_start(start_event)

        delta_event = MagicMock()
        delta_event.index = 0
        delta_event.delta = ToolCallPartDelta(args_delta='{"a":')
        handler.handle_part_delta(delta_event)

        assert on_prepare.call_count == 2  # initial placeholder + one spinner tick
        assert on_prepare.call_args_list[-1].args[0] == "call_1"
        print_fn.assert_not_called()

    def test_resolving_a_tool_call_erases_only_its_own_key(self):
        print_fn = MagicMock()
        on_prepare = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_tool_prepare_update=on_prepare
        )
        from pydantic_ai import ToolCallPart

        start_event = MagicMock()
        start_event.index = 0
        tc = ToolCallPart(tool_name="Shell", args={}, tool_call_id="call_1")
        start_event.part = tc
        handler.handle_part_start(start_event)
        on_prepare.reset_mock()

        tool_call_event = MagicMock()
        tool_call_event.part = tc
        handler.handle_tool_call(tool_call_event)

        on_prepare.assert_called_once_with("call_1", "")

    def test_parallel_tool_calls_each_get_their_own_key(self):
        """The actual bug scenario: two tool calls' PartStartEvents fire, then
        their argument deltas interleave. Each must resolve and erase
        through its own key — never touching the other's."""
        print_fn = MagicMock()
        on_prepare = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_tool_prepare_update=on_prepare
        )
        from pydantic_ai import ToolCallPart, ToolCallPartDelta

        tc_a = ToolCallPart(tool_name="ActivateSkill", args={}, tool_call_id="call_A")
        tc_b = ToolCallPart(tool_name="WebSearch", args={}, tool_call_id="call_B")

        start_a = MagicMock(index=0, part=tc_a)
        start_b = MagicMock(index=1, part=tc_b)
        handler.handle_part_start(start_a)
        handler.handle_part_start(start_b)

        delta_a = MagicMock(index=0, delta=ToolCallPartDelta(args_delta='{"skill":'))
        delta_b = MagicMock(index=1, delta=ToolCallPartDelta(args_delta='{"query":'))
        handler.handle_part_delta(delta_a)
        handler.handle_part_delta(delta_b)

        resolve_a = MagicMock(part=tc_a)
        resolve_b = MagicMock(part=tc_b)
        handler.handle_tool_call(resolve_a)
        handler.handle_tool_call(resolve_b)

        keys_touched = {c.args[0] for c in on_prepare.call_args_list}
        assert keys_touched == {"call_A", "call_B"}
        erase_calls = [c for c in on_prepare.call_args_list if c.args[1] == ""]
        assert {c.args[0] for c in erase_calls} == {"call_A", "call_B"}
        # print_fn is still used for the tool calls' own resolved lines
        # (no recorder set here) — but never for the old \r-based spinner,
        # which the offset-tracked path replaces entirely.
        printed = [str(c.args[0]) for c in print_fn.call_args_list if c.args]
        assert not any("\r" in p or "Prepare tool parameters" in p for p in printed)

    def test_without_the_hook_falls_back_to_the_original_r_based_path(self):
        """Regression guard: a UI that hasn't opted in (std_ui, Telegram, the
        SSE web UI, ...) must see exactly the same behavior as before this
        fix — single-line `\\r` animation via `print_fn`."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart, ToolCallPartDelta

        start_event = MagicMock(index=0)
        start_event.part = ToolCallPart(
            tool_name="Shell", args={}, tool_call_id="call_1"
        )
        handler.handle_part_start(start_event)

        delta_event = MagicMock(index=0)
        delta_event.delta = ToolCallPartDelta(args_delta='{"a":')
        handler.handle_part_delta(delta_event)

        printed = [str(c.args[0]) for c in print_fn.call_args_list if c.args]
        assert any("\r" in p for p in printed)


class TestStreamEventHandlerToolResult:
    def test_handle_tool_result_show_result(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_result=True)
        from pydantic_ai import ToolReturnPart

        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "success"
        handler.handle_tool_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Return success" in args

    def test_handle_tool_result_hide_result(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_result=False)
        from pydantic_ai import ToolReturnPart

        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "success"
        handler.handle_tool_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Executed" in args

    def test_handle_tool_result_hide_result_uses_recorder_when_set(self):
        print_fn = MagicMock()
        recorder = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, show_tool_result=False, tool_block_recorder=recorder
        )
        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "y" * 50

        handler.handle_tool_result(mock_event)

        print_fn.assert_not_called()
        recorder.assert_called_once()
        collapsed, full = recorder.call_args[0]
        assert "Executed" in collapsed
        assert "y" * 50 in full

    def test_handle_tool_result_show_result_ignores_recorder(self):
        """show_tool_result=True already shows everything inline — no need to
        make an already-expanded line collapsible."""
        print_fn = MagicMock()
        recorder = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, show_tool_result=True, tool_block_recorder=recorder
        )
        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "success"

        handler.handle_tool_result(mock_event)

        recorder.assert_not_called()
        print_fn.assert_called_once()

    def test_handle_tool_result_has_no_trailing_newline(self):
        """Same redundancy as `handle_tool_call` — see that test's docstring."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_result=False)
        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "success"

        handler.handle_tool_result(mock_event)

        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert not printed.endswith("\n")


class TestStreamEventHandlerRunResult:
    def test_handle_run_result(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        mock_usage = MagicMock()
        mock_usage.requests = 5
        mock_usage.tool_calls = 3
        mock_usage.total_tokens = 1000
        mock_usage.input_tokens = 500
        mock_usage.input_audio_tokens = 0
        mock_usage.output_tokens = 500
        mock_usage.output_audio_tokens = 0
        mock_usage.cache_read_tokens = 100
        mock_usage.cache_write_tokens = 50
        mock_usage.details = {}
        mock_event = MagicMock()
        mock_event.result = MagicMock()
        mock_event.result.usage = mock_usage
        handler.handle_run_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Requests: 5" in args
        assert "Total: 1000" in args
        # Same redundancy as `handle_tool_call` — the caller's own explicit
        # blank line before the rendered final answer already supplies
        # separation; a baked-in one here doubled it.
        assert not args.endswith("\n")

    def test_handle_run_result_invokes_usage_callback(self):
        print_fn = MagicMock()
        usage_callback = MagicMock()
        handler = create_event_handler(print_fn=print_fn, usage_callback=usage_callback)
        mock_usage = MagicMock()
        mock_event = MagicMock()
        mock_event.result.usage = mock_usage
        # Last ModelResponse carries the per-request usage = current context size.
        request = MagicMock(spec=["usage"])
        request.usage = MagicMock()
        mock_event.result.all_messages.return_value = [MagicMock(spec=[]), request]
        handler.handle_run_result(mock_event)
        usage_callback.assert_called_once_with(mock_usage, request.usage)

    def test_handle_run_result_no_usage_callback(self):
        """Run result is still printed when usage_callback is None."""
        print_fn = MagicMock()
        handler = create_event_handler(print_fn=print_fn, usage_callback=None)
        mock_usage = MagicMock()
        mock_usage.requests = 3
        mock_usage.tool_calls = 1
        mock_usage.total_tokens = 500
        mock_usage.input_tokens = 250
        mock_usage.input_audio_tokens = 0
        mock_usage.output_tokens = 250
        mock_usage.output_audio_tokens = 0
        mock_usage.cache_read_tokens = 0
        mock_usage.cache_write_tokens = 0
        mock_usage.details = {}
        mock_event = MagicMock()
        mock_event.result = MagicMock()
        mock_event.result.usage = mock_usage
        handler.handle_run_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Requests: 3" in args
        assert "Total: 500" in args


class TestStreamEventHandlerCall:
    @pytest.mark.asyncio
    async def test_call_part_start_event(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import PartStartEvent
        from pydantic_ai.messages import TextPart

        event = PartStartEvent(index=0, part=TextPart(content="Hello"))
        await handler(event)
        assert handler.event_prefix == "\n  "

    @pytest.mark.asyncio
    async def test_call_final_result_event(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import FinalResultEvent

        event = FinalResultEvent(tool_name="test", tool_call_id="123")
        handler.was_tool_call_delta = True
        await handler(event)
        assert handler.was_tool_call_delta is False

    @pytest.mark.asyncio
    async def test_call_output_tool_call_and_result_events(self):
        """OutputToolCallEvent/OutputToolResultEvent (final/deferred-output tool
        calls) must dispatch through the same handlers as function tool calls,
        since they share the ToolCallEvent/ToolResultEvent base."""
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_result=True)
        from pydantic_ai import OutputToolCallEvent, OutputToolResultEvent
        from pydantic_ai.messages import ToolCallPart, ToolReturnPart

        call_event = OutputToolCallEvent(
            part=ToolCallPart(
                tool_name="final_result", args="{}", tool_call_id="call_1"
            )
        )
        await handler(call_event)
        assert "call_1" in print_fn.call_args[0][0]

        result_event = OutputToolResultEvent(
            part=ToolReturnPart(
                tool_name="final_result", content="done", tool_call_id="call_1"
            )
        )
        await handler(result_event)
        assert "Return done" in print_fn.call_args[0][0]


class TestCreateEventHandler:
    def test_create_event_handler(self):
        print_fn = MagicMock()
        recorder = MagicMock()
        handler = create_event_handler(
            print_fn=print_fn,
            indent_level=2,
            show_tool_call_detail=True,
            show_tool_result=True,
            tool_block_recorder=recorder,
        )
        assert isinstance(handler, StreamEventHandler)
        assert handler.indentation == "    "
        assert handler.show_tool_call_detail is True
        mock_event = MagicMock()
        from pydantic_ai import ToolCallPart

        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"long": "x" * 50}, tool_call_id="call_1"
        )
        handler.handle_tool_call(mock_event)
        recorder.assert_called_once()


class TestGetTruncatedEventPartArgs:
    def test_no_part_attribute(self):
        event = MagicMock(spec=[])
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_part_no_args(self):
        event = MagicMock()
        event.part = MagicMock(spec=[])
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_args_empty_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = ""
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_args_none(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = None
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_args_null_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = "null"
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_args_empty_dict_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = "{}"
        result = get_truncated_event_part_args(event)
        assert result == {}

    def test_args_json_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = '{"key": "value", "long": "' + "x" * 50 + '"}'
        result = get_truncated_event_part_args(event)
        assert isinstance(result, dict)
        assert "key" in result

    def test_args_dict(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = {"key": "value"}
        result = get_truncated_event_part_args(event)
        assert result == {"key": "value"}


class TestGetFullEventPartArgs:
    def test_no_part_attribute(self):
        event = MagicMock(spec=[])
        assert get_full_event_part_args(event) == {}

    def test_args_empty_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = ""
        assert get_full_event_part_args(event) == {}

    def test_returns_untruncated_values(self):
        """The whole point: unlike the truncated variant, long values survive."""
        long_value = "x" * 50
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = {"long": long_value}
        result = get_full_event_part_args(event)
        assert result == {"long": long_value}
        # Sanity: the truncated sibling really does clip the same input.
        assert get_truncated_event_part_args(event) != result

    def test_does_not_mutate_original_args(self):
        event = MagicMock()
        event.part = MagicMock()
        original = {"long": "x" * 50}
        event.part.args = original
        get_full_event_part_args(event)
        assert event.part.args == original


class TestGetEventPartContent:
    def test_no_part_attribute(self):
        event = MagicMock(spec=[])
        result = get_event_part_content(event)
        assert result == ""

    def test_part_no_content(self):
        event = MagicMock()
        event.part = MagicMock(spec=[])
        result = get_event_part_content(event)
        assert result == ""

    def test_part_with_content(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.content = "Hello world"
        result = get_event_part_content(event)
        assert result == "Hello world"


def _spinner_calls(print_fn):
    return [
        c
        for c in print_fn.call_args_list
        if "Prepare tool parameters" in str(c.args[0])
    ]


class TestStreamEventHandlerSpinnerThrottle:
    """The 'Prepare tool parameters' spinner must repaint at most ~10x/sec so a
    slow model streaming thousands of tool-arg deltas can't flood stdout (the
    observed 9k+ frames / 500KB) or add per-frame syscall latency."""

    def test_spinner_repaint_throttled_within_one_instant(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        event = MagicMock()
        event.delta = ToolCallPartDelta(args_delta='{"a":')

        with patch("zrb.llm.util.stream_response.time.monotonic", return_value=100.0):
            for _ in range(50):
                handler.handle_part_delta(event)

        # 50 deltas at the same instant collapse to a single repaint.
        assert len(_spinner_calls(print_fn)) == 1
        # State still flips so the carriage-return cleanup downstream fires.
        assert handler.was_tool_call_delta is True

    def test_spinner_repaints_after_interval(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        event = MagicMock()
        event.delta = ToolCallPartDelta(args_delta="x")

        # One monotonic() read per delta; the third is >interval after the first.
        times = [100.0, 100.05, 100.5, 100.55]
        with patch("zrb.llm.util.stream_response.time.monotonic", side_effect=times):
            for _ in range(4):
                handler.handle_part_delta(event)

        assert len(_spinner_calls(print_fn)) == 2
