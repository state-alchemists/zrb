"""The built-in self-review gate: registered only while switched on, blocks the
Stop on a `Request changes` verdict, and never blocks on anything else."""

import asyncio
import os
import subprocess
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.util.git.worktree import (
    create_snapshot_store,
    delete_snapshot_store,
    snapshot_worktree,
)


@pytest.fixture
def store():
    path = create_snapshot_store()
    yield path
    delete_snapshot_store(path)


_FINDINGS = "## Finding\n\n**Problem:** off by one.\n\nRequest changes"


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
    """Switch the gate on and replace the reviewer; yields the inputs it saw
    and the inputs it was cancelled on."""
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
            return HookResult(success=success, output=report)

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
    manager, changed_paths=("a.py",), stop_hook_active=False, turn_start_snapshot=None
):
    return await manager.execute_hooks(
        HookEvent.STOP,
        {
            "changed_paths": list(changed_paths),
            "wrote_files": bool(changed_paths),
            "turn_start_snapshot": turn_start_snapshot,
        },
        stop_hook_active=stop_hook_active,
    )


def _blocked(results) -> list:
    return [r for r in results if r.blocked or r.decision == "block"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verdict",
    ["Request changes", "**Request changes.**", "Verdict: **Request changes**"],
)
async def test_each_spelling_of_the_verdict_blocks(verdict):
    manager = HookManager(search_dirs=[])
    with _gate(report=f"## Finding\n\nProblem: x.\n\n{verdict}"):
        results = await _stop(manager)

    assert len(_blocked(results)) == 1


@pytest.mark.asyncio
async def test_request_changes_blocks_with_the_findings():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS):
        results = await _stop(manager)

    blocked = _blocked(results)
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
async def test_anything_but_request_changes_lets_the_turn_end(report):
    manager = HookManager(search_dirs=[])
    with _gate(report=report):
        results = await _stop(manager)

    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_turn_without_changed_files_is_not_reviewed():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS) as (seen, _):
        results = await _stop(manager, changed_paths=())

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_failed_review_never_blocks():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, success=False):
        results = await _stop(manager)

    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_missing_reviewer_builder_never_blocks():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, builder=False) as (seen, _):
        results = await _stop(manager)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_rounds_are_capped_per_turn_and_reset_on_the_next_turn():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, max_rounds=2) as (seen, _):
        first = await _stop(manager, stop_hook_active=False)
        second = await _stop(manager, stop_hook_active=True)
        capped = await _stop(manager, stop_hook_active=True)
        next_turn = await _stop(manager, stop_hook_active=False)

    assert len(_blocked(first)) == 1
    assert len(_blocked(second)) == 1
    assert _blocked(capped) == []
    assert len(_blocked(next_turn)) == 1
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_disabled_gate_is_not_registered():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, enabled=False) as (seen, _):
        results = await _stop(manager)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_reviewer_gets_the_diff_not_the_transcript(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", "a.py")
    git("commit", "-qm", "init")
    (tmp_path / "a.py").write_text("x = 2\n")
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])

    with _gate() as (seen, _):
        await _stop(manager, changed_paths=("a.py", "new.py"))

    request = seen[0].event_data
    assert isinstance(request, str)
    assert "- a.py" in request and "- new.py" in request
    assert "+x = 2" in request
    assert "read it directly" in request


@pytest.mark.asyncio
async def test_turn_start_snapshot_scopes_the_review_to_this_turn(
    tmp_path, monkeypatch, store
):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    git("add", ".")
    git("commit", "-qm", "init")
    (tmp_path / "a.py").write_text("x = 1\nuser_wip = True\n")
    monkeypatch.chdir(tmp_path)
    before = {"tree": snapshot_worktree(str(tmp_path), store), "store": store}
    # A shell command's edit: no file tool names it.
    (tmp_path / "gen.py").write_text("y = 2\n")
    # A file tool's edit git ignores.
    (tmp_path / "ignored.txt").write_text("z\n")
    manager = HookManager(search_dirs=[])

    with _gate() as (seen, _):
        await _stop(manager, changed_paths=("ignored.txt",), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- gen.py" in request and "+y = 2" in request
    assert "- ignored.txt" in request
    assert "Diff against the start of this turn" in request
    assert "- a.py" not in request and "user_wip" not in request


@pytest.mark.asyncio
async def test_a_turn_with_no_changes_since_its_start_is_not_reviewed(
    tmp_path, monkeypatch, store
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    before = {"tree": snapshot_worktree(str(tmp_path), store), "store": store}
    manager = HookManager(search_dirs=[])

    with _gate(report=_FINDINGS) as (seen, _):
        results = await _stop(manager, changed_paths=(), turn_start_snapshot=before)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_review_past_its_timeout_is_cancelled_and_never_blocks():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, timeout=0.05, delay=30) as (seen, cancelled):
        results = await _stop(manager)

    assert _blocked(results) == []
    assert len(seen) == 1
    # Cancelled inside the hook's own event loop, so the model request stops
    # instead of running on in an abandoned worker thread.
    assert cancelled == seen


@pytest.mark.asyncio
async def test_slow_git_cannot_stretch_a_review_past_its_timeout(
    tmp_path, monkeypatch, store
):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    before = {"tree": snapshot_worktree(str(repo), store), "store": store}
    # From here on every git command hangs; `exec` makes the timeout kill the
    # sleep itself rather than a shell around it.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nexec sleep 30\n")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(repo)
    manager = HookManager(search_dirs=[])

    with _gate(report=_FINDINGS, timeout=1) as (seen, _):
        started = time.monotonic()
        results = await _stop(manager, turn_start_snapshot=before)
        elapsed = time.monotonic() - started

    assert elapsed < 5
    assert seen == []
    assert _blocked(results) == []
