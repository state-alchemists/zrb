"""A round's probe survives the file, and an older line reads back without one.

The field is a dry run: no line that carries it sent anything different, so what
these cases protect is the record's honesty — a probe that a rule will be judged
on must come back the way it was measured, and a line written before the field
existed must not pretend to have one.
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.contracts.shared.usage_log import (
    RoundBudget,
    read_records,
    record_usage,
    usage_store_path,
)

JANUARY = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """Point the log at a temporary directory rather than the user's home."""
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def _budget(**overrides) -> RoundBudget:
    fields = dict(
        requests_before=12,
        history_tokens=201_000,
        messages=140,
        tool_tokens=45_000,
        mask_resend_tokens=86_000,
        trigger_tokens=200_000,
        system_tokens=4_768,
        message_window=300,
        is_over_trigger=True,
        is_result_pending=False,
        gap_seconds=17.5,
    )
    fields.update(overrides)
    return RoundBudget(**fields)


def test_a_round_carries_its_probe_through_the_file(usage_dir):
    record_usage(RunUsage(input_tokens=10), model="m", when=JANUARY, budget=_budget())

    (stored,) = read_records()

    assert stored.budget is not None
    assert stored.budget.requests_before == 12
    assert stored.budget.history_tokens == 201_000
    assert stored.budget.mask_resend_tokens == 86_000
    assert stored.budget.is_over_trigger is True
    assert stored.budget.is_result_pending is False
    assert stored.budget.gap_seconds == pytest.approx(17.5)
    assert stored.budget.allowed_tokens == 200_000 - 4_768


def test_a_line_written_before_the_probe_reads_back_without_one(usage_dir):
    """A July line has no boundary measurement in it, and inventing one would be
    a claim about a send nobody measured."""
    record_usage(
        RunUsage(input_tokens=10), model="with-probe", when=JANUARY, budget=_budget()
    )
    legacy = {
        "timestamp": JANUARY.isoformat(),
        "model": "before-the-probe",
        "session": "",
        "kind": "turn",
        "input_tokens": 10,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "requests": 1,
        "tool_calls": 0,
        "unmeasured_requests": 0,
        "duration_ms": 0,
        "cost": None,
    }
    with open(usage_store_path(JANUARY), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(legacy) + "\n")

    records = read_records()

    assert records[0].budget is not None
    assert records[1].budget is None


def test_a_malformed_probe_is_dropped_rather_than_failing_the_line(usage_dir):
    record = record_usage(RunUsage(input_tokens=10), model="m", when=JANUARY)
    raw = record.to_dict()
    raw["budget"] = {"history_tokens": "not a number"}
    with open(usage_store_path(JANUARY), "w", encoding="utf-8") as stream:
        stream.write(json.dumps(raw) + "\n")

    (stored,) = read_records()

    assert stored.budget is None
    assert stored.input_tokens == 10


def test_a_first_round_reports_no_wait(usage_dir):
    """Nothing preceded the turn's opening round, so there is no gap to record —
    and a zero would read as a measurement that something happened instantly."""
    record_usage(
        RunUsage(input_tokens=10),
        model="m",
        when=JANUARY,
        budget=_budget(gap_seconds=None),
    )

    (stored,) = read_records()

    assert stored.budget is not None
    assert stored.budget.gap_seconds is None
