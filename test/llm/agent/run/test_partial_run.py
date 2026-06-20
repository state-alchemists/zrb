"""Tests for PartialRunAccumulator — stream-event capture for retry context."""

import json

from zrb.llm.agent.run.partial_run import PartialRunAccumulator


def test_empty_accumulator_produces_minimal_summary():
    acc = PartialRunAccumulator()
    summary = acc.build_summary()
    assert "[SYSTEM: PREVIOUS ATTEMPT FAILED]" in summary
    assert "The previous attempt was interrupted" not in summary
    assert "tool calls" not in summary


def test_interrupted_without_tool_calls():
    acc = PartialRunAccumulator()
    acc.is_interrupted = True
    summary = acc.build_summary()
    assert "[SYSTEM: PREVIOUS ATTEMPT FAILED]" in summary
    assert "interrupted" in summary
    assert "tool calls" not in summary


def test_error_without_tool_calls():
    acc = PartialRunAccumulator()
    acc.error = "Connection reset by peer"
    summary = acc.build_summary()
    assert "Connection reset by peer" in summary
    assert "tool calls" not in summary


def test_records_tool_call_and_result():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()

    tool_call = FunctionToolCallEvent(
        part=ToolCallPart(
            tool_name="search_files",
            args=json.dumps({"query": "main.py"}),
            tool_call_id="call_1",
        )
    )
    tool_result = FunctionToolResultEvent(
        part=ToolReturnPart(
            tool_name="search_files",
            content="Found: main.py, utils.py",
            tool_call_id="call_1",
        )
    )

    acc.record_event(tool_call)
    acc.record_event(tool_result)
    assert len(acc.completed_tools) == 1

    name, args, result = acc.completed_tools[0]
    assert name == "search_files"
    assert "main.py" in result

    summary = acc.build_summary()
    assert "search_files" in summary
    assert "main.py" in summary


def test_unmatched_tool_result_is_orphaned():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()

    tool_call = FunctionToolCallEvent(
        part=ToolCallPart(
            tool_name="search_files",
            args=json.dumps({"query": "main.py"}),
            tool_call_id="call_1",
        )
    )
    wrong_result = FunctionToolResultEvent(
        part=ToolReturnPart(
            tool_name="read_file",
            content="file content",
            tool_call_id="call_2",
        )
    )

    acc.record_event(tool_call)
    acc.record_event(wrong_result)
    # The wrong tool name resets the pending state without recording
    assert len(acc.completed_tools) == 0

    summary = acc.build_summary()
    assert "search_files" not in summary
    assert "read_file" not in summary


def test_partial_text_flag():
    from pydantic_ai import PartStartEvent
    from pydantic_ai.messages import TextPart

    acc = PartialRunAccumulator()
    assert not acc.has_partial_text

    event = PartStartEvent(
        index=0, part=TextPart(content="Hello"), previous_part_kind=None
    )
    acc.record_event(event)
    assert acc.has_partial_text

    summary = acc.build_summary()
    assert "text response" in summary
    assert "cut off" in summary


def test_text_part_in_summary():
    from pydantic_ai import PartStartEvent
    from pydantic_ai.messages import TextPart

    acc = PartialRunAccumulator()
    acc.is_interrupted = True

    event = PartStartEvent(
        index=0, part=TextPart(content="The answer is"), previous_part_kind=None
    )
    acc.record_event(event)

    summary = acc.build_summary()
    assert "interrupted" in summary
    assert "text response" in summary


def test_multiple_tool_calls():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()

    calls = [
        ("search", {"q": "foo"}, "Found foo.py"),
        ("read", {"path": "foo.py"}, "def main():"),
    ]

    for i, (name, args, result) in enumerate(calls):
        tid = f"call_{i}"
        acc.record_event(
            FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name=name, args=json.dumps(args), tool_call_id=tid
                )
            )
        )
        acc.record_event(
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name=name, content=result, tool_call_id=tid)
            )
        )

    assert len(acc.completed_tools) == 2
    summary = acc.build_summary()
    assert "search" in summary
    assert "read" in summary
    assert "Found foo.py" in summary
    assert "def main():" in summary


def test_truncation_of_long_results():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()
    long_result = "x" * 1000

    acc.record_event(
        FunctionToolCallEvent(
            part=ToolCallPart(tool_name="read", args="{}", tool_call_id="call_1")
        )
    )
    acc.record_event(
        FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name="read", content=long_result, tool_call_id="call_1"
            )
        )
    )

    name, args, result = acc.completed_tools[0]
    assert len(result) == 500 + 3  # truncated + "..."
    assert result.endswith("...")


def test_no_duplicate_tool_records():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()

    # Tool A called
    acc.record_event(
        FunctionToolCallEvent(
            part=ToolCallPart(tool_name="read", args="{}", tool_call_id="call_a")
        )
    )
    # Tool B called before A finishes
    acc.record_event(
        FunctionToolCallEvent(
            part=ToolCallPart(tool_name="search", args="{}", tool_call_id="call_b")
        )
    )
    # Tool B finishes
    acc.record_event(
        FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name="search", content="results", tool_call_id="call_b"
            )
        )
    )
    # Tool A finishes (but was orphaned by the interleaved B)
    acc.record_event(
        FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name="read", content="content", tool_call_id="call_a"
            )
        )
    )

    # Only B should be recorded (A was orphaned by interleaving)
    assert len(acc.completed_tools) == 1
    assert acc.completed_tools[0][0] == "search"


def test_tool_orphaned_by_cancellation():
    from pydantic_ai import FunctionToolCallEvent
    from pydantic_ai.messages import ToolCallPart

    acc = PartialRunAccumulator()

    # Tool called but never completed (no result event)
    acc.record_event(
        FunctionToolCallEvent(
            part=ToolCallPart(
                tool_name="search_files",
                args=json.dumps({"query": "test"}),
                tool_call_id="call_1",
            )
        )
    )

    # The call was registered but never completed, so nothing is recorded and
    # the orphaned tool does not appear in the summary.
    assert len(acc.completed_tools) == 0

    summary = acc.build_summary()
    assert "search_files" not in summary


def test_build_summary_after_tool_and_interruption():
    from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    acc = PartialRunAccumulator()
    acc.is_interrupted = True

    acc.record_event(
        FunctionToolCallEvent(
            part=ToolCallPart(
                tool_name="search",
                args=json.dumps({"q": "foo"}),
                tool_call_id="call_1",
            )
        )
    )
    acc.record_event(
        FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name="search", content="foo.py", tool_call_id="call_1"
            )
        )
    )

    summary = acc.build_summary()
    assert "[SYSTEM: PREVIOUS ATTEMPT FAILED]" in summary
    assert "interrupted" in summary
    assert "search" in summary
    assert "foo.py" in summary
    assert "Review the work already done" in summary
