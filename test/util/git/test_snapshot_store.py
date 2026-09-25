"""SnapshotStore: snapshot a directory as git trees, diff exactly what changed
between two moments, and restore one — nested repositories included — without
writing anything into any repository."""

import os
import subprocess
import time

import pytest

from zrb.util.git.snapshot_command import SnapshotError
from zrb.util.git.snapshot_store import SnapshotStore


def _git(repo, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


def _loose_objects(repo) -> set[str]:
    objects = repo / ".git" / "objects"
    return {
        str(path.relative_to(objects))
        for path in objects.rglob("*")
        if path.is_file() and path.parent.name not in ("pack", "info")
    }


@pytest.fixture(autouse=True)
def _no_enclosing_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _nested(path, files: dict[str, str]):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    for name, content in files.items():
        # Bytes: `write_text` adds CRLF on Windows, where `core.autocrlf`
        # then commits a different blob than the file's bytes.
        (path / name).write_bytes(content.encode())
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "init")
    return path


def _snap(store: SnapshotStore) -> str:
    return store.snapshot().tree


def test_diff_covers_only_what_changed_between_snapshots(repo, store):
    (repo / "tracked.txt").write_text("a\nuser wip\n")  # before the turn
    before = _snap(store)

    (repo / "created.txt").write_text("new\n")  # e.g. written by a shell command
    (repo / "tracked.txt").write_text("A\nuser wip\n")
    _git(repo, "commit", "-qam", "committed mid-turn")
    (repo / "ignored.txt").write_text("secret\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    paths, diff = changed
    assert sorted(paths) == ["created.txt", "tracked.txt"]
    assert "+A" in diff and "-a" in diff
    changed_lines = [line[1:] for line in diff.splitlines() if line[:1] in "+-"]
    assert "user wip" not in changed_lines


def test_diff_covers_a_file_deleted_from_the_working_tree(repo, store):
    # A file present at turn start is in the start tree, so its removal
    # shows as a deletion.
    before = _snap(store)

    (repo / "tracked.txt").unlink()  # e.g. `rm` through a shell command
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    paths, diff = changed
    assert paths == ["tracked.txt"]
    assert "deleted file mode" in diff and "-a" in diff


def test_snapshot_writes_nothing_into_the_repository(repo, store):
    (repo / ".env.local").write_text("AWS_SECRET=hunter2\n")  # untracked secret
    objects_before = _loose_objects(repo)

    tree = _snap(store)

    assert tree
    assert _loose_objects(repo) == objects_before
    secret_blob = _git(repo, "hash-object", ".env.local").stdout.strip()
    assert _git(repo, "cat-file", "-e", secret_blob, check=False).returncode != 0
    assert _git(repo, "status", "--porcelain").stdout.splitlines() == ["?? .env.local"]


def test_outside_a_repository_the_directory_itself_is_snapshotted(tmp_path):
    workdir = tmp_path / "project"
    (workdir / "node_modules").mkdir(parents=True)
    (workdir / "a.txt").write_text("a\n")
    store = SnapshotStore.create_temporary(str(workdir))
    try:
        before = _snap(store)
        (workdir / "a.txt").write_text("b\n")
        (workdir / "node_modules" / "dep.js").write_text("x\n")
        after = _snap(store)

        assert store.work_tree == os.path.realpath(workdir)
        assert store.diff(before, after)[0] == ["a.txt"]
    finally:
        store.delete()


def test_a_passed_deadline_runs_no_git_command(repo, store):
    before = _snap(store)
    past = time.monotonic() - 1

    with pytest.raises(SnapshotError):
        store.snapshot(past)
    with pytest.raises(SnapshotError):
        store.diff(before, before, past)


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_unreadable_file_is_left_out_instead_of_failing_the_snapshot(repo, store):
    secret = repo / "secret.key"
    secret.write_text("protected\n")
    secret.chmod(0)
    try:
        before = _snap(store)
        (repo / "tracked.txt").write_text("changed\n")
        after = _snap(store)
    finally:
        secret.chmod(0o600)

    assert before and after
    changed = store.diff(before, after)
    assert changed[0] == ["tracked.txt"]


def test_file_ignored_mid_turn_leaves_later_snapshots(repo, store):
    (repo / " late.txt").write_text("v1\n")  # leading space: -z paths unstripped
    before = _snap(store)
    (repo / ".gitignore").write_text("ignored.txt\n late.txt\n")
    first = _snap(store)
    (repo / " late.txt").write_text("v2\n")
    second = _snap(store)

    assert before and first and second
    assert store.diff(first, second) == ([], "")


def test_changed_paths_are_exact_for_unusual_names(repo, store):
    names = ["café.txt", " lead.txt", "tab\there.txt", 'quo"te.txt']
    if os.name == "nt":
        names = names[:2]
    before = _snap(store)
    for name in names:
        (repo / name).write_text("x\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert sorted(changed[0]) == sorted(names)


def test_a_rename_lists_both_its_old_and_new_path(repo, store):
    before = _snap(store)
    (repo / "tracked.txt").rename(repo / "moved.txt")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert sorted(changed[0]) == ["moved.txt", "tracked.txt"]


def test_non_utf8_content_does_not_break_a_diff(repo, store):
    before = _snap(store)
    (repo / "latin.txt").write_bytes(b"caf\xe9\n")
    after = _snap(store)

    paths, diff = store.diff(before, after)
    assert paths == ["latin.txt"]
    assert "caf\ufffd" in diff


@pytest.mark.skipif(os.name != "posix", reason="non-UTF-8 file names are POSIX-only")
def test_a_non_utf8_file_name_survives_a_snapshot(repo, store):
    raw_name = os.path.join(os.fsencode(str(repo)), b"latin\xe9.txt")
    try:
        with open(raw_name, "wb") as f:
            f.write(b"x\n")
    except OSError:
        # macOS (APFS) refuses a name that is not valid UTF-8 outright, so the
        # case cannot arise there.
        pytest.skip("this filesystem rejects non-UTF-8 file names")
    os.remove(raw_name)
    before = _snap(store)
    with open(raw_name, "wb") as f:
        f.write(b"x\n")
    after = _snap(store)

    paths, _ = store.diff(before, after)
    assert [os.fsencode(p) for p in paths] == [b"latin\xe9.txt"]


def test_the_diff_ignores_the_users_external_diff_and_colour(repo, store):
    _git(repo, "config", "diff.external", "false")
    _git(repo, "config", "color.ui", "always")
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert "-a\n+b" in changed[1]
    assert "\x1b[" not in changed[1]


def test_a_store_inside_the_repository_is_not_snapshotted(repo):
    store = SnapshotStore(str(repo / "tmp-store"), str(repo), borrow_objects=True)
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert before and after
    changed = store.diff(before, after)
    assert changed[0] == ["tracked.txt"]


def test_the_repositorys_own_info_exclude_applies(repo, store):
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_text("local-notes.txt\n")
    before = _snap(store)
    (repo / "local-notes.txt").write_text("private\n")
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert store.diff(before, after)[0] == ["tracked.txt"]


def test_inherited_git_variables_cannot_redirect_a_snapshot(repo, store, monkeypatch):
    # e.g. zrb started from inside a git hook, which exports these.
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo / "elsewhere-index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(repo / "elsewhere-objects"))
    monkeypatch.setenv("GIT_DIR", str(repo / "not-a-repo"))
    before = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    after = _snap(store)

    assert store.diff(before, after)[0] == ["tracked.txt"]
    assert not (repo / "elsewhere-index").exists()
    assert not (repo / "elsewhere-objects").exists()


def test_a_temporary_store_borrows_tracked_objects_instead_of_copying(repo, store):
    # Written as bytes, and hashed without filters: on Windows `write_text`
    # would add CRLF, and the repository's `core.autocrlf` would hash that
    # differently from the store, which stores bytes exactly.
    (repo / "committed.txt").write_bytes(b"committed\n")
    _git(repo, "add", "committed.txt")
    _git(repo, "commit", "-qm", "add committed")
    (repo / "untracked.txt").write_bytes(b"new\n")
    tracked_blob = _git(
        repo, "hash-object", "--no-filters", "committed.txt"
    ).stdout.strip()
    untracked_blob = _git(
        repo, "hash-object", "--no-filters", "untracked.txt"
    ).stdout.strip()

    _snap(store)

    own = os.path.join(store.git_dir, "objects")
    assert not os.path.exists(os.path.join(own, tracked_blob[:2], tracked_blob[2:]))
    assert os.path.exists(os.path.join(own, untracked_blob[:2], untracked_blob[2:]))


def test_changes_inside_a_nested_repository_are_diffed(repo, store):
    lib = _nested(repo / "vendor" / "lib", {"v.py": "v\n"})
    before = _snap(store)

    (lib / "v.py").write_text("changed\n")  # e.g. `sed -i` through a shell
    after = _snap(store)

    assert store.diff(before, after)[0] == ["vendor/lib/v.py"]
    assert _git(lib, "status", "--porcelain").stdout == " M v.py\n"


def test_a_directory_of_repositories_is_diffed_as_one(tmp_path):
    workspace = tmp_path / "ws"
    a = _nested(workspace / "a", {"x.py": "a\n"})
    b = _nested(workspace / "b", {"y.py": "b\n"})
    (workspace / "notes.txt").write_text("n\n")
    store = SnapshotStore.create_temporary(str(workspace))
    try:
        before = _snap(store)
        (a / "x.py").write_text("A\n")
        (b / "y.py").unlink()
        (workspace / "notes.txt").write_text("N\n")
        after = _snap(store)

        assert sorted(store.diff(before, after)[0]) == ["a/x.py", "b/y.py", "notes.txt"]
    finally:
        store.delete()


def test_a_temporary_store_borrows_a_nested_repositorys_objects(repo, store):
    lib = _nested(repo / "lib", {"v.py": "v\n"})
    blob = _git(lib, "hash-object", "--no-filters", "v.py").stdout.strip()

    _snap(store)

    own = os.path.join(store.git_dir, "objects")
    assert not os.path.exists(os.path.join(own, blob[:2], blob[2:]))


def test_a_snapshot_reports_the_repositories_it_holds(repo, store):
    (repo / ".gitignore").write_text("ignored.txt\n.zrb/worktree/\n")
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    _nested(repo / "lib", {"v.py": "v\n"})

    snapshot = store.snapshot()

    assert sorted(snapshot.repositories) == ["", ".zrb/worktree/wt", "lib"]


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_an_unreadable_file_with_a_newline_in_its_name_is_left_out(repo, store):
    secret = repo / "two\nlines.key"
    secret.write_text("protected\n")
    secret.chmod(0)
    try:
        snapshot = store.snapshot()
    finally:
        secret.chmod(0o600)

    assert snapshot.tree and snapshot.unreadable == ("two\nlines.key",)


def test_a_file_rewritten_in_the_same_second_at_the_same_size_is_seen(repo, store):
    # Git's stat cache trusts a file whose size and times match its index
    # entry, unless the entry is as new as the index file itself. The rewrite
    # below keeps size and (to the second) times; the next snapshot starts a
    # new second, which must not make the index vouch for the stale entry.
    time.sleep(1 - time.time() % 1 + 0.05)  # the start of a second
    (repo / "tracked.txt").write_text("a\n")
    first = _snap(store)
    (repo / "tracked.txt").write_text("b\n")
    time.sleep(1 - time.time() % 1 + 0.05)  # the next second
    second = _snap(store)

    assert store.diff(first, second)[0] == ["tracked.txt"]


@pytest.mark.parametrize("autocrlf", ["false", "true"])
def test_a_repository_baseline_holds_what_its_own_checkout_wrote(repo, store, autocrlf):
    _git(repo, "config", "core.autocrlf", autocrlf)
    (repo / ".gitignore").write_bytes(b"ignored.txt\n.zrb/worktree/\n")
    (repo / "gone.txt").write_bytes(b"g\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "more")
    fork = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _snap(store)
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    (worktree / "tracked.txt").write_bytes(b"changed\n")
    (worktree / "gone.txt").unlink()
    (worktree / "new.txt").write_bytes(b"n\n")
    (worktree / "committed.txt").write_bytes(b"c\n")
    _git(worktree, "add", "committed.txt")
    _git(worktree, "commit", "-qm", "added since the fork")
    after = store.snapshot()

    baseline = store.create_repository_baseline(before, after, ".zrb/worktree/wt", fork)

    paths, diff = store.diff(baseline, after.tree)
    assert sorted(paths) == [
        ".zrb/worktree/wt/committed.txt",
        ".zrb/worktree/wt/gone.txt",
        ".zrb/worktree/wt/new.txt",
        ".zrb/worktree/wt/tracked.txt",
    ]
    assert "-a" in diff and "+changed" in diff
    assert "+c" in diff  # added and committed since the fork: shown as added


def test_a_repository_baseline_leaves_out_what_the_listing_leaves_out(repo, store):
    (repo / ".gitignore").write_bytes(b"ignored.txt\n.zrb/worktree/\n")
    (repo / ".cache").mkdir()
    (repo / ".cache" / "c.txt").write_bytes(b"c\n")
    _git(repo, "add", "-f", ".")
    _git(repo, "commit", "-qm", "tracked cache")
    fork = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _snap(store)
    worktree = repo / ".zrb" / "worktree" / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    (worktree / ".cache" / "c.txt").write_bytes(b"changed\n")  # never listed
    after = store.snapshot()

    baseline = store.create_repository_baseline(before, after, ".zrb/worktree/wt", fork)

    assert store.diff(baseline, after.tree)[0] == []


def test_a_diff_leaves_out_the_paths_it_is_told_to(repo, store):
    before = _snap(store)
    (repo / "tracked.txt").write_bytes(b"b\n")
    (repo / "odd[name].txt").write_bytes(b"o\n")
    after = _snap(store)

    paths, diff = store.diff(before, after, exclude=["odd[name].txt"])

    assert paths == ["tracked.txt"]
    assert "odd" not in diff


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0, reason="needs POSIX permissions, non-root"
)
def test_a_file_that_becomes_unreadable_leaves_the_next_snapshot(repo, store):
    first = _snap(store)  # holds tracked.txt
    (repo / "tracked.txt").write_bytes(b"newer\n")
    (repo / "tracked.txt").chmod(0)
    try:
        second = store.snapshot()
    finally:
        (repo / "tracked.txt").chmod(0o600)

    assert second.unreadable == ("tracked.txt",)
    assert store.git(["ls-tree", second.tree, "--", "tracked.txt"]) == ""  # not stale
    assert first
