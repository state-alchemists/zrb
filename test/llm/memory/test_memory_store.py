"""The store: atomic writes, the lock taken before the read, and a log by date."""

import os
import threading
import time
from datetime import date, timedelta

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import paths, render, store
from zrb.llm.memory.model import Fact
from zrb.llm.tool.memory import remember
from zrb.util.file_lock import FileLockTimeout


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


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


def test_yesterday_reaches_the_recent_lines_with_its_date(store_dir):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    store.append_log("From yesterday", day=yesterday)
    lines = store.recent_log_lines(4)
    assert len(lines) == 1
    assert lines[0].startswith("- ")
    assert "From yesterday" in lines[0]


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


def test_git_is_not_used_when_it_is_switched_off(store_dir):
    store.git_commit("remember: x")
    assert not os.path.isdir(os.path.join(str(store_dir), ".git"))
