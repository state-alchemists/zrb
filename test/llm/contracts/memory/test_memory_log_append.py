"""Appending to a log day: a writer must read what it is about to rewrite."""

import pytest

from zrb.config.config import CFG
from zrb.llm.contracts.memory import paths, store


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def test_an_append_to_a_day_it_could_not_read_leaves_that_day_alone(store_dir):
    """An append is a read-modify-write, so a degraded read erases the day.

    Reproduced before the fix: `read_document` maps an invalid-UTF-8 file to `""`
    on purpose, `append_log` took that for an empty day, and a file holding two
    good lines and one bad byte came back as the new line alone.
    """
    day = "2026-11-03"
    path = paths.log_path(day)
    original = (
        b"# 2026-11-03\n"
        b"- 09:00 \xe2\x80\x94 First event\n"
        b"- 10:00 \xe2\x80\x94 caf\xe9\n"  # latin-1 `é`: not UTF-8
    )
    with open(path, "wb") as f:
        f.write(original)

    with pytest.raises(store.UnreadableLogDay) as refusal:
        store.append_log("New event", day=day)

    assert path in str(refusal.value)
    with open(path, "rb") as f:
        assert f.read() == original
