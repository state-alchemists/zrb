"""The store: atomic writes, the lock taken before the read, and a log by date."""

import os
import shutil
import stat
import subprocess
import threading
import time
from datetime import date, timedelta

import pytest

from zrb.config.config import CFG
from zrb.llm.hook.builtin.memory_reviewer import _append_event_line
from zrb.llm.hook.contracts.interface import HookContext
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.memory import paths, render, search, store
from zrb.llm.memory.model import Diary, Fact
from zrb.llm.tool.memory import forget, remember
from zrb.util.file_lock import FileLockTimeout
from zrb.util.owner_only import DIR_MODE, FILE_MODE


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX mode bits (the mode under test)"
)


@needs_posix_modes
def test_the_store_is_created_owner_only(store_dir):
    """A memory holds what the user said; a 0755 directory lists it to everyone."""
    old_umask = os.umask(0o022)
    try:
        paths.ensure_store()
        for path in (str(store_dir), paths.facts_dir(), paths.diary_dir()):
            assert stat.S_IMODE(os.stat(path).st_mode) == DIR_MODE, path
        with store.locked():
            pass
        assert stat.S_IMODE(os.stat(paths.lock_path()).st_mode) == FILE_MODE
        gitignore = os.path.join(str(store_dir), ".gitignore")
        if os.path.exists(gitignore):
            assert stat.S_IMODE(os.stat(gitignore).st_mode) == FILE_MODE
    finally:
        os.umask(old_umask)


def test_a_write_leaves_no_temporary_file(store_dir):
    path = os.path.join(str(store_dir), "facts", "x.md")
    store.write_document(path, "first")
    store.write_document(path, "second")
    assert store.read_document(path) == "second"
    assert os.listdir(os.path.join(str(store_dir), "facts")) == ["x.md"]


def test_a_read_of_a_missing_file_is_empty_not_an_error(store_dir):
    assert store.read_document(os.path.join(str(store_dir), "facts", "gone.md")) == ""


def test_facts_load_in_id_order(store_dir):
    for fact_id in ("c", "a", "b"):
        store.save_fact(Fact(id=fact_id, claim=f"{fact_id} is true."))
    assert [fact.id for fact in store.load_facts()] == ["a", "b", "c"]


def test_a_retired_fact_is_hidden_unless_asked_for(store_dir):
    store.save_fact(Fact(id="x", claim="X.", status="retired", reason="stale"))
    assert store.load_facts() == []
    assert [fact.id for fact in store.load_facts(include_retired=True)] == ["x"]


def test_the_log_line_carries_a_clock_time_and_the_day_is_the_filename(store_dir):
    line = store.append_log("Did the thing", tags="zrb")
    assert line.startswith("- ")
    assert "Did the thing" in line
    assert line.endswith("(zrb)")
    assert store.log_lines(store.today()) == [line]
    assert store.read_document(paths.log_path(store.today())).startswith(
        f"# {store.today()}"
    )


def test_a_second_log_line_sits_directly_under_the_first(store_dir):
    """A day file is one line per event: an append leaves no gap behind it."""
    day = store.today()
    first = store.append_log("First event")
    second = store.append_log("Second event")
    assert store.read_document(paths.log_path(day)) == (f"# {day}\n{first}\n{second}\n")


def test_a_day_file_written_with_gaps_is_healed_by_the_next_append(store_dir):
    """The guarantee covers what an older writer left, not only new lines."""
    day = store.today()
    store.write_document(paths.log_path(day), f"# {day}\n\n- 09:00 — Old event\n")
    line = store.append_log("New event")
    assert store.read_document(paths.log_path(day)) == (
        f"# {day}\n- 09:00 — Old event\n{line}\n"
    )


def test_yesterday_reaches_the_recent_lines_with_its_date(store_dir):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    store.append_log("From yesterday", day=yesterday)
    lines = store.recent_log_lines(4)
    assert len(lines) == 1
    assert lines[0].startswith("- ")
    assert "From yesterday" in lines[0]


