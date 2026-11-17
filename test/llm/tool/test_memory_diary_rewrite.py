"""A rewrite names the body it read, so a day that moved refuses it.

Split from `test_memory_tools.py` by feature group: the two verbs and the search
live there, the diary rewrite's digest lives here.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import store
from zrb.llm.memory.model import digest_body
from zrb.llm.tool.memory import remember


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOG_RETENTION_DAYS", 90, raising=False)
    return tmp_path / "memory"


def test_a_rewrite_naming_the_body_it_read_is_written(store_dir):
    remember("2026-11-07", "A day.", kind="diary", body="First light.")
    read = store.load_diary("2026-11-07")

    message = remember(
        "2026-11-07",
        None,
        kind="diary",
        body="First light.\n\nEvening: the cap.",
        body_mode="w",
        body_digest=digest_body(read.body),
    )

    assert "Remembered the day 2026-11-07" in message
    assert store.load_diary("2026-11-07").body == "First light.\n\nEvening: the cap."


def test_a_rewrite_of_a_day_that_moved_is_refused_and_shows_the_day(store_dir):
    """Two reviewers compact one day: the second read a body that no longer exists.

    The lock serialised the writes and proved nothing about what had been read, so
    the newer paragraph was replaced by an older copy — a turn's diary entry, gone
    with no error anywhere. The digest makes the rewrite refusable, and the
    refusal carries the day so the second reviewer can merge instead of guess.
    """
    remember("2026-11-07", "A day.", kind="diary", body="First light.")
    stale = digest_body(store.load_diary("2026-11-07").body)
    remember(
        "2026-11-07",
        None,
        kind="diary",
        body="Evening, from the other session.",
        body_mode="a",
    )

    message = remember(
        "2026-11-07",
        None,
        kind="diary",
        body="Evening, compacted.",
        body_mode="w",
        body_digest=stale,
    )

    assert "Nothing was written" in message
    assert "Evening, from the other session." in message
    assert f"body_digest={digest_body(store.load_diary('2026-11-07').body)}" in message
    assert "Evening, compacted." not in store.load_diary("2026-11-07").body


def test_a_digest_on_an_append_is_refused(store_dir):
    """An append is measured against the day as it is, so it has nothing to check."""
    remember("2026-11-07", "A day.", kind="diary", body="First light.")

    message = remember(
        "2026-11-07",
        None,
        kind="diary",
        body="More.",
        body_mode="a",
        body_digest="deadbeef",
    )

    assert "nothing was written" in message
    assert store.load_diary("2026-11-07").body == "First light."


def test_a_digest_on_a_fact_is_refused(store_dir):
    """A fact's body is evidence about one subject, replaced as a whole."""
    message = remember("x", "X is true.", body_digest="deadbeef")
    assert "nothing was written" in message
    assert store.load_fact("x") is None
