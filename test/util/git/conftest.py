"""Fixtures shared by the snapshot-store tests: a small repository and a
temporary store snapshotting it."""

import subprocess

import pytest

from zrb.util.git.snapshot_store import SnapshotStore


def _git(repo, *args) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A repository with one tracked file and `ignored.txt` in `.gitignore`."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tracked.txt").write_text("a\n")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


@pytest.fixture
def store(repo):
    """A temporary store over `repo`, deleted after the test."""
    snapshots = SnapshotStore.create_temporary(str(repo))
    yield snapshots
    snapshots.delete()