def test_a_zero_limit_asks_for_no_log_lines(store_dir):
    """`0` means none; `lines[-0:]` is the whole list, not an empty one."""
    store.append_log("An event")
    assert store.recent_log_lines(0) == []
    assert store.recent_log_lines(-1) == []


def test_pruning_is_off_by_default(store_dir, monkeypatch):
    """The log is history; deleting it is an opt-in, not a default."""
    assert CFG.DEFAULT_LLM_MEMORY_LOG_RETENTION_DAYS == "0"
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 0, raising=False)
    old = (date.today() - timedelta(days=400)).isoformat()
    store.append_log("Ancient", day=old)
    assert store.prune_logs() == []
    assert store.log_lines(old)


def test_pruning_drops_a_log_day_past_the_retention(store_dir, monkeypatch):
    old = (date.today() - timedelta(days=400)).isoformat()
    store.append_log("Ancient", day=old)
    store.append_log("Recent")
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    removed = store.prune_logs()
    assert removed == [f"{old}.md"]
    assert store.log_lines(old) == []
    assert store.log_lines(store.today())


def test_pruning_keeps_everything_when_retention_is_zero(store_dir, monkeypatch):
    old = (date.today() - timedelta(days=400)).isoformat()
    store.append_log("Ancient", day=old)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 0, raising=False)
    assert store.prune_logs() == []
    assert store.log_lines(old)


def test_a_write_holds_the_lock_across_its_render(store_dir, monkeypatch):
    """The read-merge-render-write is one critical section.

    A second writer that cannot get the lock while the first is still rendering
    is what proves the read happens *inside* it: the journal's path read the note
    before taking the lock, and two sessions revising one subject then silently
    dropped each other's revision.
    """
    started = threading.Event()
    release = threading.Event()
    original = render.render_core

    def slow_render(facts):
        started.set()
        release.wait(5)
        return original(facts)

    monkeypatch.setattr(render, "render_core", slow_render)
    worker = threading.Thread(target=lambda: remember("x", "X is true."), daemon=True)
    worker.start()
    try:
        assert started.wait(5)
        monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 0.05, raising=False)
        with pytest.raises(FileLockTimeout):
            with store.locked():
                pass
    finally:
        release.set()
        worker.join(5)


def test_two_writers_on_one_id_keep_both_their_fields(store_dir, monkeypatch):
    """A merge written by a second writer starts from the first one's file."""
    started = threading.Event()
    release = threading.Event()
    original = render.render_core
    calls = {"count": 0}

    def slow_first_render(facts):
        calls["count"] += 1
        if calls["count"] == 1:
            started.set()
            release.wait(5)
        return original(facts)

    monkeypatch.setattr(render, "render_core", slow_first_render)
    first = threading.Thread(
        target=lambda: remember("x", "X is true.", body="Evidence from the first."),
        daemon=True,
    )
    first.start()
    assert started.wait(5)
    second = threading.Thread(
        target=lambda: remember("x", "X is true.", tags=["second"]), daemon=True
    )
    second.start()
    time.sleep(0.1)
    release.set()
    first.join(5)
    second.join(5)

    fact = store.load_fact("x")
    assert fact is not None
    assert fact.body == "Evidence from the first."
    assert fact.tags == ("second",)


def test_a_custom_gitignore_is_extended_not_replaced(store_dir):
    """A user's own ignore rules survive, and stay in force.

    Rewriting `.gitignore` would un-ignore whatever the user excluded, and the
    next `git_commit`'s `git add -A` would then commit it into the audit repo.
    """
    path = os.path.join(str(store_dir), ".gitignore")
    store.write_document(path, "secrets.md\n")
    paths.ensure_store()
    content = store.read_document(path)
    assert content.startswith("secrets.md\n")
    assert ".lock" in content
    assert ".state/" in content


def test_ensure_store_does_not_duplicate_its_gitignore_entries(store_dir):
    paths.ensure_store()
    paths.ensure_store()
    content = store.read_document(os.path.join(str(store_dir), ".gitignore"))
    assert content.count(".lock") == 1
    assert content.count(".state/") == 1


