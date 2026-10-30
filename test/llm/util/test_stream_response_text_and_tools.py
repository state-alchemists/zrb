from unittest.mock import MagicMock

from zrb.llm.util.stream_response import CONTINUATION_PAD, StreamEventHandler


class TestStreamEventHandlerTextCollapse:
    "Mirrors TestStreamEventHandlerThinkingCollapse: the final text"

    def test_text_part_opens_block_when_hook_set(self):
        print_fn = MagicMock()
        on_start = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_start=on_start)
        from pydantic_ai.messages import TextPart

        mock_event = MagicMock()
        mock_event.part = TextPart(content="Here's the answer")
        handler.handle_part_start(mock_event)

        on_start.assert_called_once_with()
        print_fn.assert_called()

    def test_tool_call_after_text_settles_it_with_its_own_text(self):
        """The realistic mid-turn case: text streamed, then a further tool.

        That text is prose written before acting, not the turn's answer, so the
        block is settled — handed over in full — rather than collapsed into the
        placeholder the final answer gets.
        """
        print_fn = MagicMock()
        on_start = MagicMock()
        on_collapse = MagicMock()
        on_settle = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            on_text_start=on_start,
            on_text_collapse=on_collapse,
            on_text_settle=on_settle,
        )
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        text_event = MagicMock()
        text_event.part = TextPart(content="Let me check that for you")
        handler.handle_part_start(text_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_settle.assert_called_once_with(
            "Let me check that for you", f"{handler.indentation}{CONTINUATION_PAD}"
        )
        on_collapse.assert_not_called()

    def test_settled_text_carries_no_indentation_or_leading_icon(self):
        """A markdown renderer would read the stream's indentation as code, so
        the settled text is the model's own words."""
        print_fn = MagicMock()
        on_settle = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_text_settle=on_settle, indent_level=2
        )
        from pydantic_ai import TextPartDelta, ToolCallPart
        from pydantic_ai.messages import TextPart

        start_event = MagicMock()
        start_event.part = TextPart(content="Let me check")
        handler.handle_part_start(start_event)

        delta_event = MagicMock()
        delta_event.delta = TextPartDelta(content_delta=" that for you")
        handler.handle_part_delta(delta_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_settle.assert_called_once_with(
            "Let me check that for you", f"{handler.indentation}{CONTINUATION_PAD}"
        )

    def test_an_empty_text_block_still_collapses_instead_of_settling(self):
        """Nothing to keep — the placeholder is better than a bare icon."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        on_settle = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn, on_text_collapse=on_collapse, on_text_settle=on_settle
        )
        from pydantic_ai import ToolCallPart
        from pydantic_ai.messages import TextPart

        text_event = MagicMock()
        text_event.part = TextPart(content="")
        handler.handle_part_start(text_event)

        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_settle.assert_not_called()
        on_collapse.assert_called_once()
        collapsed_text, _full = on_collapse.call_args[0]
        assert "💬 Response" in collapsed_text

    def test_carriage_return_in_a_delta_does_not_truncate_the_full_text(self):
        "Same regression as thinking's: `full` must be accumulated at the"
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)
        from pydantic_ai import TextPartDelta
        from pydantic_ai.messages import TextPart

        start_event = MagicMock()
        start_event.part = TextPart(content="Answering the question")
        handler.handle_part_start(start_event)

        delta_event = MagicMock()
        delta_event.delta = TextPartDelta(content_delta="\rmore of the answer")
        handler.handle_part_delta(delta_event)

        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

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
        "A turn with both: thinking closes on the text part start, text"
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
        handler.handle_part_start(tool_event)


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
        "AskUserQuestion's large payload is shown in the widget, not dumped here."
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
        "Without a recorder, the tool call is printed normally."
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
        "Tool-call output has no trailing newline."
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


class TestStreamEventHandlerSpokenMarkers:
    """`<spoken>` marks what is read aloud; the screen shows the whole reply
    without the markers, which belong to the ear alone."""

    def _text_start(self, handler, content: str):
        from pydantic_ai.messages import TextPart

        event = MagicMock()
        event.part = TextPart(content=content)
        handler.handle_part_start(event)

    def _text_delta(self, handler, content: str):
        from pydantic_ai.messages import TextPartDelta

        event = MagicMock()
        event.delta = TextPartDelta(content_delta=content)
        handler.handle_part_delta(event)

    def _printed(self, print_fn: MagicMock) -> str:
        return "".join(
            str(call.args[0]) for call in print_fn.call_args_list if call.args
        )

    def test_a_streamed_reply_reaches_the_screen_without_the_markers(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)

        self._text_start(handler, "<spoken>😊 Fixed it.</spoken>")
        self._text_delta(handler, "\nTwo files changed.")

        printed = self._printed(print_fn)
        assert "spoken" not in printed
        assert "😊 Fixed it." in printed
        assert "Two files changed." in printed

    def test_a_marker_split_across_two_deltas_reaches_no_screen(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)

        self._text_start(handler, "")
        for piece in ("<spo", "ken>All green.", "</spoke", "n> Detail."):
            self._text_delta(handler, piece)

        printed = self._printed(print_fn)
        assert "spoken" not in printed
        assert "All green. Detail." in printed

    def test_a_settled_block_carries_no_marker(self):
        """What `settle_text_block` renders in full is the block's own text."""
        on_settle = MagicMock()
        handler = StreamEventHandler(print_fn=MagicMock(), on_text_settle=on_settle)
        from pydantic_ai import ToolCallPart

        self._text_start(handler, "<spoken>Reading the file.</spoken>")
        tool_event = MagicMock()
        tool_event.part = ToolCallPart(tool_name="t", args={}, tool_call_id="1")
        handler.handle_part_start(tool_event)

        on_settle.assert_called_once_with(
            "Reading the file.", f"{handler.indentation}{CONTINUATION_PAD}"
        )

    def test_the_final_text_carries_no_marker(self):
        """The hint a closed block collapses into counts, and keeps, the text
        the user is meant to read."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)

        self._text_start(handler, "<spoken>😊 Done.</spoken>\nTwo files changed.")
        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

        _collapsed, full = on_collapse.call_args[0]
        assert "spoken" not in full
        assert "😊 Done." in full
        assert "Two files changed." in full

    def test_a_trailing_partial_marker_is_shown_instead_of_lost(self):
        """A reply cut off after `<spo` wrote prose, not a marker: closing the
        block must not swallow it."""
        print_fn = MagicMock()
        on_collapse = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, on_text_collapse=on_collapse)

        self._text_start(handler, "prose <spo")
        result_event = MagicMock()
        result_event.result.usage = MagicMock()
        handler.handle_run_result(result_event)

        _collapsed, full = on_collapse.call_args[0]
        assert "prose <spo" in full
