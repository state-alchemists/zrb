"""`/usage` gains a Tools section, and omits it when the log holds nothing for it."""

from datetime import datetime, timezone

import pytest
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.custom_command.usage_command import create_usage_commands, render_usage
from zrb.llm.usage_log import UsageRecord, record_usage


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    return tmp_path


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
