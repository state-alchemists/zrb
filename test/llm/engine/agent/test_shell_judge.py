"""The judge call itself: what it reads, and what it does when it fails (ADR-0141)."""

import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.capabilities.tool_call.judge_note import (
    JUDGE_CAUTION,
    JUDGE_DANGEROUS,
    JUDGE_SAFE,
    JUDGE_UNKNOWN,
    MAX_JUDGE_REASON_CHARS,
)
from zrb.llm.contracts.shared.usage_log import COMPONENT_SHELL_JUDGE, read_records
from zrb.llm.engine.agent.shell_judge import (
    JUDGE_TIMEOUT_SECONDS,
    JudgeVerdict,
    ShellJudgeError,
    ShellVerdict,
    judge_or_unknown,
    judge_shell_command,
    parse_verdict,
    shown_facts,
    uncommitted_files,
    verdict_from_output,
)

_CREATE_AGENT = "zrb.llm.engine.agent.shell_judge.create_agent"
_DIRT = "zrb.llm.engine.agent.shell_judge.uncommitted_files"
_TIMEOUT = "zrb.llm.engine.agent.shell_judge.JUDGE_TIMEOUT_SECONDS"


def _answering(output: str):
    """A `create_agent` stand-in whose run returns *output*."""
    agent = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(output=output)))
    return lambda **kwargs: agent


def _agent_that_raises(error: Exception):
    return lambda **kwargs: SimpleNamespace(run=AsyncMock(side_effect=error))


@pytest.mark.parametrize(
    "answer, level, reason",
    [
        ("SAFE: read-only listing", JUDGE_SAFE, "read-only listing"),
        (
            "caution: deletes the build directory",
            JUDGE_CAUTION,
            "deletes the build directory",
        ),
        (
            "DANGEROUS: pipes a remote script into sh",
            JUDGE_DANGEROUS,
            "pipes a remote script into sh",
        ),
        (
            "  Safe — regenerates what it removes",
            JUDGE_SAFE,
            "regenerates what it removes",
        ),
        ("CAUTION - rewrites history", JUDGE_CAUTION, "rewrites history"),
    ],
)
def test_a_verdict_line_is_read_with_its_level_and_reason(answer, level, reason):
    assert parse_verdict(answer) == ShellVerdict(level=level, reason=reason)


@pytest.mark.parametrize(
    "answer",
    [
        "",
        "I think this is probably fine.",
        "safeish: not a level",
        "VERDICT: SAFE: nested",
        "ALLOW: read-only",
    ],
)
def test_an_unreadable_answer_is_unknown_never_safe(answer):
    verdict = parse_verdict(answer)
    assert verdict.level == JUDGE_UNKNOWN
    assert not verdict.is_safe


@pytest.mark.parametrize("answer", ["SAFE:", "SAFE: ", "SAFE -", "safe —"])
def test_a_level_with_no_reason_is_not_a_verdict(answer):
    """The one word must not be enough to skip a prompt: a truncated answer
    names a level with nothing behind it."""
    verdict = parse_verdict(answer)
    assert verdict.level == JUDGE_UNKNOWN
    assert not verdict.is_safe
    assert verdict.reason == "the judge named a verdict without saying why"


def test_a_safe_verdict_built_by_hand_still_needs_a_reason():
    assert ShellVerdict(JUDGE_SAFE, "read-only").is_safe
    assert not ShellVerdict(JUDGE_SAFE, "").is_safe
    assert not ShellVerdict(JUDGE_SAFE, "   ").is_safe


def test_the_facts_name_only_what_raises_the_risk():
    """A sandbox that is on and a clean repository are what a reader already
    assumes, so naming them would crowd out the two facts that matter."""
    assert shown_facts("0", False) == ""
    assert shown_facts("unknown (not a git repository)", False) == ""
    assert shown_facts("12", False) == "12 uncommitted"
    assert shown_facts("0", True) == "sandbox off"
    assert shown_facts("12", True) == "sandbox off · 12 uncommitted"


