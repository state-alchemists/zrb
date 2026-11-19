"""A diary is compacted before it is full, not when it is.

The reviewer rewrote a day to fit "under 8,000 characters" and landed at 7,980:
every turn compacted, nothing freed, and the page sat there for hours while the
next writer — usually the assistant itself, appending in the foreground — was the
one refused. Two refusals make a compaction a compaction, and both live in the
tool because a prompt can only ask: an append may not cross the point, and a
rewrite that starts past it may not land past it.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.memory import remember
from zrb.llm.contracts.memory import store
from zrb.llm.contracts.memory.model import digest_body

_CAP = 1_000
_COMPACT_AT = 600


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_MAX_CHARS", _CAP, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_COMPACT_AT", _COMPACT_AT, raising=False)
    return tmp_path / "memory"


def test_an_append_past_the_compaction_point_is_refused_and_shows_the_day(store_dir):
    """The paragraph fits the cap and still may not be added.

    The paragraph is not too long; the page it joins is too full. Without this,
    the day grows to the cap one turn at a time and the last writer to arrive is
    the one refused, with no page to shorten.
    """
    body = "x" * (_COMPACT_AT - 10)
    remember("2026-11-07", "A day.", kind="diary", body=body)

    message = remember("2026-11-07", None, kind="diary", body="y" * 40, body_mode="a")

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == body
    assert "Nothing was written" in message
    assert f"compacted from {_COMPACT_AT}" in message
    # The writer holds its paragraph and never the page, so the refusal carries
    # the day and the digest the answering rewrite has to name.
    assert body in message
    assert f'body_digest="{digest_body(body)}"' in message


def test_a_rewrite_from_a_full_page_has_to_land_under_the_point(store_dir):
    """This is the ceiling-hugging write: a compaction that drops one paragraph.

    A day at 7,980 was rewritten to 7,9xx turn after turn — shorter, never short
    — so the append that followed was refused again and the page never moved.
    """
    body = "x" * 700
    remember("2026-11-07", "A day.", kind="diary", body=body)

    message = remember(
        "2026-11-07",
        None,
        kind="diary",
        body="x" * 650,
        body_mode="w",
        body_digest=digest_body(body),
    )

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == body
    assert "Nothing was written" in message
    assert "freed nothing" in message


def test_a_handover_alone_is_written_on_a_full_page(store_dir):
    """A metadata update asks for no rewrite, so there is nothing to free.

    This is the reviewer's own path: the day is past the point, the state of play
    has changed, and the write carries a handover and no body. Judging it as a
    rewrite compared the stored body with itself — over the threshold and over
    it — and refused a write that never touched the page.
    """
    body = "x" * (_COMPACT_AT + 50)
    remember("2026-11-07", "A day.", kind="diary", body=body)

    message = remember("2026-11-07", None, kind="diary", handover="At chapter two.")

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == body
    assert entry.handover == "At chapter two."
    assert "Nothing was written" not in message


def test_a_claim_alone_is_written_on_a_full_page(store_dir):
    """The same rule for the other metadata: a claim is not a body either."""
    body = "x" * (_COMPACT_AT + 50)
    remember("2026-11-07", "A day.", kind="diary", body=body)

    message = remember("2026-11-07", "Another day.", kind="diary")

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == body
    assert entry.claim == "Another day."
    assert "Nothing was written" not in message


def test_the_rewrite_that_answers_the_refusal_is_written(store_dir):
    """One number, one answer: cut below the point and the write lands."""
    body = "x" * 700
    remember("2026-11-07", "A day.", kind="diary", body=body)

    message = remember(
        "2026-11-07",
        None,
        kind="diary",
        body="x" * 500,
        body_mode="w",
        body_digest=digest_body(body),
    )

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == "x" * 500
    assert "Remembered the day 2026-11-07" in message


def test_a_rewrite_below_the_point_is_an_edit_and_may_grow(store_dir):
    """Only a page past the point is being compacted; below it a rewrite can grow."""
    body = "x" * 300
    remember("2026-11-07", "A day.", kind="diary", body=body)

    remember(
        "2026-11-07",
        None,
        kind="diary",
        body="x" * 590,
        body_mode="w",
        body_digest=digest_body(body),
    )

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == "x" * 590


def test_a_new_day_is_bounded_by_the_cap_and_not_by_the_point(store_dir):
    """Nothing to drop from a page that did not exist yet, so only the cap applies."""
    message = remember("2026-11-07", "A day.", kind="diary", body="x" * 700)

    entry = store.load_diary("2026-11-07")
    assert entry is not None and entry.body == "x" * 700
    assert "Remembered the day" in message


def test_a_point_above_the_cap_leaves_only_the_cap(store_dir, monkeypatch):
    """A threshold the cap refuses is clamped, so an older config keeps working."""
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_COMPACT_AT", 5_000, raising=False)
    remember("2026-11-07", "A day.", kind="diary", body="x" * (_CAP - 10))

    message = remember("2026-11-07", None, kind="diary", body="y" * 40, body_mode="a")

    assert "Nothing was written" in message
    assert f"would be {_CAP + 32} characters" in message
    assert "LLM_MEMORY_DIARY_MAX_CHARS" in message
