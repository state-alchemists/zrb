from unittest.mock import MagicMock, patch

from zrb.llm.util.stream_response import (
    StreamEventHandler,
    get_event_part_content,
    get_full_event_part_args,
    get_truncated_event_part_args,
)


def _spinner_calls(print_fn):
    return [
        c
        for c in print_fn.call_args_list
        if "Prepare tool parameters" in str(c.args[0])
    ]


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
