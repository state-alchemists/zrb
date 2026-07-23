from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.util.stream_response import (
    StreamEventHandler,
    _get_event_part_content,
    _get_truncated_event_part_args,
    _truncate_arg,
    _truncate_kwargs,
    create_event_handler,
)


class TestStreamEventHandlerInit:
    def test_init_default_values(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        assert handler._indentation == "  "
        assert handler._show_tool_call_detail is False
        assert handler._show_tool_result is False
        assert handler._progress_idx == 0
        assert handler._was_tool_call_delta is False
        assert handler._was_tool_call_start is False
        assert handler._event_prefix == "  "
        assert handler._printed_tool_ids == set()

    def test_init_custom_values(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(
            print_fn=print_fn,
            indent_level=3,
            show_tool_call_detail=True,
            show_tool_result=True,
        )
        assert handler._indentation == "      "
        assert handler._show_tool_call_detail is True
        assert handler._show_tool_result is True


class TestStreamEventHandlerFprint:
    def test_fprint_simple_text(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler._fprint("Hello", kind="text")
        print_fn.assert_called_once_with("Hello", "text")

    def test_fprint_with_trailing_newline(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler._fprint("Hello\n", kind="text")
        print_fn.assert_called_once_with("Hello\n", "text")

    def test_fprint_preserve_leading_newline(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler._fprint("\nHello", preserve_leading_newline=True, kind="text")
        print_fn.assert_called_once_with("\nHello", "text")

    def test_fprint_multiline_indent(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        handler._fprint("Line1\nLine2", kind="text")
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
        result = handler._handle_part_start(mock_event)
        assert result is True
        assert handler._was_tool_call_start is True

    def test_handle_part_start_text_part(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai.messages import TextPart

        mock_event = MagicMock()
        mock_event.part = TextPart(content="Hello world")
        result = handler._handle_part_start(mock_event)
        assert result is False
        print_fn.assert_called()

    def test_handle_part_start_thinking_part(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai.messages import ThinkingPart

        mock_event = MagicMock()
        mock_event.part = ThinkingPart(content="Let me think...")
        result = handler._handle_part_start(mock_event)
        assert result is False
        print_fn.assert_called()


class TestStreamEventHandlerPartDelta:
    def test_handle_part_delta_text(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import TextPartDelta

        mock_event = MagicMock()
        mock_event.delta = TextPartDelta(content_delta="Hello")
        handler._handle_part_delta(mock_event)
        print_fn.assert_called()
        assert handler._was_tool_call_delta is False
        assert handler._was_tool_call_start is False

    def test_handle_part_delta_thinking(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ThinkingPartDelta

        mock_event = MagicMock()
        mock_event.delta = ThinkingPartDelta(content_delta="Thinking...")
        handler._handle_part_delta(mock_event)
        print_fn.assert_called()

    def test_handle_part_delta_tool_call_with_detail(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=True)
        from pydantic_ai import ToolCallPartDelta

        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler._handle_part_delta(mock_event)
        print_fn.assert_called()
        assert handler._was_tool_call_delta is True

    def test_handle_part_delta_tool_call_without_detail(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler._handle_part_delta(mock_event)
        assert handler._was_tool_call_delta is True
        assert handler._progress_idx == 1

    def test_handle_part_delta_tool_call_progress_wraparound(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_call_detail=False)
        from pydantic_ai import ToolCallPartDelta

        handler._progress_idx = 9
        mock_event = MagicMock()
        mock_event.delta = ToolCallPartDelta(
            tool_name_delta="test", args_delta='{"key":'
        )
        handler._handle_part_delta(mock_event)
        assert handler._progress_idx == 0


class TestStreamEventHandlerToolCall:
    def test_handle_tool_call_first_time(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler._handle_tool_call(mock_event)
        assert "call_123" in handler._printed_tool_ids
        print_fn.assert_called()

    def test_handle_tool_call_duplicate_id(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler._printed_tool_ids.add("call_123")
        handler._handle_tool_call(mock_event)
        assert print_fn.call_count == 0

    def test_handle_tool_call_after_delta(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import ToolCallPart

        mock_event = MagicMock()
        mock_event.part = ToolCallPart(
            tool_name="my_tool", args={"param": "value"}, tool_call_id="call_123"
        )
        handler._was_tool_call_delta = True
        handler._handle_tool_call(mock_event)
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
        handler._handle_tool_call(mock_event)

        printed = "".join(str(c.args[0]) for c in print_fn.call_args_list if c.args)
        assert "AskUserQuestion" in printed
        assert "call_abc" in printed
        # The questions/options payload must not be echoed.
        assert "options" not in printed
        assert "Pick?" not in printed


class TestStreamEventHandlerToolResult:
    def test_handle_tool_result_show_result(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn, show_tool_result=True)
        from pydantic_ai import ToolReturnPart

        mock_event = MagicMock()
        mock_event.tool_call_id = "call_123"
        mock_event.part = MagicMock()
        mock_event.part.content = "success"
        handler._handle_tool_result(mock_event)
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
        handler._handle_tool_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Executed" in args


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
        handler._handle_run_result(mock_event)
        print_fn.assert_called()
        args = print_fn.call_args[0][0]
        assert "Requests: 5" in args
        assert "Total: 1000" in args

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
        handler._handle_run_result(mock_event)
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
        handler._handle_run_result(mock_event)
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
        assert handler._event_prefix == "\n  "

    @pytest.mark.asyncio
    async def test_call_final_result_event(self):
        print_fn = MagicMock()
        handler = StreamEventHandler(print_fn=print_fn)
        from pydantic_ai import FinalResultEvent

        event = FinalResultEvent(tool_name="test", tool_call_id="123")
        handler._was_tool_call_delta = True
        await handler(event)
        assert handler._was_tool_call_delta is False

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
        handler = create_event_handler(
            print_fn=print_fn,
            indent_level=2,
            show_tool_call_detail=True,
            show_tool_result=True,
        )
        assert isinstance(handler, StreamEventHandler)
        assert handler._indentation == "    "
        assert handler._show_tool_call_detail is True


class TestGetTruncatedEventPartArgs:
    def test_no_part_attribute(self):
        event = MagicMock(spec=[])
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_part_no_args(self):
        event = MagicMock()
        event.part = MagicMock(spec=[])
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_args_empty_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = ""
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_args_none(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = None
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_args_null_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = "null"
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_args_empty_dict_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = "{}"
        result = _get_truncated_event_part_args(event)
        assert result == {}

    def test_args_json_string(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = '{"key": "value", "long": "' + "x" * 50 + '"}'
        result = _get_truncated_event_part_args(event)
        assert isinstance(result, dict)
        assert "key" in result

    def test_args_dict(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.args = {"key": "value"}
        result = _get_truncated_event_part_args(event)
        assert result == {"key": "value"}


class TestTruncateKwargs:
    def test_truncate_kwargs(self):
        kwargs = {"short": "abc", "long": "a" * 50}
        result = _truncate_kwargs(kwargs)
        assert result["short"] == "abc"
        assert len(result["long"]) == 30
        assert "..." in result["long"]


class TestTruncateArg:
    def test_truncate_short_string(self):
        result = _truncate_arg("short", length=30)
        assert result == "short"

    def test_truncate_long_string(self):
        result = _truncate_arg("a" * 50, length=30)
        assert len(result) == 30
        assert result.endswith("...")

    def test_truncate_non_string(self):
        result = _truncate_arg(12345)
        assert result == 12345


class TestGetEventPartContent:
    def test_no_part_attribute(self):
        event = MagicMock(spec=[])
        result = _get_event_part_content(event)
        assert result == ""

    def test_part_no_content(self):
        event = MagicMock()
        event.part = MagicMock(spec=[])
        result = _get_event_part_content(event)
        assert result == ""

    def test_part_with_content(self):
        event = MagicMock()
        event.part = MagicMock()
        event.part.content = "Hello world"
        result = _get_event_part_content(event)
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
                handler._handle_part_delta(event)

        # 50 deltas at the same instant collapse to a single repaint.
        assert len(_spinner_calls(print_fn)) == 1
        # State still flips so the carriage-return cleanup downstream fires.
        assert handler._was_tool_call_delta is True

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
                handler._handle_part_delta(event)

        assert len(_spinner_calls(print_fn)) == 2