def test_a_file_whose_frontmatter_disagrees_with_its_name_is_not_the_fact(
    store_dir, monkeypatch
):
    """`forget('x')` must never retire a document that says it is `y`."""
    store_dir.mkdir(parents=True, exist_ok=True)
    store.write_document(
        os.path.join(str(store_dir), "facts", "x.md"),
        "---\nid: y\nclaim: A different subject.\n---\n",
    )
    assert store.load_fact("x") is None
    message = forget("x", "stale")
    assert "Nothing is remembered" in message
    assert store.load_fact("y") is None


def test_an_invalid_utf8_file_degrades_to_absent(store_dir):
    """A corrupted or synced file must not take a turn down."""
    facts = os.path.join(str(store_dir), "facts")
    os.makedirs(facts, exist_ok=True)
    with open(os.path.join(facts, "broken.md"), "wb") as f:
        f.write(b"---\nid: broken\nclaim: caf\xe9\n---\n")
    assert store.load_facts() == []
    assert search.search("cafe") == []


def test_a_path_shaped_name_is_refused_by_the_path_builder(store_dir):
    """The boundary checks the id; the path builder checks it again.

    A caller that skipped the tools' validation must not be able to name a file
    outside the store, and a read of such a name is an empty read, not a crash.
    """
    with pytest.raises(ValueError):
        paths.fact_path("../victim")
    with pytest.raises(ValueError):
        paths.diary_path("../../etc/passwd")
    with pytest.raises(ValueError):
        paths.log_path("a/b")
    assert store.load_fact("../victim") is None
    assert store.load_diary("../../etc/passwd") is None


def test_the_last_day_written_is_the_newest_one_before_today(store_dir):
    """What the block's last-day line names, and the one day it must not."""
    for day in ("2026-11-01", "2026-11-03", "2026-11-05"):
        store.save_diary(Diary(id=day, claim=f"Wrote about {day}."))

    previous = store.latest_diary_before("2026-11-04")
    assert previous is not None and previous.id == "2026-11-03"
    previous = store.latest_diary_before("2026-11-06")
    assert previous is not None and previous.id == "2026-11-05"
    # Strictly before: a day is not its own previous day, and a first day has none.
    assert store.latest_diary_before("2026-11-01") is None


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git")


def _run_git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _prepare_default_layout(monkeypatch, notes):
    """The store inside the notes directory, audit trail on, first use run."""
    monkeypatch.setattr(CFG, "LLM_NOTES_DIR", str(notes), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(notes / "memory-v1"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", True, raising=False)
    paths.prepare()


@needs_git
def test_the_reviewers_log_line_is_committed(store_dir, monkeypatch):
    """A log entry retention could prune must exist in the audit history first."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", True, raising=False)
    context = HookContext(
        event=HookEvent.STOP,
        event_data={},
        last_assistant_message="Did a thing worth logging.",
        cwd="/home/gofrendi/zrb",
    )
    _append_event_line(context)
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(store_dir), capture_output=True, text=True
    ).stdout
    assert "log:" in log


@needs_git
def test_an_unrelated_file_in_the_store_directory_is_not_committed(
    store_dir, monkeypatch
):
    """`LLM_MEMORY_DIR` may hold something else; the audit trail owns only its own."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", True, raising=False)
    (store_dir / "notes.txt").write_text("not the store's", encoding="utf-8")
    store.save_fact(Fact(id="x", claim="X is true.", updated=store.now()))
    store.write_core()
    store.git_commit("remember: x")
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(store_dir), capture_output=True, text=True
    ).stdout
    assert "notes.txt" not in tracked
    assert "facts/x.md" in tracked


