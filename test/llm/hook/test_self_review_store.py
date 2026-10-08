"The self-review gate's own store: it only reads the turn's store, which"

import asyncio
import os
import subprocess
import tempfile
import threading

import pytest

from zrb.llm.hook.manager import HookManager


def _contents(directory: str) -> dict[str, bytes]:
    found = {}
    for root, _dirs, files in os.walk(directory):
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as f:
                found[os.path.relpath(path, directory)] = f.read()
    return found


def _temporary_stores() -> set[str]:
    temp = tempfile.gettempdir()
    return {name for name in os.listdir(temp) if name.startswith("zrb-snapshot-")}


@pytest.fixture
def own_temp_dir(tmp_path_factory, monkeypatch):
    "A temp directory only this test's stores land in — other tests running"
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path_factory.mktemp("temp")))


@pytest.mark.asyncio
async def test_a_review_only_reads_the_turn_store_and_leaves_nothing_behind(
    tmp_path, monkeypatch, own_temp_dir, start_snapshot, gate, stop
):
    "The runner deletes the turn-start store when the turn ends — also"
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    before = start_snapshot(tmp_path)
    turn_store = _contents(before["store"])
    stores = _temporary_stores()
    (tmp_path / "a.py").write_text("x = 2\n")
    (tmp_path / "new.txt").write_text("untracked\n")
    manager = HookManager(search_dirs=[])

    with gate() as (seen, _):
        await stop(manager, changed_paths=(), turn_start_snapshot=before)

    assert "+x = 2" in seen[0].event_data
    assert _contents(before["store"]) == turn_store
    assert _temporary_stores() == stores


@pytest.mark.asyncio
async def test_a_cancelled_review_stops_its_git_work_and_cleans_up(
    tmp_path, monkeypatch, own_temp_dir, start_snapshot, gate, stop
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    before = start_snapshot(tmp_path)
    stores = _temporary_stores()
    real_run = subprocess.run
    running, release = threading.Event(), threading.Event()
    after_cancel: list = []

    def git_held_once(args, *rest, **kwargs):
        if args[0] == "git" and not running.is_set():
            running.set()
            release.wait(5)
        elif args[0] == "git" and release.is_set():
            after_cancel.append(args)
        return real_run(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "run", git_held_once)
    monkeypatch.chdir(tmp_path)
    manager = HookManager(search_dirs=[])

    with gate():
        review = asyncio.ensure_future(stop(manager, turn_start_snapshot=before))
        assert await asyncio.to_thread(running.wait, 5)
        review.cancel()
        await asyncio.sleep(0.2)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await review
        for _ in range(50):
            if _temporary_stores() == stores:
                break
            await asyncio.sleep(0.1)

    assert after_cancel == []
    assert _temporary_stores() == stores
