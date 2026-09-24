"""The built-in self-review gate: registered only while switched on, blocks the
Stop on a `Request changes` verdict, and never blocks on anything else."""

import subprocess
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent

_FINDINGS = "## Finding\n\n**Problem:** off by one.\n\nRequest changes"


@contextmanager
def _gate(report="LGTM", success=True, enabled=True, max_rounds=2, builder=True):
    """Switch the gate on and replace the reviewer; yields the inputs it saw."""
    seen: list = []

    def build(config):
        async def reviewer(context):
            seen.append(context)
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
        cfg.LLM_MAX_OUTPUT_CHARS = 100_000
        cfg.LOGGER = MagicMock()
        yield seen


async def _stop(
    manager, changed_paths=("a.py",), stop_hook_active=False, turn_start_tree=None
):
    return await manager.execute_hooks(
        HookEvent.STOP,
        {
            "changed_paths": list(changed_paths),
            "wrote_files": bool(changed_paths),
            "turn_start_tree": turn_start_tree,
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
    with _gate(report=_FINDINGS) as seen:
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
    with _gate(report=_FINDINGS, builder=False) as seen:
        results = await _stop(manager)

    assert seen == []
    assert _blocked(results) == []


@pytest.mark.asyncio
async def test_rounds_are_capped_per_turn_and_reset_on_the_next_turn():
    manager = HookManager(search_dirs=[])
    with _gate(report=_FINDINGS, max_rounds=2) as seen:
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
    with _gate(report=_FINDINGS, enabled=False) as seen:
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

    with _gate() as seen:
        await _stop(manager, changed_paths=("a.py", "new.py"))

    request = seen[0].event_data
    assert isinstance(request, str)
    assert "- a.py" in request and "- new.py" in request
    assert "+x = 2" in request
    assert "read it directly" in request


@pytest.mark.asyncio
async def test_turn_start_tree_scopes_the_review_to_this_turn(tmp_path, monkeypatch):
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
    from zrb.util.git.worktree import snapshot_worktree

    before = snapshot_worktree(str(tmp_path))
    # A shell command's edit: no file tool names it.
    (tmp_path / "gen.py").write_text("y = 2\n")
    # A file tool's edit git ignores.
    (tmp_path / "ignored.txt").write_text("z\n")
    manager = HookManager(search_dirs=[])

    with _gate() as seen:
        await _stop(manager, changed_paths=("ignored.txt",), turn_start_tree=before)

    request = seen[0].event_data
    assert "- gen.py" in request and "+y = 2" in request
    assert "- ignored.txt" in request
    assert "Diff against the start of this turn" in request
    assert "- a.py" not in request and "user_wip" not in request


@pytest.mark.asyncio
async def test_a_turn_with_no_changes_since_its_start_is_not_reviewed(
    tmp_path, monkeypatch
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    from zrb.util.git.worktree import snapshot_worktree

    before = snapshot_worktree(str(tmp_path))
    manager = HookManager(search_dirs=[])

    with _gate(report=_FINDINGS) as seen:
        results = await _stop(manager, changed_paths=(), turn_start_tree=before)

    assert seen == []
    assert _blocked(results) == []
