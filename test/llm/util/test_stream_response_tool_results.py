from unittest.mock import MagicMock

import pytest

from zrb.llm.util.stream_response import (
    StreamEventHandler,
    create_event_handler,
    get_truncated_event_part_args,
)


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
