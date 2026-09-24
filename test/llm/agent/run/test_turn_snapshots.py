"""The registry of roots one turn has snapshotted for the self-review gate."""

import os
import subprocess

import pytest

from zrb.llm.agent.run.turn_snapshots import TurnSnapshots
from zrb.llm.permission import Capability
from zrb.util.git.snapshot_store import SnapshotStore


def _repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "f.txt").write_text("x\n")
    return path


@pytest.fixture
def snapshots():
    registry = TurnSnapshots()
    yield registry
    registry.close()


def _roots(registry: TurnSnapshots) -> list[str]:
    return [entry["workdir"] for entry in registry.payload()]


def test_the_working_directory_covers_its_whole_repository(tmp_path, snapshots):
    repo = _repo(tmp_path / "repo")
    (repo / "sub").mkdir()

    snapshots.cover_workdir(str(repo / "sub"))

    assert _roots(snapshots) == [os.path.realpath(repo)]


def test_a_shell_in_another_repository_snapshots_it_first(tmp_path, snapshots):
    main, other = _repo(tmp_path / "main"), _repo(tmp_path / "other")
    snapshots.cover_workdir(str(main))

    snapshots.cover_tool_call(Capability.EXECUTE, {"cwd": str(other)})
    snapshots.cover_tool_call(Capability.EXECUTE, {"cwd": str(other)})  # once

    assert _roots(snapshots) == [os.path.realpath(main), os.path.realpath(other)]


def test_a_worktree_inside_the_repository_is_its_own_root(tmp_path, snapshots):
    main = _repo(tmp_path / "main")
    subprocess.run(["git", "add", "."], cwd=main, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "i"],
        cwd=main,
        check=True,
    )
    worktree = main / ".zrb" / "worktree" / "feat"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "feat", str(worktree)],
        cwd=main,
        check=True,
    )
    snapshots.cover_workdir(str(main))

    # A file the tool is about to create: its nearest existing directory counts.
    snapshots.cover_tool_call(Capability.EDIT, {"path": str(worktree / "new" / "a.py")})

    assert _roots(snapshots) == [os.path.realpath(main), os.path.realpath(worktree)]


def test_reads_and_paths_in_covered_roots_add_nothing(tmp_path, snapshots):
    main, other = _repo(tmp_path / "main"), _repo(tmp_path / "other")
    snapshots.cover_workdir(str(main))

    snapshots.cover_tool_call(Capability.READ, {"path": str(other / "f.txt")})
    snapshots.cover_tool_call(Capability.EDIT, {"path": str(main / "f.txt")})

    assert _roots(snapshots) == [os.path.realpath(main)]


def test_a_directory_outside_every_repository_is_not_snapshotted(
    tmp_path, snapshots, monkeypatch
):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    main = _repo(tmp_path / "main")
    loose = tmp_path / "loose"
    loose.mkdir()
    snapshots.cover_workdir(str(main))

    snapshots.cover_tool_call(Capability.EXECUTE, {"cwd": str(loose)})

    assert _roots(snapshots) == [os.path.realpath(main)]


def test_closing_deletes_every_store_and_refuses_new_ones(tmp_path):
    main, other = _repo(tmp_path / "main"), _repo(tmp_path / "other")
    registry = TurnSnapshots()
    registry.cover_workdir(str(main))
    stores = [entry["store"] for entry in registry.payload()]

    registry.close()
    registry.cover_tool_call(Capability.EXECUTE, {"cwd": str(other)})

    assert registry.payload() == []
    assert not any(os.path.exists(store) for store in stores)


def test_a_store_that_fails_to_set_up_is_deleted_and_the_turn_goes_on(
    tmp_path, snapshots, monkeypatch
):
    main = _repo(tmp_path / "main")
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

    snapshots.cover_workdir(str(main))

    assert snapshots.payload() == []
    assert len(created) == 1 and not os.path.exists(created[0])
