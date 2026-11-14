"""`/usage` gains a Tools and a Memory section, and omits each when it is empty."""

from datetime import datetime, timezone

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.custom_command.usage.command import create_usage_commands, render_usage
from zrb.llm.memory.model import Diary, Fact
from zrb.llm.shared.usage_log import (
    COMPACTION_FORCED,
    COMPONENT_MAIN,
    COMPONENT_SHELL_JUDGE,
    KIND_SUMMARIZATION,
    LIMIT_MESSAGE,
    CompactionDetail,
    ContextComposition,
    UsageRecord,
    UsageTotals,
    record_totals,
    record_usage,
)


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    return tmp_path


@pytest.fixture
def memory_dir(tmp_path, monkeypatch):
    """A store path that does not exist yet: reading it must not create one."""
    path = tmp_path / "memory"
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(path), raising=False)
    return path


def _write_fact(memory, fact_id: str, claim: str, **kwargs) -> None:
    _write_entry(memory / "facts", Fact(id=fact_id, claim=claim, **kwargs))


def _write_diary(memory, day: str, claim: str, **kwargs) -> None:
    _write_entry(memory / "diary", Diary(id=day, claim=claim, **kwargs))


def _write_entry(directory, entry) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{entry.id}.md").write_text(entry.to_markdown())


def _record(**kwargs) -> UsageRecord:
    # Stamped at call time, not at import: a run that reaches this test after
    # midnight would otherwise write yesterday's record and then read today's.
    kwargs.setdefault("when", datetime.now(timezone.utc))
    record = record_usage(RunUsage(input_tokens=1000, requests=1), model="m", **kwargs)
    assert record is not None
    return record


def test_the_tools_section_ranks_calls_and_lists_the_idle_registered_tools(usage_dir):
    records = [
        _record(tool_counts={"Read": 5, "Shell": 2}, tool_errors={"Shell": 1}),
        _record(tool_counts={"Read": 1}),
    ]

    out = render_usage(
        records, "label", registered_tools=["Read", "Shell", "Grep", "Glob"]
    )

    assert out.index("Read") < out.index("Shell")
    assert "6 call(s)" in out
    assert "never called (2 of 4 registered on this machine): Glob, Grep" in out


def test_the_tools_section_shows_error_counts_and_caps_the_idle_list(usage_dir):
    record = _record(tool_counts={"Shell": 4}, tool_errors={"Shell": 2})
    idle = [f"Tool{n:02}" for n in range(20)]

    out = render_usage([record], "label", registered_tools=["Shell", *idle])

    assert "4 call(s)  2 error(s)" in out
    assert "Tool11, +8 more" in out


def test_without_counted_tools_the_section_is_omitted(usage_dir):
    out = render_usage([_record()], "label", registered_tools=["Read"])

    assert "Tools" not in out
    assert "never called" not in out


def test_the_command_prints_the_tools_section_after_the_table(usage_dir):
    _record(tool_counts={"Read": 3})
    (command,) = create_usage_commands()

    out = command.handle({}, None)

    assert out is not None
    assert out.index("model") < out.index("  Tools")


def test_the_command_omits_the_section_when_the_log_holds_nothing_for_it(usage_dir):
    _record()
    (command,) = create_usage_commands()

    out = command.handle({}, None)

    assert out is not None
    assert "  Tools" not in out


def test_the_memory_section_reports_the_core_and_the_store(usage_dir, memory_dir):
    _write_fact(memory_dir, "alpha", "Alpha is true.", pin=True)
    _write_fact(memory_dir, "beta", "Beta is true.")
    _write_fact(
        memory_dir, "gamma", "Gamma was true.", status="retired", reason="stale"
    )
    _write_diary(memory_dir, "2026-11-04", "The day happened.")

    out = render_usage([_record()], "label", registered_tools=[])

    assert "  Memory" in out
    assert "1 pinned" in out
    assert "2 fact(s)" in out
    assert "1 retired" in out
    assert "1 diary day(s)" in out
    assert f"of {CFG.LLM_MEMORY_CORE_MAX_CHARS} chars" in out


def test_the_memory_section_counts_the_windows_writes(usage_dir, memory_dir):
    records = [
        _record(tool_counts={"Remember": 3, "SearchMemory": 2}),
        _record(tool_counts={"Forget": 1}),
    ]

    out = render_usage(records, "label", registered_tools=[])

    assert "3 written" in out
    assert "1 forgotten" in out
    assert "2 search(es)" in out
    assert "1.0 search(es) per run over 2 run(s)" in out


def test_a_store_alone_reports_its_state_and_no_writes(usage_dir, memory_dir):
    _write_fact(memory_dir, "alpha", "Alpha is true.")

    out = render_usage([_record()], "label", registered_tools=[])

    assert "  Memory" in out
    assert "1 fact(s)" in out
    assert "writes" not in out
    assert "recall" not in out


def test_without_a_store_or_a_call_the_section_is_omitted(usage_dir, memory_dir):
    out = render_usage([_record()], "label", registered_tools=[])

    assert "Memory" not in out
    # Asking the question must not answer it by creating the thing asked about.
    assert not memory_dir.exists()


def test_the_command_prints_the_memory_section_after_the_tools_section(
    usage_dir, memory_dir
):
    _write_fact(memory_dir, "alpha", "Alpha is true.")
    _record(tool_counts={"Read": 3, "Remember": 1})
    (command,) = create_usage_commands()

    out = command.handle({}, None)

    assert out is not None
    assert out.index("  Tools") < out.index("  Memory")


