"""Search ranks by where a word was found, and returns pointers."""

import pytest

from zrb.config.config import CFG
from zrb.llm.memory import paths, search, store
from zrb.llm.memory.model import Diary, Fact


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def _save(**fields):
    fields.setdefault("updated", "2026-11-03T10:00:00")
    fact = Fact(**fields)
    store.save_fact(fact)
    return fact


def test_an_exact_id_outranks_a_claim_mention(store_dir):
    _save(id="deploy", claim="Deploy is a script.", body="")
    _save(id="other", claim="Deploy happens on Fridays.", body="")
    hits = search.search("deploy")
    assert hits[0].id == "deploy"


def test_a_claim_term_outranks_a_tag_and_a_tag_outranks_the_body(store_dir):
    _save(id="in-claim", claim="Compaction keeps the tail verbatim.")
    _save(id="in-tag", claim="Something else entirely.", tags=("compaction",))
    _save(id="in-body", claim="Another thing.", body="compaction is mentioned here")
    order = [hit.id for hit in search.search("compaction")]
    assert order == ["in-claim", "in-tag", "in-body"]


def test_a_newer_tie_is_shown_first(store_dir):
    _save(id="older", claim="Redis is used.", updated="2026-11-01T10:00:00")
    _save(id="newer", claim="Redis is used twice.", updated="2026-11-03T10:00:00")
    assert [hit.id for hit in search.search("redis")] == ["newer", "older"]


def test_retired_claims_are_only_in_the_retired_scope(store_dir):
    _save(id="gone", claim="Staging was port 22.", status="retired", reason="stale")
    assert search.search("staging") == []
    hits = search.search("staging", scope="retired")
    assert [hit.id for hit in hits] == ["gone"]
    assert hits[0].kind == "retired"


def test_diary_scope_reads_the_days(store_dir):
    store.save_diary(
        Diary(id="2026-11-03", claim="Spent the day on memory.", updated="2026-11-03")
    )
    assert [hit.id for hit in search.search("memory", scope="diary")] == ["2026-11-03"]
    assert search.search("memory", scope="facts") == []


def test_log_scope_reads_the_event_lines(store_dir):
    store.append_log("Replaced the journal with a memory store", day="2026-11-03")
    hits = search.search("journal", scope="log")
    assert len(hits) == 1
    assert hits[0].kind == "log"
    assert "Replaced the journal" in hits[0].claim


def test_all_scope_reaches_every_layer(store_dir):
    _save(id="x", claim="A claim about compaction.")
    store.save_diary(
        Diary(id="2026-11-03", claim="A day about compaction.", updated="2026-11-03")
    )
    store.append_log("A line about compaction", day="2026-11-03")
    kinds = {hit.kind for hit in search.search("compaction", scope="all")}
    assert kinds == {"fact", "diary", "log"}


def test_an_unknown_scope_is_refused():
    with pytest.raises(ValueError):
        search.search("x", scope="sessions")


def test_a_zero_hit_search_suggests_an_id_by_word_overlap(store_dir):
    _save(id="staging-ssh-port", claim="Staging SSH is 2222.")
    assert search.suggest("ssh port") == ["staging-ssh-port"]


def test_a_zero_hit_search_says_it_is_not_proof(store_dir):
    text = search.format_hits("unknown-subject", search.search("unknown-subject"))
    assert "No claim matches" in text
    assert "not proof" in text


def test_a_result_is_a_pointer_not_a_body(store_dir):
    _save(id="x", claim="X is true.", body="a body that must not be returned")
    hit = search.search("x")[0]
    assert "must not be returned" not in hit.line()
    assert hit.path == "facts/x.md"
