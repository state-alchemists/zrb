from unittest.mock import MagicMock

from zrb.llm.util.stream_response import StreamEventHandler


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
