"""Tests for SnapshotManager's `/save` copies recorded beside the store: a
record left behind after its copy landed must never overwrite the history
its target took since, nor be followed as a live copy."""

import json
import os
import tempfile
import threading

import pytest

from zrb.llm.snapshot import SnapshotManager
from zrb.util.file_lock import hold_file_lock


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def snapshot_dir():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield d


def _record_path(snapshot_dir) -> str:
    (store,) = [e.path for e in os.scandir(snapshot_dir) if e.name.endswith(".git")]
    return store[: -len(".git")] + ".copies.json"


def _leave_record_behind(snapshot_dir, target, source, target_before=""):
    """What a copy whose removal from the record failed leaves on disk."""
    with open(_record_path(snapshot_dir), "w", encoding="utf-8") as f:
        json.dump({target: {"source": source, "target_before": target_before}}, f)


def _labels(manager) -> list[str]:
    return [s.label for s in manager.list_snapshots()]


def _write(workdir, text):
    with open(os.path.join(workdir, "f.txt"), "w") as f:
        f.write(text)


async def _saved_then_worked_on(snapshot_dir, workdir) -> SnapshotManager:
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)
    await mgr.copy_history("draft", "final")
    mgr.session_name = "final"
    _write(workdir, "newer")
    await mgr.take_snapshot("newer in final", message_count=2)
    return mgr


@pytest.mark.asyncio
async def test_a_record_left_behind_never_overwrites_the_targets_newer_history(
    snapshot_dir, workdir
):
    await _saved_then_worked_on(snapshot_dir, workdir)
    _leave_record_behind(snapshot_dir, "final", "draft")

    later = SnapshotManager(snapshot_dir, "final", workdir)
    _write(workdir, "next")
    await later.take_snapshot("next session", message_count=3)

    assert _labels(later) == ["next session", "newer in final", "in draft"]
    assert not os.path.exists(_record_path(snapshot_dir))  # forgotten


@pytest.mark.asyncio
async def test_a_record_that_cannot_be_removed_leaves_this_sessions_turns_alone(
    snapshot_dir, workdir, monkeypatch
):
    """While the record stays locked by another process, every operation
    meets the stale entry again; none may reset the target, and the list
    shows the target's own history."""
    mgr = await _saved_then_worked_on(snapshot_dir, workdir)
    _leave_record_behind(snapshot_dir, "final", "draft")
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_COPY_LOCK_TIMEOUT", "0.05")
    held, release = threading.Event(), threading.Event()

    def other_process():
        with hold_file_lock(_record_path(snapshot_dir) + ".lock"):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=other_process)
    thread.start()
    held.wait(5)
    try:
        for turn in range(2):
            _write(workdir, f"turn {turn}")
            await mgr.take_snapshot(f"turn {turn}", message_count=3 + turn)
        labels = _labels(mgr)
    finally:
        release.set()
        thread.join(5)

    assert labels == ["turn 1", "turn 0", "newer in final", "in draft"]


@pytest.mark.asyncio
async def test_a_copy_of_a_conversation_with_a_stale_record_takes_its_own_history(
    snapshot_dir, workdir
):
    """`/save final2` from final must copy final's history, not follow a
    record of an old copy into final back to draft."""
    mgr = await _saved_then_worked_on(snapshot_dir, workdir)
    _leave_record_behind(snapshot_dir, "final", "draft")

    await mgr.copy_history("final", "final2")

    later = SnapshotManager(snapshot_dir, "final2", workdir)
    assert _labels(later) == ["newer in final", "in draft"]


@pytest.mark.asyncio
async def test_a_record_the_target_has_not_moved_from_is_still_replayed(
    snapshot_dir, workdir
):
    """The head check refuses only a copy that landed: one a session never
    applied — its target still where it was — lands at the next session."""
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)
    _leave_record_behind(snapshot_dir, "final", "draft")  # final has no history

    later = SnapshotManager(snapshot_dir, "final", workdir)
    assert _labels(later) == ["in draft"]
    await later.take_snapshot("resumed", message_count=2)

    assert _labels(later) == ["resumed", "in draft"]