@needs_git
def test_a_repository_the_store_did_not_create_is_left_alone(store_dir, monkeypatch):
    """A `.git` without our marker belongs to somebody else; no commits go into it."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", True, raising=False)
    subprocess.run(["git", "init", "-q"], cwd=str(store_dir), check=True)
    store.save_fact(Fact(id="x", claim="X is true.", updated=store.now()))
    store.git_commit("remember: x")
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(store_dir), capture_output=True, text=True
    )
    assert log.returncode != 0


@needs_git
def test_a_store_inside_the_notes_directory_uses_the_notes_repository(
    tmp_path, monkeypatch
):
    """One history, not two: `memory-v1` belongs to the repository above it.

    A `.git` of its own there would be a repository nested in another, which the
    outer one then treats as something between a file and a directory.
    """
    notes = tmp_path / "llm-notes"
    notes.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(notes), check=True)
    monkeypatch.setattr(CFG, "LLM_NOTES_DIR", str(notes), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(notes / "memory-v1"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", True, raising=False)
    paths.ensure_store()
    store.save_fact(Fact(id="x", claim="X is true.", updated=store.now()))
    store.git_commit("remember: x")
    assert not os.path.isdir(str(notes / "memory-v1" / ".git"))
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(notes), capture_output=True, text=True
    ).stdout
    assert "remember: x" in log


@needs_git
def test_a_neighbour_file_already_staged_is_not_swept_into_the_commit(
    tmp_path, monkeypatch
):
    """The index is shared, so a commit has to name its paths.

    Reproduced before the fix: `git add -A -- memory-v1/...` put the store's files
    into the same index that already held the user's staged work, and the bare
    `git commit` committed both under zrb's message — the notes history then said
    `zrb-memory` wrote a file it never opened.
    """
    notes = tmp_path / "llm-notes"
    notes.mkdir()
    _run_git(notes, "init", "-q")
    (notes / "unrelated.txt").write_text("the user's work\n", encoding="utf-8")
    _run_git(notes, "add", "unrelated.txt")

    _prepare_default_layout(monkeypatch, notes)
    store.save_fact(Fact(id="x", claim="X is true.", updated=store.now()))
    store.git_commit("remember: x")

    history = _run_git(notes, "log", "--name-only", "--format=").stdout
    assert "unrelated.txt" not in history
    assert "memory-v1/facts/x.md" in history
    assert "A  unrelated.txt" in _run_git(notes, "status", "--short").stdout


@needs_git
def test_a_notes_directory_inside_another_repository_is_left_alone(
    tmp_path, monkeypatch
):
    """A repository that merely contains the notes is not the notes' repository.

    Reproduced before the fix: notes under a project checkout made the store
    answer with the project's repository, and the conversion commit landed in the
    project's history carrying whatever the user had staged — a `.env` in the
    reproduction. The write still happens; only the commit is skipped, which is
    what `git_commit`'s best-effort contract already allows.
    """
    project = tmp_path / "project"
    notes = project / "notes"
    notes.mkdir(parents=True)
    _run_git(project, "init", "-q")
    (project / ".env").write_text("a secret\n", encoding="utf-8")
    _run_git(project, "add", ".env")

    _prepare_default_layout(monkeypatch, notes)
    store.save_fact(Fact(id="x", claim="X is true.", updated=store.now()))
    store.git_commit("remember: x")

    assert store.load_fact("x") is not None
    assert _run_git(project, "log", "--oneline").returncode != 0
    assert "A  .env" in _run_git(project, "status", "--short").stdout
    assert not os.path.isdir(str(notes / "memory-v1" / ".git"))


@needs_git
def test_a_notes_repository_nested_in_another_repository_keeps_its_history(
    tmp_path, monkeypatch
):
    """The nearest repository is the one that counts.

    A notes directory with a `.git` of its own is the notes' repository even when
    a checkout above it also is — the guard asks which repository, not whether
    there is one.
    """
    project = tmp_path / "project"
    notes = project / "notes"
    notes.mkdir(parents=True)
    _run_git(project, "init", "-q")
    _run_git(notes, "init", "-q")

    _prepare_default_layout(monkeypatch, notes)

    assert "memory:" in _run_git(notes, "log", "--oneline").stdout
    assert _run_git(project, "log", "--oneline").returncode != 0


def test_git_is_not_used_when_it_is_switched_off(store_dir):
    store.git_commit("remember: x")
    assert not os.path.isdir(os.path.join(str(store_dir), ".git"))
