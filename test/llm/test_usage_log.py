"""The usage log keeps what `RunUsage` reports, and keeps it readable later."""

import json
import pathlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.history_manager.conversation_naming import with_slug
from zrb.llm.usage_log import read_records, record_usage, usage_store_path
from zrb.util.string.name import get_conversation_key, get_random_name

JANUARY = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
FEBRUARY = datetime(2026, 2, 15, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """Point the log at a temporary directory rather than the user's home."""
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def test_a_record_keeps_every_counted_field(usage_dir):
    usage = RunUsage(
        input_tokens=1200,
        output_tokens=340,
        cache_read_tokens=940,
        cache_write_tokens=50,
        output_reasoning_tokens=120,
        requests=3,
        tool_calls=5,
        unmeasured_requests=1,
    )

    record = record_usage(usage, model="some-model", session="s1", when=JANUARY)

    assert record is not None
    assert record.input_tokens == 1200
    assert record.output_tokens == 340
    assert record.cache_read_tokens == 940
    assert record.cache_write_tokens == 50
    assert record.reasoning_tokens == 120
    assert record.requests == 3
    assert record.tool_calls == 5
    assert record.unmeasured_requests == 1
    assert record.model == "some-model"
    assert record.session == "s1"


def test_the_record_round_trips_through_the_file(usage_dir):
    record_usage(RunUsage(input_tokens=10, output_tokens=2), model="m", when=JANUARY)

    (stored,) = read_records()

    assert stored.input_tokens == 10
    assert stored.output_tokens == 2
    assert stored.timestamp == JANUARY


def test_the_cache_ratio_uses_the_same_definition_as_pydantic_ai(usage_dir):
    usage = RunUsage(input_tokens=1000, cache_read_tokens=940)

    record = record_usage(usage, model="m", when=JANUARY)

    assert record is not None
    assert record.cache_hit_ratio == pytest.approx(usage.cache_hit_ratio)
    assert record.cache_hit_ratio == pytest.approx(0.94)


def test_a_run_with_no_input_tokens_has_no_ratio(usage_dir):
    record = record_usage(RunUsage(requests=1, output_tokens=4), model="m", when=JANUARY)

    assert record is not None
    assert record.cache_hit_ratio == 0.0


def test_a_run_that_reported_nothing_is_not_recorded(usage_dir):
    """A mocked agent, or a provider that said nothing, adds no information."""
    assert record_usage(RunUsage(), model="m", when=JANUARY) is None
    assert read_records() == []


def test_an_unpriced_run_is_recorded_as_unknown_not_free(usage_dir):
    record = record_usage(RunUsage(input_tokens=5, cost=None), model="local", when=JANUARY)

    assert record is not None
    assert record.cost is None


def test_a_priced_run_keeps_its_cost(usage_dir):
    record = record_usage(RunUsage(input_tokens=5, cost=0.55), model="m", when=JANUARY)

    assert record is not None
    assert record.cost == pytest.approx(0.55)


def test_each_month_gets_its_own_file(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="m", when=JANUARY)
    record_usage(RunUsage(input_tokens=1), model="m", when=FEBRUARY)

    assert usage_store_path(JANUARY).endswith("usage-2026-01.jsonl")
    assert usage_store_path(FEBRUARY).endswith("usage-2026-02.jsonl")
    assert sorted(path.name for path in usage_dir.glob("*.jsonl")) == [
        "usage-2026-01.jsonl",
        "usage-2026-02.jsonl",
    ]


def test_reading_a_window_skips_other_months(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="january", when=JANUARY)
    record_usage(RunUsage(input_tokens=1), model="february", when=FEBRUARY)

    records = read_records(
        since=datetime(2026, 1, 1, tzinfo=timezone.utc),
        until=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )

    assert [record.model for record in records] == ["january"]


def test_reading_without_a_window_returns_every_record_oldest_first(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="later", when=FEBRUARY)
    record_usage(RunUsage(input_tokens=1), model="earlier", when=JANUARY)

    records = read_records()

    assert [record.model for record in records] == ["earlier", "later"]


def test_reading_can_restrict_itself_to_one_session(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="m", session="wanted", when=JANUARY)
    record_usage(RunUsage(input_tokens=1), model="m", session="other", when=JANUARY)

    records = read_records(session_key="wanted")

    assert [record.session for record in records] == ["wanted"]


def test_a_run_belongs_to_its_conversation_across_the_rename(usage_dir):
    """Auto-naming renames the conversation after its first turn, so the row
    written under the generated name must still answer for it (ADR-0109)."""
    name = get_random_name()
    record_usage(RunUsage(input_tokens=1), model="early", session=name, when=JANUARY)

    records = read_records(session_key=get_conversation_key(with_slug(name, "topic")))

    assert [record.model for record in records] == ["early"]


def test_a_malformed_line_is_skipped_rather_than_raised(usage_dir):
    record_usage(RunUsage(input_tokens=7), model="good", when=JANUARY)
    with open(usage_store_path(JANUARY), "a", encoding="utf-8") as handle:
        handle.write('{"model": "truncated"\n')
        handle.write("not json at all\n")

    records = read_records()

    assert [record.model for record in records] == ["good"]
    assert records[0].input_tokens == 7


def test_a_read_of_a_missing_directory_returns_nothing(usage_dir):
    assert read_records(directory=str(usage_dir / "absent")) == []


def test_a_failed_write_does_not_raise(usage_dir, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    CFG.LLM_USAGE_DIR = str(blocker / "nested")

    record = record_usage(RunUsage(input_tokens=1), model="m", when=JANUARY)

    assert record is None


def test_the_duration_and_kind_travel_with_the_record(usage_dir):
    record_usage(
        RunUsage(input_tokens=1), model="m", kind="subagent", duration_ms=4200, when=JANUARY
    )

    (stored,) = read_records()

    assert stored.kind == "subagent"
    assert stored.duration_ms == 4200


def test_a_window_bound_without_a_timezone_is_read_as_utc(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="m", when=JANUARY)

    records = read_records(
        since=datetime(2026, 1, 15, 0, 0),
        until=datetime(2026, 1, 16, 0, 0),
    )

    assert len(records) == 1


def test_records_are_one_json_object_per_line(usage_dir):
    record_usage(RunUsage(input_tokens=1), model="first", when=JANUARY)
    record_usage(RunUsage(input_tokens=1), model="second", when=JANUARY)

    lines = pathlib.Path(usage_store_path(JANUARY)).read_text(encoding="utf-8").splitlines()

    assert [json.loads(line)["model"] for line in lines] == ["first", "second"]


def test_consecutive_months_are_all_read(usage_dir):
    start = datetime(2025, 12, 20, tzinfo=timezone.utc)
    for offset in range(3):
        record_usage(
            RunUsage(input_tokens=1),
            model=f"m{offset}",
            when=start + timedelta(days=31 * offset),
        )

    records = read_records(since=start, until=start + timedelta(days=70))

    assert len(records) == 3


def _fake_run_from(result):
    """An ``agent.run`` that hands the runner the events it expects.

    Mirrors the fake-run helper in `test_runner_retry`: the trailing
    `AgentRunResultEvent` is stripped out of the stream and returned as
    ``agent.run()``'s value, which is what the real `event_stream_handler`
    contract looks like.
    """

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
async def test_a_headless_run_writes_one_line(usage_dir):
    """The seam is the runner, so a run with no UI is accounted for too."""
    result = MagicMock()
    result.output = "done"
    result.all_messages.return_value = []
    result.usage = RunUsage(input_tokens=120, output_tokens=8, requests=1)
    result.response.model_name = "test-model"
    agent = MagicMock()
    agent.run = _fake_run_from(result)

    await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter()
    )

    (record,) = read_records()
    assert record.model == "test-model"
    assert record.input_tokens == 120
    assert record.output_tokens == 8
    assert record.requests == 1
    assert record.duration_ms >= 0


@pytest.mark.asyncio
async def test_the_session_name_comes_from_the_ui(usage_dir):
    result = MagicMock()
    result.output = "done"
    result.all_messages.return_value = []
    result.usage = RunUsage(input_tokens=10, requests=1)
    result.response.model_name = "test-model"
    agent = MagicMock()
    agent.run = _fake_run_from(result)
    ui = MagicMock()
    ui.conversation_session_name = "calm-gate"

    await run_agent(
        agent=agent, message="Hi", message_history=[], limiter=LLMLimiter(), ui=ui
    )

    (record,) = read_records()
    assert record.session == "calm-gate"