@pytest.mark.asyncio
async def test_a_record_without_the_targets_head_is_never_replayed(
    snapshot_dir, workdir
):
    """An entry that cannot say which head it was recorded against cannot be
    replayed safely, so it is skipped rather than guessed at."""
    mgr = await _saved_then_worked_on(snapshot_dir, workdir)
    with open(_record_path(snapshot_dir), "w", encoding="utf-8") as f:
        json.dump({"final": "draft"}, f)

    await mgr.take_snapshot("later", message_count=3)

    assert _labels(mgr) == ["later", "newer in final", "in draft"]


@pytest.mark.asyncio
async def test_a_snapshot_right_after_save_in_the_same_task_builds_on_the_copy(
    snapshot_dir, workdir
):
    """The copy is registered when `copy_history` is called, so a turn the
    caller starts before its task ever runs — without yielding in between —
    applies it first instead of being overwritten by it."""
    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)

    copy = mgr.copy_history("draft", "final")  # `/save final`, not yet run
    mgr.session_name = "final"
    _write(workdir, "turn")
    await mgr.take_snapshot("turn after save", message_count=2)
    await copy

    assert _labels(mgr) == ["turn after save", "in draft"]
    # The copy landed before it could be recorded, so no record carries a
    # head that would let a replay reach the turn.
    assert not os.path.exists(_record_path(snapshot_dir))
    later = SnapshotManager(snapshot_dir, "final", workdir)
    await later.take_snapshot("next session", message_count=3)
    assert _labels(later) == ["next session", "turn after save", "in draft"]


@pytest.mark.asyncio
async def test_a_copy_whose_target_head_cannot_be_read_still_lands_unrecorded(
    snapshot_dir, workdir, monkeypatch
):
    from zrb.util.git.snapshot_command import SnapshotError
    from zrb.util.git.snapshot_store import SnapshotStore

    mgr = SnapshotManager(snapshot_dir, "draft", workdir)
    await mgr.take_snapshot("in draft", message_count=1)
    real_run_git = SnapshotStore.run_git
    failures = []

    def fail_the_first_head_read(self, args, *rest, **kwargs):
        if args[0] == "rev-parse" and not failures:
            failures.append(args)
            raise SnapshotError("transient")
        return real_run_git(self, args, *rest, **kwargs)

    monkeypatch.setattr(SnapshotStore, "run_git", fail_the_first_head_read)
    await mgr.copy_history("draft", "final")
    monkeypatch.undo()

    assert failures
    mgr.session_name = "final"
    assert _labels(mgr) == ["in draft"]
    assert not os.path.exists(_record_path(snapshot_dir))


@pytest.mark.asyncio
async def test_copies_land_in_the_order_they_were_registered(snapshot_dir, workdir):
    """`/save b` then `/save c` from b: c takes a's history even when its
    coroutine runs first, since the copy it copies lands before it."""
    mgr = SnapshotManager(snapshot_dir, "a", workdir)
    await mgr.take_snapshot("in a", message_count=1)

    to_b = mgr.copy_history("a", "b")
    to_c = mgr.copy_history("b", "c")
    await to_c
    await to_b

    mgr.session_name = "c"
    assert _labels(mgr) == ["in a"]


@pytest.mark.asyncio
async def test_saving_over_a_name_a_pending_copy_depends_on_keeps_that_copy(
    snapshot_dir, workdir
):
    """`/save b`, `/save c` from b, then `/save b` again from x, before any
    lands: c must still get a's history, not b's replaced state."""
    first = SnapshotManager(snapshot_dir, "a", workdir)
    await first.take_snapshot("in a", message_count=1)
    _write(workdir, "x")
    await SnapshotManager(snapshot_dir, "x", workdir).take_snapshot("in x", 1)
    mgr = SnapshotManager(snapshot_dir, "a", workdir)

    copies = [
        mgr.copy_history("a", "b"),
        mgr.copy_history("b", "c"),
        mgr.copy_history("x", "b"),
    ]
    for copy in copies:
        await copy

    mgr.session_name = "b"
    assert _labels(mgr) == ["in x"]
    mgr.session_name = "c"
    assert _labels(mgr) == ["in a"]
