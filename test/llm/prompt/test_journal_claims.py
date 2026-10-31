"""The claims a turn after the first is given, and the two budgets on them.

The index goes in once, at the start of a session. Before this module, a note
written after that reached the model only when the conversation was compacted —
so a session could record a fact and then answer as though it had not. These
tests pin the replacement: a few claims a turn, ranked, never repeated.
"""

import ast
import pathlib
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from zrb.config.config import CFG
from zrb.llm.ambient_state import set_current_session
from zrb.llm.journal_usage_log import record_prompted
from zrb.llm.prompt import live_context
from zrb.llm.prompt.live_context import _render_parts, render_journal_claims
from zrb.llm.tool.journal_note import set_frontmatter
from zrb.llm.tool.journal_write import supersede_journal_note, write_journal_note

LINE = "Retry is not concurrency-safe."


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """A private journal and usage log, with the claims switched on."""
    root = tmp_path / "notes"
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_DIR", str(root), raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", True, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_INDEX_FILE", "index.md", raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_PER_TURN", 3, raising=False)
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_MAX_CHARS", 1000, raising=False)
    # A conversation key unique to this test: the in-process record of what was
    # shown lives in the module and outlives a test, the way process memory
    # outlives a turn, so two tests must never share a conversation.
    set_current_session(f"bold-arch-{uuid4().hex[:12]}")
    # A turn begins with a prompt, which is this session's first event; every
    # note these tests write comes after it, so all of them are "this session".
    record_prompted()
    return root


def _write(slug: str, hud_line: str = LINE, pinned: bool = False) -> str:
    return write_journal_note(
        category="technical",
        slug=slug,
        title=f"Note {slug}",
        context="while the test runs",
        finding="One finding, whatever it is.",
        source="source.py:1",
        hud_line=hud_line,
        pinned=pinned,
        applies_when="while the test runs",
    )


def _claims(block: str) -> list[str]:
    return [line for line in block.splitlines() if line.startswith("- ")]


def test_a_note_written_mid_session_reaches_the_next_turn(journal):
    """The gap this closes: the index went in at the start, the note was written
    after it, and without this the next turn cannot see it at all."""
    _write("retry-policy")

    block = render_journal_claims()

    assert block is not None
    assert "<journal-claims>" in block
    assert LINE in block
    assert "([note](technical/retry-policy.md))" in block


def _age(root: str, slug: str, when: "datetime") -> None:
    """Rewrite a note's `updated` stamp, so a test can place it in the past."""
    path = pathlib.Path(root, "technical", f"{slug}.md")
    text = set_frontmatter(
        path.read_text(encoding="utf-8"), {"updated": when.isoformat()}
    )
    path.write_text(text, encoding="utf-8")


def test_a_note_older_than_the_conversation_is_not_a_claim(journal, monkeypatch):
    """The block says "during this session". A note the journal already held — here
    one the cap kept out of the index — is what `SearchJournal` and the category
    indexes are for; it would spend one of three slots on old news while the
    block's own sentence says otherwise."""
    monkeypatch.setattr(CFG, "LLM_JOURNAL_INDEX_MAX_CHARS", 120, raising=False)
    for index in range(12):
        _write(f"filler-{index}", hud_line=f"Filler claim number {index}.")
        _age(journal, f"filler-{index}", datetime.now() - timedelta(days=2))
    _render_parts([], None, True, True, first_message="hello")

    assert render_journal_claims() is None