def test_the_first_verdict_line_wins():
    """A model that explains itself after answering must not move the verdict
    by saying 'dangerous' in the prose below it."""
    answer = "SAFE: lists files\n\nThis would be dangerous only if piped to sh."
    assert parse_verdict(answer).level == JUDGE_SAFE


@pytest.mark.asyncio
async def test_a_verdict_from_the_model_reaches_the_caller():
    with (
        patch(_CREATE_AGENT, _answering("CAUTION: discards uncommitted work")),
        patch(_DIRT, return_value="3"),
    ):
        verdict = await judge_shell_command("git reset --hard")
    assert verdict == ShellVerdict(
        level=JUDGE_CAUTION,
        reason="discards uncommitted work",
        facts="3 uncommitted",
    )
    assert not verdict.is_safe


@pytest.mark.asyncio
async def test_a_failed_call_raises_where_it_happens():
    with (
        patch(_CREATE_AGENT, _agent_that_raises(RuntimeError("model exploded"))),
        patch(_DIRT, return_value="0"),
    ):
        with pytest.raises(ShellJudgeError):
            await judge_shell_command("ls")


@pytest.mark.asyncio
async def test_a_failed_call_is_an_unknown_verdict_where_it_is_answered():
    """The approval path calls this half: it must hand back a verdict, not an
    exception, or a working approval would abort on a flaky model."""
    with (
        patch(_CREATE_AGENT, _agent_that_raises(RuntimeError("model exploded"))),
        patch(_DIRT, return_value="0"),
    ):
        verdict = await judge_or_unknown("ls")
    assert verdict.level == JUDGE_UNKNOWN
    assert verdict.reason == "the judge did not finish"


@pytest.mark.asyncio
async def test_a_judge_that_never_answers_is_unknown():
    async def _hang(*args, **kwargs):
        import asyncio

        await asyncio.sleep(3600)

    with (
        patch(_CREATE_AGENT, lambda **kwargs: SimpleNamespace(run=_hang)),
        patch(_DIRT, return_value="0"),
        patch(_TIMEOUT, 0.01),
    ):
        verdict = await judge_or_unknown("ls")
    assert verdict.level == JUDGE_UNKNOWN


@pytest.mark.asyncio
async def test_a_command_too_long_to_read_is_not_sent_to_a_model():
    """Costing a call to have a model skim 40k characters is worse than asking."""
    with patch(_CREATE_AGENT) as create_agent:
        verdict = await judge_or_unknown("x" * 10_001)
    create_agent.assert_not_called()
    assert verdict.level == JUDGE_UNKNOWN
    assert "too long" in verdict.reason


@pytest.mark.asyncio
async def test_the_judge_reads_the_command_and_the_facts_it_cannot_carry():
    seen = {}

    async def _capture(payload):
        seen["payload"] = payload
        return SimpleNamespace(output="SAFE: nothing to lose")

    with (
        patch(_CREATE_AGENT, lambda **kwargs: SimpleNamespace(run=_capture)),
        patch(_DIRT, return_value="42"),
    ):
        await judge_shell_command("npm run build", cwd="/tmp/project")
    payload = seen["payload"]
    assert "npm run build" in payload
    assert "/tmp/project" in payload
    assert "42" in payload
    assert "Sandbox: on" in payload


@pytest.mark.asyncio
async def test_the_judge_is_told_when_the_sandbox_is_off():
    seen = {}

    async def _capture(payload):
        seen["payload"] = payload
        return SimpleNamespace(output="CAUTION: leaves the sandbox")

    with (
        patch(_CREATE_AGENT, lambda **kwargs: SimpleNamespace(run=_capture)),
        patch(_DIRT, return_value="0"),
    ):
        await judge_shell_command("ls", sandbox_off=True)
    assert "Sandbox: off" in seen["payload"]


