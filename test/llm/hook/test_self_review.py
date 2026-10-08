"The built-in self-review gate: registered only while switched on, blocks the"

import pytest

from zrb.llm.hook.manager import HookManager

_FINDINGS = "## Finding\n\n**Problem:** off by one.\n\nRequest changes"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verdict",
    ["Request changes", "**Request changes.**", "Verdict: **Request changes**"],
)
async def test_each_spelling_of_the_verdict_blocks(verdict, gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=f"## Finding\n\nProblem: x.\n\n{verdict}"):
        results = await stop(manager)

    assert len(blocked(results)) == 1


@pytest.mark.asyncio
async def test_request_changes_blocks_with_the_findings(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS):
        results = await stop(manager)

    blocked = blocked(results)
    assert len(blocked) == 1
    reason = blocked[0].reason
    assert reason.startswith("[SELF-REVIEW]")
    assert "off by one" in reason
    assert "complete final answer again" in reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report",
    ["Looks fine.\n\nLGTM", "**LGTM**", "Some notes but no verdict", ""],
)
async def test_anything_but_request_changes_lets_the_turn_end(
    report, gate, stop, blocked
):
    manager = HookManager(search_dirs=[])
    with gate(report=report):
        results = await stop(manager)

    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_turn_without_changed_files_is_not_reviewed(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS) as (seen, _):
        results = await stop(manager, changed_paths=())

    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_failed_review_never_blocks(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, success=False):
        results = await stop(manager)

    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_missing_reviewer_builder_never_blocks(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, builder=False) as (seen, _):
        results = await stop(manager)

    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_rounds_are_capped_per_turn_and_reset_on_the_next_turn(
    gate, stop, blocked
):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, max_rounds=2) as (seen, _):
        first = await stop(manager, stop_hook_active=False)
        second = await stop(manager, stop_hook_active=True)
        capped = await stop(manager, stop_hook_active=True)
        next_turn = await stop(manager, stop_hook_active=False)

    assert len(blocked(first)) == 1
    assert len(blocked(second)) == 1
    assert blocked(capped) == []
    assert len(blocked(next_turn)) == 1
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_disabled_gate_is_not_registered(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, enabled=False) as (seen, _):
        results = await stop(manager)

    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_review_past_its_timeout_is_cancelled_and_never_blocks(
    tmp_path, monkeypatch, gate, stop, blocked
):

    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, timeout=2, delay=30) as (seen, cancelled):
        results = await stop(manager)

    assert blocked(results) == []
    assert len(seen) == 1

    assert cancelled == seen


@pytest.mark.asyncio
async def test_a_delegated_sub_agent_run_is_not_reviewed(gate, stop, blocked):
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS) as (seen, _):
        results = await stop(manager, nested_run=True)

    assert seen == []
    assert blocked(results) == []


@pytest.mark.asyncio
async def test_a_review_that_lets_the_turn_end_clears_its_run_count(
    gate, stop, blocked
):
    "A run's count lives only while the gate holds its turn open, so a"
    manager = HookManager(search_dirs=[])
    reports = [_FINDINGS, "LGTM", _FINDINGS, _FINDINGS]
    with gate(report=reports, max_rounds=2):
        await stop(manager)
        await stop(manager, stop_hook_active=True)

        again = await stop(manager, stop_hook_active=True)
        still = await stop(manager, stop_hook_active=True)

    assert len(blocked(again)) == 1
    assert len(blocked(still)) == 1


@pytest.mark.asyncio
async def test_rounds_are_counted_per_run(gate, stop, blocked):
    "Concurrent sessions share one hook manager: one run's new turn must"
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, max_rounds=2) as (seen, _):
        await stop(manager, run_scope="a")
        await stop(manager, run_scope="a", stop_hook_active=True)
        other = await stop(manager, run_scope="b")
        capped = await stop(manager, run_scope="a", stop_hook_active=True)

    assert len(blocked(other)) == 1
    assert blocked(capped) == []
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_rounds_are_counted_per_turn_even_under_one_conversation_name(
    gate, stop, blocked
):
    "Two sessions under one conversation name share a run scope; the turn"
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, max_rounds=1) as (seen, _):
        await stop(manager, run_scope="shared", turn_id="a")
        other = await stop(manager, run_scope="shared", turn_id="b")
        capped = await stop(
            manager, run_scope="shared", turn_id="a", stop_hook_active=True
        )

    assert len(blocked(other)) == 1
    assert blocked(capped) == []
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_counts_of_turns_that_never_came_back_are_bounded(gate, stop, blocked):
    "A turn cancelled mid-continuation never clears its count; past"
    manager = HookManager(search_dirs=[])
    with gate(report=_FINDINGS, max_rounds=1, max_tracked_turns=3):
        for turn in range(4):
            await stop(manager, turn_id=f"t{turn}")
        first_again = await stop(manager, turn_id="t0", stop_hook_active=True)
        newest_again = await stop(manager, turn_id="t3", stop_hook_active=True)

    assert len(blocked(first_again)) == 1
    assert blocked(newest_again) == []
