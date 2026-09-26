"""Fixtures shared by the self-review gate's tests: a switched-on gate with a
replaced reviewer, a Stop event, and turn-start snapshots."""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.run.turn_snapshot import TurnSnapshot
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.types import HookEvent


@pytest.fixture
def start_snapshot():
    """Take a turn-start snapshot of a directory, as the runner puts it in the
    payload; every store it made is deleted after the test."""
    snapshots: list[TurnSnapshot] = []

    def take(workdir) -> dict:
        snapshot = TurnSnapshot()
        snapshot.take(str(workdir))
        snapshots.append(snapshot)
        payload = snapshot.payload()
        assert payload is not None
        return payload

    yield take
    for snapshot in snapshots:
        snapshot.close()


@pytest.fixture
def gate():
    """Switch the gate on and replace the reviewer; the context yields the
    inputs the reviewer saw and the inputs it was cancelled on."""
    return _gate


@pytest.fixture
def stop():
    """Fire a Stop event with the gate's payload fields."""
    return _stop


@pytest.fixture
def blocked():
    """The results among a Stop's that block it."""
    return _blocked


@contextmanager
def _gate(
    report="LGTM",
    success=True,
    enabled=True,
    max_rounds=2,
    builder=True,
    timeout=240,
    delay=0.0,
    max_tracked_turns=64,
):
    seen: list = []
    cancelled: list = []

    def build(config):
        async def reviewer(context):
            seen.append(context)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                cancelled.append(context)
                raise
            output = report.pop(0) if isinstance(report, list) else report
            return HookResult(success=success, output=output)

        return reviewer

    with (
        patch("zrb.llm.hook.self_review.CFG") as cfg,
        patch(
            "zrb.llm.hook.self_review.get_agent_hook_builder",
            return_value=build if builder else None,
        ),
    ):
        cfg.LLM_SELF_REVIEW_ENABLED = enabled
        cfg.LLM_SELF_REVIEW_MAX_ROUNDS = max_rounds
        cfg.LLM_SELF_REVIEW_MODEL = ""
        cfg.LLM_SELF_REVIEW_TIMEOUT = timeout
        cfg.LLM_SELF_REVIEW_MAX_TRACKED_TURNS = max_tracked_turns
        cfg.LLM_MAX_OUTPUT_CHARS = 100_000
        cfg.LOGGER = MagicMock()
        yield seen, cancelled


async def _stop(
    manager,
    changed_paths=("a.py",),
    stop_hook_active=False,
    turn_start_snapshot=None,
    run_scope="run-1",
    nested_run=False,
    turn_id=None,
):
    return await manager.execute_hooks(
        HookEvent.STOP,
        {
            "changed_paths": list(changed_paths),
            "wrote_files": bool(changed_paths),
            "turn_start_snapshot": turn_start_snapshot,
            "run_scope": run_scope,
            "nested_run": nested_run,
            "turn_id": turn_id,
        },
        stop_hook_active=stop_hook_active,
    )


def _blocked(results) -> list:
    return [r for r in results if r.blocked or r.decision == "block"]
