"""Fixtures shared by the snapshot-store tests: a small repository and a
temporary store snapshotting it."""

import shutil
import subprocess

import pytest

from zrb.llm.snapshot.store import SnapshotStore


def _git(repo, *args) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture(scope="session")
def repo_template(tmp_path_factory):
    """The repository every test starts from, built once: seven `git` runs per
    test were a large part of what the snapshot tests spent."""
    template = tmp_path_factory.mktemp("repo-template")
    _git(template, "init", "-q")
    _git(template, "config", "user.email", "t@example.com")
    _git(template, "config", "user.name", "t")
    # No background `git maintenance` or auto-gc touching it mid-test.
    _git(template, "config", "maintenance.auto", "false")
    _git(template, "config", "gc.auto", "0")
    (template / "tracked.txt").write_text("a\n")
    (template / ".gitignore").write_text("ignored.txt\n")
    _git(template, "add", ".")
    _git(template, "commit", "-qm", "init")
    return template


@pytest.fixture
def repo(tmp_path, repo_template):
    """A repository with one tracked file and `ignored.txt` in `.gitignore`."""
    shutil.copytree(repo_template, tmp_path, dirs_exist_ok=True)
    return tmp_path


@pytest.fixture
def store(repo):
    """A temporary store over `repo`, deleted after the test."""
    snapshots = SnapshotStore.create_temporary(str(repo))
    yield snapshots
    snapshots.delete()