def test_the_memory_section_is_absent_when_memory_is_off(
    usage_dir, memory_dir, monkeypatch
):
    _write_fact(memory_dir, "alpha", "Alpha is true.")
    monkeypatch.setattr(CFG, "LLM_MEMORY_ENABLED", False, raising=False)

    out = render_usage([_record()], "label", registered_tools=[])

    assert "Memory" not in out


def test_a_window_with_no_runs_still_reports_the_store(memory_dir):
    _write_fact(memory_dir, "alpha", "Alpha is true.")

    out = render_usage([], "today")

    assert "No usage recorded for today." in out
    assert "  Memory" in out
    assert "1 fact(s)" in out
    assert "writes" not in out


def _compaction_totals() -> UsageTotals:
    """A non-empty total, so `record_totals` writes a line at all."""
    totals = UsageTotals()
    totals.input_tokens = 900
    totals.requests = 1
    return totals


def test_the_compaction_section_names_the_limit_each_fire_answered(usage_dir):
    """The table says what a compaction cost; this says why it ran.

    Without it a reader sees cost and has to guess between the token trigger,
    the message window and a typed `/compress`.
    """
    record = record_totals(
        _compaction_totals(),
        session="s1",
        kind=KIND_SUMMARIZATION,
        when=datetime.now(timezone.utc),
        compaction=CompactionDetail(
            reason=LIMIT_MESSAGE,
            history_tokens=172_329,
            allowed_tokens=172_500,
            prompt_tokens=54_900,
            messages=315,
            window=300,
        ),
    )
    assert record is not None

    out = render_usage([record], "label", registered_tools=[])

    assert "fires (newest first)" in out
    assert "message · 172.3k of 172.5k allowed" in out
    assert "315 of 300 message(s)" in out
    assert "prompt 54.9k" in out
    # The default window is the whole log, which is never rotated, so a stamp
    # without the year cannot tell two same-day fires a year apart apart.
    assert record.timestamp.astimezone().strftime("%Y-%m-%d %H:%M") in out


def test_a_forced_compaction_says_so_without_inventing_a_measurement(usage_dir):
    """`/compress` answers no limit, so it has no history to compare.

    Printing zeroes would read as a history that measured nothing; the line
    has to say what it knows and stop.
    """
    record = record_totals(
        _compaction_totals(),
        session="s1",
        kind=KIND_SUMMARIZATION,
        when=datetime.now(timezone.utc),
        compaction=CompactionDetail(
            reason=COMPACTION_FORCED,
            history_tokens=0,
            allowed_tokens=0,
            prompt_tokens=0,
            messages=84,
            window=300,
        ),
    )
    assert record is not None

    out = render_usage([record], "label", registered_tools=[])

    assert "forced · 84 message(s)" in out
    assert "0 of" not in out


def test_a_window_spent_by_one_thing_draws_no_breakdown(usage_dir):
    """Every line written before this field existed is such a window: one row
    saying "all of it was the turn" is a line to read and nothing to learn."""
    out = render_usage([_record(), _record()], "label", registered_tools=[])
    assert "Who spent it" not in out


def test_a_window_spent_by_two_things_says_how_much_each(usage_dir):
    records = [
        _record(component=COMPONENT_MAIN),
        _record(component=COMPONENT_SHELL_JUDGE),
    ]
    out = render_usage(records, "label", registered_tools=[])
    assert "  Who spent it" in out
    rows = [line for line in out.splitlines() if "shell_judge" in line]
    assert rows, out
    assert "50%" in rows[0], rows[0]


def test_the_context_section_says_where_the_input_went(usage_dir):
    record = _record(
        context=ContextComposition(
            prompt_tokens=4_000, history_tokens=28_000, message_tokens=1_000
        )
    )

    out = render_usage([record], "label")

    assert "Where the input went" in out
    # Shares of the 33.0k the counter says the request was: 4k, 28k, 1k.
    assert "system prompt" in out and "12%" in out
    assert "history" in out and "85%" in out
    # The provider's own number for the same request sits beside the estimate.
    assert "1 turn(s) · provider reported 1.0k for them" in out


def test_without_a_measured_request_the_section_is_omitted(usage_dir):
    out = render_usage([_record()], "label")

    assert "Where the input went" not in out


def _raw_line(**overrides) -> dict:
    """One log line as it is written to disk, before any record class sees it."""
    line = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "m",
        "session": "s",
        "kind": "turn",
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "requests": 1,
        "tool_calls": 0,
        "unmeasured_requests": 0,
        "duration_ms": 1,
        "cost": None,
    }
    line.update(overrides)
    return line


def test_a_line_written_before_the_composition_existed_still_reads():
    record = UsageRecord.from_dict(_raw_line())

    assert record.context is None


def test_a_malformed_composition_is_dropped_rather_than_breaking_the_record():
    record = UsageRecord.from_dict(
        _raw_line(context={"prompt_tokens": 4_000, "history_tokens": "not a number"})
    )

    assert record.context is None
    # The tokens the line paid for survive: the detail is optional, the bill is not.
    assert record.input_tokens == 10


def test_the_composition_survives_being_written_and_read_back(usage_dir):
    record = _record(
        context=ContextComposition(
            prompt_tokens=4_000, history_tokens=28_000, message_tokens=1_000
        )
    )

    read_back = UsageRecord.from_dict(record.to_dict())

    assert read_back.context == ContextComposition(
        prompt_tokens=4_000, history_tokens=28_000, message_tokens=1_000
    )
