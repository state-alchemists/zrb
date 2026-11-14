"""Which model call a line belongs to, and how an old line reads back
without the field (ADR-0142)."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.shared.usage_log import (
    COMPONENT_MAIN,
    COMPONENT_OTHER,
    COMPONENT_SHELL_JUDGE,
    COMPONENT_SUBAGENT,
    COMPONENT_SUMMARIZER,
    KIND_SUMMARIZATION,
    UsageTotals,
    read_records,
    record_agent_usage,
    record_totals,
    record_usage,
    usage_component,
)

JANUARY = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
FEBRUARY = datetime(2026, 2, 15, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """Point the log at a temporary directory rather than the user's home."""
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path




    """The default names the conversation's own rounds, which is what every
    call site that does not say otherwise is."""
    record = record_usage(
        RunUsage(input_tokens=10, requests=1), model="m", when=JANUARY
    )
    assert record is not None
    assert record.component == COMPONENT_MAIN


def test_an_ambient_component_names_every_line_written_inside_it(usage_dir):
    """A sub-agent's rounds go through the same runner as the conversation's,
    so the tag has to travel with the run rather than through each call site."""
    with usage_component(COMPONENT_SUBAGENT):
        inside = record_usage(
            RunUsage(input_tokens=10, requests=1), model="m", when=JANUARY
        )
    outside = record_usage(
        RunUsage(input_tokens=10, requests=1), model="m", when=JANUARY
    )
    assert inside is not None and inside.component == COMPONENT_SUBAGENT
    assert outside is not None and outside.component == COMPONENT_MAIN


def test_a_line_written_before_the_field_existed_reads_back_by_its_kind(usage_dir):
    """Only two modules wrote a line before `component` existed, so a kind names
    its writer without a guess: a compaction line was the summarizer's."""
    turn = record_usage(
        RunUsage(input_tokens=10, requests=1), model="m", when=JANUARY
    )
    spent = UsageTotals()
    spent.input_tokens = 5
    spent.requests = 1
    spent.model = "m"
    compaction = record_totals(
        spent,
        kind=KIND_SUMMARIZATION,
        when=FEBRUARY,
    )
    lines = []
    for record, month in ((turn, "01"), (compaction, "02")):
        assert record is not None
        raw = record.to_dict()
        raw.pop("component")
        (usage_dir / f"usage-2026-{month}.jsonl").write_text(
            json.dumps(raw) + "\n", encoding="utf-8"
        )
        lines.append(raw)
    assert len(lines) == 2
    assert [record.component for record in read_records(directory=str(usage_dir))] == [
        COMPONENT_MAIN,
        COMPONENT_SUMMARIZER,
    ]


def test_a_component_this_version_does_not_know_keeps_its_name(usage_dir):
    """Same rule as `kind`: a line whose component is unknown is still tokens the
    user paid for, so it is filed, not dropped."""
    record_usage(
        RunUsage(input_tokens=10, requests=1),
        model="m",
        when=JANUARY,
        component="something_new",
    )
    assert read_records(directory=str(usage_dir))[0].component == "something_new"


def test_a_finished_run_is_written_with_its_own_model(usage_dir):
    """The auxiliary call sites hand over the result and nothing else: the model
    the provider answered with is more than the caller knows."""
    result = MagicMock()
    result.usage.return_value = RunUsage(input_tokens=10, requests=1)
    result.response.model_name = "small-model"
    record = record_agent_usage(
        result, component=COMPONENT_SHELL_JUDGE, when=JANUARY
    )
    assert record is not None
    assert record.component == COMPONENT_SHELL_JUDGE
    assert record.model == "small-model"


def test_a_run_that_reported_nothing_writes_no_line(usage_dir):
    assert record_agent_usage(MagicMock(), component=COMPONENT_OTHER) is None