def test_a_claim_is_not_repeated_when_the_usage_log_cannot_be_written(
    journal, monkeypatch, tmp_path
):
    """The log survives a fresh process; this process still remembers what it
    showed when there is no log to write — a read-only home or a full disk must
    not turn the block into the same three claims every turn."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a directory belongs", encoding="utf-8")
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(blocker / "usage"), raising=False)
    _write("retry-policy")

    assert render_journal_claims() is not None
    assert render_journal_claims() is None


def test_two_sessions_do_not_hide_each_other_s_claims(journal):
    """Each conversation gets its own claims: the record is keyed by session, so
    what one session was shown another may still need — the same note is the
    answer to two different questions asked at once."""
    _write("retry-policy")

    set_current_session("bold-arch-1234")
    assert render_journal_claims() is not None

    set_current_session("calm-wave-5678")
    assert render_journal_claims() is not None

    set_current_session("bold-arch-1234")


def test_a_claim_is_shown_once_per_session(journal):
    """Re-injecting what the conversation already carries is the stale-copy
    failure: a thirty-turn session would hold thirty copies of one fact."""
    _write("retry-policy")

    assert render_journal_claims() is not None
    assert render_journal_claims() is None


def test_a_note_revised_after_it_was_shown_is_shown_again(journal):
    """A correction is the valuable claim: the session has seen the note, but
    not the line it now carries. Deduplicating by name alone hid every revision
    made mid-session, which is the one thing a session cannot afford to miss."""
    _write("retry-policy")
    assert "Retry is not concurrency-safe." in render_journal_claims()

    _write("retry-policy", hud_line="Retry is capped at one attempt per prompt.")

    block = render_journal_claims()
    assert block is not None
    assert "Retry is capped at one attempt per prompt." in block
    assert "Retry is not concurrency-safe." not in block


def test_a_note_revised_after_the_index_carried_it_is_shown_again(journal):
    """The index is an injection like any other: what it showed is the note as
    it stood then, not the note for the rest of the session."""
    _write("retry-policy")
    _render_parts([], None, True, True, first_message="hello")
    assert render_journal_claims() is None

    _write("retry-policy", hud_line="Retry is capped at one attempt per prompt.")

    block = render_journal_claims()
    assert block is not None
    assert "Retry is capped at one attempt per prompt." in block


def test_a_claim_the_index_already_carried_is_not_repeated(journal):
    """The index records what it injected as note ids; the claims block records
    the same ids. If the two disagreed, every claim the index showed would come
    back once more — which is why this compares across the two writers."""
    _write("retry-policy")

    _render_parts([], None, True, True, first_message="hello")

    assert render_journal_claims() is None


def test_at_most_the_configured_number_of_claims_a_turn(journal, monkeypatch):
    """A turn that wrote five notes must not answer the next one with five
    claims; they queue instead of piling up."""
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_PER_TURN", 2, raising=False)
    for index in range(5):
        _write(f"note-{index}", hud_line=f"Claim number {index}.")

    first = render_journal_claims()
    second = render_journal_claims()
    third = render_journal_claims()

    assert len(_claims(first)) == 2
    assert len(_claims(second)) == 2
    assert len(_claims(third)) == 1
    assert render_journal_claims() is None


def test_a_pinned_claim_outranks_a_newer_unpinned_one(journal, monkeypatch):
    """A pin is a constraint that holds every turn, so a constraint written this
    session has to reach the next one ahead of a headline written after it."""
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_PER_TURN", 1, raising=False)
    _write("constraint", hud_line="The lock is held for every write.", pinned=True)
    _write("headline", hud_line="A headline written after the constraint.")

    block = render_journal_claims()

    assert "The lock is held for every write." in block
    assert "A headline written after" not in block


def test_a_claim_sharing_a_word_with_the_message_wins_the_last_slot(
    journal, monkeypatch
):
    """Among notes written together, the one on the subject is the one the turn
    can use; freshness alone would pick by write order."""
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_PER_TURN", 1, raising=False)
    _write("coffee", hud_line="Coffee goes in the glass as tubruk.")
    _write("rollout", hud_line="The kubernetes rollout waits for the drain.")

    block = render_journal_claims("how does the kubernetes rollout behave?")

    assert "kubernetes rollout" in block
    assert "tubruk" not in block


def test_a_superseded_note_is_never_a_claim(journal):
    """A note whose `applies_when` stopped holding is evidence, not memory: the
    claim that replaced it is what a later session has to act on."""
    _write("old-cause", hud_line="The cause is buffer starvation.")
    _write("prebuffer", hud_line="The cause is a cushion of audio.")
    supersede_journal_note("technical", "old-cause", "a cushion", "technical/prebuffer")

    block = render_journal_claims()

    assert "The cause is a cushion of audio." in block
    assert "buffer starvation" not in block


def test_the_character_budget_skips_a_claim_that_does_not_fit(journal, monkeypatch):
    """One long claim must not end the turn: the next line may be a short claim
    that fits, and a skipped line is still eligible on a later turn."""
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_MAX_CHARS", 60, raising=False)
    _write("long", hud_line="A long claim about a long subject, at length. " * 2)
    _write("short", hud_line="Short claim.")

    block = render_journal_claims()

    assert "Short claim." in block
    assert "A long claim" not in block


def test_zero_per_turn_suppresses_the_claims(journal, monkeypatch):
    _write("retry-policy")
    monkeypatch.setattr(CFG, "LLM_JOURNAL_CLAIMS_PER_TURN", 0, raising=False)

    assert render_journal_claims() is None


def test_a_disabled_journal_has_no_claims(journal, monkeypatch):
    _write("retry-policy")
    monkeypatch.setattr(CFG, "LLM_JOURNAL_ENABLED", False, raising=False)

    assert render_journal_claims() is None


def test_the_module_postpones_its_annotations():
    """`Note` is imported only for the type checker, so an annotation naming it
    must stay unevaluated: 3.13 and older evaluate annotations where the
    function is defined and raise `NameError` on import, while 3.14 postpones
    them by default (PEP 649). That is why this break reached the matrix and not
    the local suite — PR #783, run 41072102481: 3.14 passed, 3.11 to 3.13 did not.
    """
    module = ast.parse(pathlib.Path(live_context.__file__).read_text(encoding="utf-8"))
    statements = [
        node
        for node in module.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    ]

    assert isinstance(statements[0], ast.ImportFrom)
    assert statements[0].module == "__future__"
    assert any(alias.name == "annotations" for alias in statements[0].names)


def test_the_first_turn_carries_the_index_and_later_turns_the_claims(journal):
    """The two blocks are alternatives, not a pair: a turn with the index does
    not also need the claims, and a turn without it needs them."""
    _write("retry-policy")
    first = _render_parts([], None, True, True, first_message="hello")
    assert "<journal-index>" in first
    assert "<journal-claims>" not in first

    _write("written-later", hud_line="A fact recorded after the index went in.")
    later = _render_parts([], None, True, False, first_message="hello")
    assert "<journal-claims>" in later
    assert "A fact recorded after the index went in." in later
    assert "<journal-index>" not in later
