"""The self-review gate's turn-start snapshot of the working directory."""

import os
import subprocess

import pytest

from zrb.llm.agent.run.turn_snapshot import TurnSnapshot
from zrb.util.git.snapshot_store import SnapshotStore


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "f.txt").write_text("x\n")
    return path


def test_a_snapshot_covers_the_working_directory_and_its_store_is_deleted(
    tmp_path,
):
    workdir = _repo(tmp_path / "main")
    snapshot = TurnSnapshot()

    snapshot.take(str(workdir))
    payload = snapshot.payload()
    snapshot.close()

    assert payload is not None
    assert payload["workdir"] == os.path.realpath(workdir)
    assert payload["tree"]
    assert not os.path.exists(payload["store"])
    assert snapshot.payload() is None


def test_a_store_that_fails_to_set_up_is_deleted_and_the_turn_goes_on(
    tmp_path, monkeypatch
):
    workdir = _repo(tmp_path / "main")
    created: list[str] = []
    real_create = SnapshotStore.create_temporary

    def create(workdir):
        store = real_create(workdir)
        created.append(store.git_dir)
        return store

    def fail(store, deadline=None):
        raise PermissionError("chmod refused")

    monkeypatch.setattr(SnapshotStore, "create_temporary", create)
    monkeypatch.setattr(SnapshotStore, "snapshot", fail)
    snapshot = TurnSnapshot()

    snapshot.take(str(workdir))

    assert snapshot.payload() is None
    assert len(created) == 1 and not os.path.exists(created[0])


def test_a_directory_over_the_budget_is_reported_once(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES", "1")
    workdir = tmp_path / "loose"
    workdir.mkdir()
    (workdir / "a.txt").write_text("a\n")
    (workdir / "b.txt").write_text("b\n")

    with caplog.at_level("WARNING", logger="zrb.llm.agent.run.turn_snapshot"):
        for _ in range(2):
            snapshot = TurnSnapshot()
            snapshot.take(str(workdir))
            assert snapshot.payload() is None

    assert caplog.text.count("more than 1 files outside any git repository") == 1


def test_a_directory_too_large_to_snapshot_in_time_is_not_tried_again(
    tmp_path, monkeypatch
):
    workdir = _repo(tmp_path / "huge")
    calls: list = []
    real_run = subprocess.run

    def run(argv, *args, **kwargs):
        calls.append(argv)
        if "update-index" in argv:
            raise subprocess.TimeoutExpired(argv, 30)
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    TurnSnapshot().take(str(workdir))
    tried = len(calls)

    snapshot = TurnSnapshot()
    snapshot.take(str(workdir))

    assert snapshot.payload() is None
    assert len(calls) == tried
