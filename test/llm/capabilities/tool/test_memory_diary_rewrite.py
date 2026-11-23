"""A rewrite names the body it read, so a day that moved refuses it.

Split from `test_memory_tools.py` by feature group: the two verbs and the search
live there, the diary rewrite's digest lives here — with the rule that a rewrite
has to name a page at all, and the one that keeps the hour the day opened at.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.memory import remember
from zrb.llm.contracts.memory import store
from zrb.llm.contracts.memory.model import digest_body


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


def test_a_rewrite_naming_no_page_is_refused(store_dir):
    """2026-11-23: a session's first write of a day replaced that day.

    The morning body was 6,073 characters when the evening session sent its own
    658 as the default `body_mode="w"` with no digest, and every check passed —
    the length rules compare a body against a threshold, and nothing compared the
    two pages. A rewrite now names the page it read, so the first write of a day
    adds a paragraph instead of replacing the day it never opened.
    """
    morning = "06:37 — He arrived and gave his day a shape."
    remember("2026-11-23", "A day.", kind="diary", body=morning)

    message = remember(
        "2026-11-23",
        None,
        kind="diary",
        body="17:54 — He moved the verifier thread.",
        body_mode="w",
    )

    assert "Nothing was written" in message
    assert morning in message
    assert f'body_digest="{digest_body(morning)}"' in message
    assert store.load_diary("2026-11-23").body == morning


def test_a_rewrite_that_opens_the_day_later_is_refused(store_dir):
    """A compaction shortens a day; it does not start the page at 17:54.

    The day opened at 06:37, and the rewrite that replaced it opened at 17:54:
    both bodies fit the cap and the rewrite freed plenty, so the length rules had
    nothing to say. The hour each body opens at is what a reader can check, and the
    morning is the paragraph a page loses first.
    """
    body = "06:37 — He arrived.\n\n10:09 — He measured the core himself."
    remember("2026-11-23", "A day.", kind="diary", body=body)

    message = remember(
        "2026-11-23",
        None,
        kind="diary",
        body="17:54 — He moved the verifier thread.",
        body_mode="w",
        body_digest=digest_body(body),
    )

    assert "Nothing was written" in message
    assert "opened at 06:37" in message and "opens at 17:54" in message
    assert store.load_diary("2026-11-23").body == body


def test_a_compaction_that_keeps_the_opening_is_written(store_dir):
    """The answering write: the same day, shorter, still opening at 06:37."""
    body = "06:37 — He arrived, and the morning was long.\n\n17:54 — The thread."
    remember("2026-11-23", "A day.", kind="diary", body=body)

    compacted = "06:37 — He arrived.\n\n17:54 — The thread."
    message = remember(
        "2026-11-23",
        None,
        kind="diary",
        body=compacted,
        body_mode="w",
        body_digest=digest_body(body),
    )

    assert "Remembered the day 2026-11-23" in message
    assert store.load_diary("2026-11-23").body == compacted


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