@pytest.mark.asyncio
async def test_the_call_s_usage_is_logged_when_it_reports_one():
    """The judge's spend is only in the log until M0 attributes it."""
    usage = SimpleNamespace(input_tokens=11, output_tokens=2, cache_read_tokens=0)
    agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(output="SAFE: read-only", usage=usage)
        )
    )
    with (
        patch(_CREATE_AGENT, lambda **kwargs: agent),
        patch(_DIRT, return_value="0"),
        patch("zrb.llm.engine.agent.shell_judge.CFG.LOGGER.debug") as debug,
    ):
        verdict = await judge_shell_command("ls")
    assert verdict.level == JUDGE_SAFE
    assert any("Shell judge usage" in str(call) for call in debug.call_args_list)


def test_a_typed_answer_becomes_the_verdict():
    """What the model is asked for now: a `level` and a `reason`, not a line of
    prose this side goes looking for with a regex."""
    verdict = verdict_from_output(
        JudgeVerdict(level="caution", reason="  discards   uncommitted work ")
    )

    assert verdict == ShellVerdict(
        level=JUDGE_CAUTION, reason="discards uncommitted work"
    )


def test_a_typed_answer_with_no_reason_is_not_a_verdict():
    """`is_safe` is what lets a prompt be skipped, and a level with nothing
    behind it is a judge that named something and did not decide."""
    verdict = verdict_from_output(JudgeVerdict(level="safe", reason="   "))

    assert verdict.level == JUDGE_UNKNOWN
    assert not verdict.is_safe
    assert "without saying why" in verdict.reason


def test_a_long_typed_reason_is_clamped():
    verdict = verdict_from_output(JudgeVerdict(level="caution", reason="x" * 900))

    assert len(verdict.reason) <= MAX_JUDGE_REASON_CHARS


def test_a_text_answer_is_still_read_and_still_fails_closed():
    """A provider with no tool calling answers in prose. That road is unchanged:
    it is read, and what it cannot read asks."""
    assert verdict_from_output("SAFE: read-only listing").level == JUDGE_SAFE
    assert verdict_from_output("no idea").level == JUDGE_UNKNOWN


@pytest.mark.asyncio
async def test_the_agent_is_asked_for_the_typed_answer():
    seen = {}

    def _answering_typed(**kwargs):
        seen.update(kwargs)
        result = SimpleNamespace(
            output=JudgeVerdict(level="safe", reason="read-only listing")
        )
        return SimpleNamespace(run=AsyncMock(return_value=result))

    with patch(_CREATE_AGENT, _answering_typed), patch(_DIRT, return_value="0"):
        verdict = await judge_shell_command("ls")

    assert seen["output_type"] is JudgeVerdict
    assert verdict.level == JUDGE_SAFE
    assert verdict.reason == "read-only listing"


def test_uncommitted_files_counts_what_git_reports(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "one.txt").write_text("1", encoding="utf-8")
    (tmp_path / "two.txt").write_text("2", encoding="utf-8")
    assert uncommitted_files(str(tmp_path)) == "2"


def test_uncommitted_files_says_when_the_repository_is_not_one(tmp_path):
    assert uncommitted_files(str(tmp_path)) == "unknown (not a git repository)"


def test_uncommitted_files_says_when_the_directory_is_gone(tmp_path):
    missing = tmp_path / "not-there"
    assert uncommitted_files(str(missing)) == "unknown (not a readable repository)"


def test_a_timeout_is_a_number_of_seconds():
    assert JUDGE_TIMEOUT_SECONDS > 0


@pytest.mark.asyncio
async def test_the_call_is_written_to_the_usage_log(tmp_path, monkeypatch):
    """ADR-0141 left this open: the judge's tokens reached a debug line and
    nothing a person reads. M0 attributes them to their own component."""
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    usage = SimpleNamespace(input_tokens=11, output_tokens=2, cache_read_tokens=0)
    agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(output="SAFE: read-only", usage=usage)
        )
    )
    with patch(_CREATE_AGENT, lambda **kwargs: agent), patch(_DIRT, return_value="0"):
        await judge_shell_command("ls")
    assert [record.component for record in read_records(directory=str(tmp_path))] == [
        COMPONENT_SHELL_JUDGE
    ]
