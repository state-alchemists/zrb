"""The built-in self-review gate: registered only while switched on, blocks the
Stop on a `Request changes` verdict, and never blocks on anything else."""

import asyncio
import subprocess
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.util.git.snapshot_store import SnapshotStore


@pytest.fixture
def store():
    """The temporary stores a test snapshots into, deleted afterwards."""
    stores: list[SnapshotStore] = []
    yield stores
    for snapshots in stores:
        snapshots.delete()


def _start_snapshot(workdir, stores: list) -> dict:
    """A turn-start snapshot of *workdir*, as the runner puts it in the payload."""
    snapshots = SnapshotStore.create_temporary(str(workdir))
    stores.append(snapshots)
    tree, _ = snapshots.snapshot()
    return {"tree": tree, "store": snapshots.git_dir}


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
async def test_without_a_turn_start_snapshot_only_the_paths_are_reviewed(
    tmp_path, monkeypatch
):
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

    # The reviewer gets a request, not the transcript — and no diff against
    # HEAD, which would carry the user's uncommitted work from before the turn.
    request = seen[0].event_data
    assert isinstance(request, str)
    assert "- a.py" in request and "- new.py" in request
    assert "x = 2" not in request
    assert "No diff of this turn's changes is available." in request
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
    before = _start_snapshot(tmp_path, store)
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
    before = _start_snapshot(tmp_path, store)
    manager = HookManager(search_dirs=[])

    with _gate(report=_FINDINGS) as (seen, _):
        results = await _stop(manager, changed_paths=(), turn_start_snapshot=before)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_review_past_its_timeout_is_cancelled_and_never_blocks(
    tmp_path, monkeypatch
):
    # Outside a repository the scope's one git command fails fast; the
    # timeout leaves it ample room so the deadline lands on the reviewer.
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, timeout=2, delay=30) as (seen, cancelled):
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
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    before = _start_snapshot(tmp_path, store)
    real_run = subprocess.run
    timeouts: list[float] = []

    def hanging_git(args, *rest, timeout=None, **kwargs):
        # Every git command from here on hangs until its own timeout — not a
        # fake binary on PATH, which a noexec temp dir would skip.
        if args[0] != "git":
            return real_run(args, *rest, timeout=timeout, **kwargs)
        timeouts.append(timeout)
        time.sleep(timeout)
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(subprocess, "run", hanging_git)
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])

    with _gate(report=_FINDINGS, timeout=1) as (seen, _):
        started = time.monotonic()
        results = await _stop(manager, turn_start_snapshot=before)
        elapsed = time.monotonic() - started

    assert elapsed < 5
    # Each command got only the time left before the deadline, not 30s.
    assert timeouts and max(timeouts) <= 1
    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_a_delegated_sub_agent_run_is_not_reviewed():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS) as (seen, _):
        results = await _stop(manager, nested_run=True)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_rounds_are_counted_per_run():
    """Concurrent sessions share one hook manager: one run's new turn must
    not reset another run's round count."""
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, max_rounds=2) as (seen, _):
        await _stop(manager, run_scope="a")
        await _stop(manager, run_scope="a", stop_hook_active=True)  # a at its cap
        other = await _stop(manager, run_scope="b")  # b's first Stop
        capped = await _stop(manager, run_scope="a", stop_hook_active=True)

    assert len(_blocked(other)) == 1
    assert _blocked(capped) == []
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_a_tool_path_under_home_matches_its_tree_path(
    tmp_path, monkeypatch, store
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    before = _start_snapshot(tmp_path, store)
    (tmp_path / "a.py").write_text("x = 1\n")
    manager = HookManager(search_dirs=[])

    with _gate() as (seen, _):
        await _stop(manager, changed_paths=("~/a.py",), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a.py" in request
    assert "- ~/a.py" not in request


@pytest.mark.asyncio
async def test_outside_git_the_review_still_gets_the_turns_diff(
    tmp_path, monkeypatch, store
):
    """The store's work tree is the directory itself when there is no
    repository, so a shell command's edit is still diffed."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    workdir = tmp_path / "project"
    workdir.mkdir()
    (workdir / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(workdir)
    before = _start_snapshot(workdir, store)
    (workdir / "a.py").write_text("x = 2\n")  # through a shell command
    manager = HookManager(search_dirs=[])

    with _gate() as (seen, _):
        await _stop(manager, changed_paths=(), turn_start_snapshot=before)

    request = seen[0].event_data
    assert "- a.py" in request and "+x = 2" in request
    assert "Diff against the start of this turn" in request
