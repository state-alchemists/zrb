"""Fixtures shared by the self-review gate's tests: a switched-on gate with a
replaced reviewer, a Stop event, and turn-start snapshots."""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.types import HookEvent
from zrb.util.git.snapshot_store import SnapshotStore


@pytest.fixture
def start_snapshot():
    """Take a turn-start snapshot of a directory, as the runner puts it in the
    payload; every store it made is deleted after the test."""
    stores: list[SnapshotStore] = []

    def take(workdir) -> dict:
        store = SnapshotStore.create_temporary(str(workdir))
        stores.append(store)
        tree = store.snapshot().tree
        return {"workdir": store.work_tree, "tree": tree, "store": store.git_dir}

    yield take
    for store in stores:
        store.delete()


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
):
    return await manager.execute_hooks(
        HookEvent.STOP,
        {
            "changed_paths": list(changed_paths),
            "wrote_files": bool(changed_paths),
            "turn_start_snapshot": turn_start_snapshot,
            "run_scope": run_scope,
            "nested_run": nested_run,
        },
        stop_hook_active=stop_hook_active,
    )


def _blocked(results) -> list:
    return [r for r in results if r.blocked or r.decision == "block"]
