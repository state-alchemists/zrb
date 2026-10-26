"""The usage log counts tool calls and failures per tool name, names only."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.usage_log import (
    count_tool_calls,
    read_records,
    record_usage,
    usage_store_path,
)

JANUARY = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def _round():
    """One model round: two Reads (one fails its arguments), one Shell."""
    return [
        ModelResponse(
            parts=[
                ToolCallPart("Read", {"path": "/secret/plan.txt"}, "1"),
                ToolCallPart("Read", {"path": "/other"}, "2"),
                ToolCallPart("Shell", {"command": "echo hunter2"}, "3"),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart("Read", "file body", "1"),
                ToolReturnPart("Read", "bad arguments", "2", outcome="retried"),
                ToolReturnPart("Shell", "boom", "3", outcome="failed"),
            ]
        ),
    ]


def test_calls_and_failures_are_counted_per_tool_name():
    calls, errors = count_tool_calls(_round())

    assert calls == {"Read": 2, "Shell": 1}
    assert errors == {"Read": 1, "Shell": 1}


def test_a_message_without_tool_parts_counts_nothing():
    assert count_tool_calls([ModelRequest(parts=[]), MagicMock(parts=None)]) == (
        {},
        {},
    )


def test_the_counts_round_trip_through_the_file(usage_dir):
    record_usage(
        RunUsage(input_tokens=10),
        model="m",
        when=JANUARY,
        tool_counts={"Read": 2},
        tool_errors={"Read": 1},
    )

    (record,) = read_records()

    assert record.tool_counts == {"Read": 2}
    assert record.tool_errors == {"Read": 1}


def test_a_line_written_before_the_fields_existed_still_reads(usage_dir):
    old = {
        "timestamp": JANUARY.isoformat(),
        "model": "old-model",
        "session": "s",
        "kind": "turn",
        "input_tokens": 5,
        "output_tokens": 1,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "requests": 1,
        "tool_calls": 2,
        "unmeasured_requests": 0,
        "duration_ms": 3,
        "cost": None,
    }
    path = usage_store_path(JANUARY)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(old) + "\n")

    (record,) = read_records()

    assert record.model == "old-model"
    assert record.tool_counts == {}
    assert record.tool_errors == {}


def test_a_malformed_tool_map_keeps_the_run_and_drops_the_detail(usage_dir):
    record_usage(RunUsage(input_tokens=10), model="m", when=JANUARY)
    path = usage_store_path(JANUARY)
    line = json.loads(open(path, encoding="utf-8").read())
    line["tool_counts"] = {"Read": "many", "Shell": 2, "x": True}
    line["tool_errors"] = ["not", "a", "map"]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")

    (record,) = read_records()

    assert record.input_tokens == 10
    assert record.tool_counts == {"Shell": 2}
    assert record.tool_errors == {}


def test_the_record_holds_tool_names_but_no_arguments(usage_dir):
    calls, errors = count_tool_calls(_round())
    record_usage(
        RunUsage(input_tokens=1),
        model="m",
        when=JANUARY,
        tool_counts=calls,
        tool_errors=errors,
    )

    text = open(usage_store_path(JANUARY), encoding="utf-8").read()

    assert "Read" in text
    for leaked in ("/secret/plan.txt", "hunter2", "file body", "bad arguments"):
        assert leaked not in text


def _fake_run_from(result):
    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        seen = []

        async def events():
            yield AgentRunResultEvent(result=result)
            seen.append(result)

        if handler is not None:
            await handler(MagicMock(), events())
        return seen[0] if seen else None

    return fake_run


@pytest.mark.asyncio
async def test_the_runner_records_a_rounds_tool_calls_once(usage_dir):
    """The seam is the end of a round: its own messages already hold every call."""
    result = MagicMock()
    result.output = "done"
    result.all_messages.return_value = []
    result.new_messages.return_value = _round()
    result.usage = RunUsage(input_tokens=120, requests=1, tool_calls=3)
    result.response.model_name = "test-model"
    agent = MagicMock()
    agent.run = _fake_run_from(result)

    await run_agent(agent=agent, message="Hi", message_history=[], limiter=LLMLimiter())

    (record,) = read_records()
    assert record.tool_counts == {"Read": 2, "Shell": 1}
    assert record.tool_errors == {"Read": 1, "Shell": 1}
