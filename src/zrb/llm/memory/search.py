"""Search over the store: pointers, not payloads.

A result is the claim and the path that holds it, never the body. The body is
evidence and can be a page; a search that returned bodies would spend a turn's
context on something the model may not need, and would put text nobody has read
back into the prompt.

Ranking is word overlap with three weights, not embeddings. A fact's claim is one
sentence about one subject, so a term in the claim is strong evidence, a term in
the tags is weaker, and a term only in the evidence is weakest — the journal's
word search had to rank *prose bodies*, which is why the same approach ranked a
note seventh. Ids are matched exactly and score highest, because an id is the
subject and re-stating one is how a claim is revised rather than duplicated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime

from zrb.llm.memory import paths, store
from zrb.llm.memory.model import STATUS_RETIRED, Diary, Fact, parse_stamp

ID_MATCH = 100
CLAIM_TERM = 10
TAG_TERM = 5
BODY_TERM = 1
LOG_TERM = 1

DEFAULT_LIMIT = 10
MAX_SUGGESTIONS = 5

SCOPE_FACTS = "facts"
SCOPE_DIARY = "diary"
SCOPE_LOG = "log"
SCOPE_ALL = "all"
SCOPE_RETIRED = "retired"
SCOPES = (SCOPE_FACTS, SCOPE_DIARY, SCOPE_LOG, SCOPE_ALL, SCOPE_RETIRED)

# Words that say nothing about a subject. Dropped before matching, so "how do I
# deploy" searches for `deploy` rather than for `how`.
_STOP_WORDS = frozenset(
    """
    a an and are as at be been but by can did do does for from had has have how
    i if in into is it its just me my not of on or our so than that the their
    them then there these they this to too was we were what when where which
    who why will with would you your
    """.split()
)

# A term shorter than this is a letter or a preposition fragment.
_MIN_TERM_CHARS = 2


@dataclass(frozen=True)
class Hit:
    """One result: what is claimed, where it lives, and how well it scored."""

    kind: str
    id: str
    claim: str
    path: str
    updated: str
    score: int

    def line(self) -> str:
        stamps = [stamp for stamp in (self.updated[:10], self.kind) if stamp]
        suffix = f" ({', '.join(stamps)})" if stamps else ""
        name = self.id or self.path
        return f"{name} — {self.claim}  [{self.path}]{suffix}"


def terms(query: str) -> list[str]:
    """The words of *query* that could name a subject."""
    words = [word for word in query.lower().split() if word]
    significant = [
        word.strip(".,;:!?()[]\"'") for word in words if word not in _STOP_WORDS
    ]
    kept = [word for word in significant if len(word) >= _MIN_TERM_CHARS]
    return kept or [word for word in significant if word]


def search(
    query: str, scope: str = SCOPE_FACTS, limit: int = DEFAULT_LIMIT
) -> list[Hit]:
    """The best *limit* hits for *query* in *scope*, best first."""
    if scope not in SCOPES:
        raise ValueError(f"scope is one of {', '.join(SCOPES)}; {scope!r} is not.")
    wanted = terms(query)
    if not wanted:
        return []
    hits: list[Hit] = []
    if scope in (SCOPE_FACTS, SCOPE_ALL):
        hits.extend(_fact_hits(wanted, active_only=True))
    if scope in (SCOPE_DIARY, SCOPE_ALL):
        hits.extend(_diary_hits(wanted, active_only=True))
    if scope in (SCOPE_LOG, SCOPE_ALL):
        hits.extend(_log_hits(wanted))
    if scope == SCOPE_RETIRED:
        hits.extend(_fact_hits(wanted, active_only=False, retired_only=True))
        hits.extend(_diary_hits(wanted, active_only=False, retired_only=True))
    hits.sort(key=_best_first)
    return hits[: max(1, limit)]


def format_hits(query: str, hits: list[Hit]) -> str:
    """The result as the model reads it: a summary, then one line per hit."""
    if not hits:
        suggestions = suggest(query)
        head = (
            f"No claim matches {query!r}. This is not proof the subject was never "
            "known: try the words a claim about it would use."
        )
        if suggestions:
            return f"{head}\nDid you mean: {', '.join(suggestions)}"
        return head
    lines = [f"{len(hits)} claim(s) for {query!r}, best first:", *(h.line() for h in hits)]
    return "\n".join(lines)


def suggest(query: str, limit: int = MAX_SUGGESTIONS) -> list[str]:
    """Ids sharing a word with *query*, most shared first.

    Word overlap rather than whole-string similarity: a question is longer than
    any id, and the journal measured `difflib` scoring a six-letter query against
    a ninety-character title at about 0.12 against its own 0.6 bar, so it never
    fired for a realistic query.
    """
    wanted = terms(query)
    if not wanted:
        return []
    scored: list[tuple[int, str]] = []
    for fact in store.load_facts(include_retired=True):
        haystack = f"{fact.id} {fact.claim} {' '.join(fact.tags)}".lower()
        shared = sum(1 for word in wanted if word in haystack)
        if shared:
            scored.append((-shared, fact.id))
    scored.sort()
    return [fact_id for _shared, fact_id in scored[:limit]]


def _fact_hits(
    wanted: list[str], active_only: bool, retired_only: bool = False
) -> list[Hit]:
    hits: list[Hit] = []
    for fact in store.load_facts(include_retired=not active_only):
        if retired_only and fact.is_active:
            continue
        if active_only and not fact.is_active:
            continue
        score = _fact_score(wanted, fact)
        if score:
            hits.append(_fact_hit(fact, score))
    return hits


def _fact_score(wanted: list[str], fact: Fact) -> int:
    if fact.id.lower() in wanted:
        return ID_MATCH
    claim = fact.claim.lower()
    tags = " ".join(fact.tags).lower()
    body = fact.body.lower()
    score = 0
    for word in wanted:
        if word in claim:
            score += CLAIM_TERM
        if word in tags:
            score += TAG_TERM
        if word in body:
            score += BODY_TERM
    return score


def _fact_hit(fact: Fact, score: int) -> Hit:
    return Hit(
        kind="retired" if fact.status == STATUS_RETIRED else fact.kind,
        id=fact.id,
        claim=fact.claim,
        path=paths.relative(paths.fact_path(fact.id)),
        updated=fact.updated,
        score=score,
    )


def _diary_hits(
    wanted: list[str], active_only: bool, retired_only: bool = False
) -> list[Hit]:
    hits: list[Hit] = []
    for entry in store.load_diaries(include_retired=not active_only).values():
        if retired_only and entry.is_active:
            continue
        if active_only and not entry.is_active:
            continue
        score = _diary_score(wanted, entry)
        if score:
            hits.append(_diary_hit(entry, score))
    return hits


def _diary_score(wanted: list[str], entry: Diary) -> int:
    claim = entry.claim.lower()
    body = entry.body.lower()
    return sum(
        (CLAIM_TERM if word in claim else 0) + (BODY_TERM if word in body else 0)
        for word in wanted
    )


def _diary_hit(entry: Diary, score: int) -> Hit:
    return Hit(
        kind="diary",
        id=entry.id,
        claim=entry.claim,
        path=paths.relative(paths.diary_path(entry.id)),
        updated=entry.updated,
        score=score,
    )


def _log_hits(wanted: list[str]) -> list[Hit]:
    hits: list[Hit] = []
    for day in _log_days():
        for line in store.log_lines(day):
            folded = line.lower()
            score = sum(LOG_TERM for word in wanted if word in folded)
            if not score:
                continue
            hits.append(
                Hit(
                    kind="log",
                    id=day,
                    claim=line.removeprefix("- ").strip(),
                    path=paths.relative(paths.log_path(day)),
                    updated=day,
                    score=score,
                )
            )
    return hits


def _log_days() -> list[str]:
    try:
        names = sorted(os.listdir(paths.log_dir()), reverse=True)
    except OSError:
        return []
    return [name.removesuffix(".md") for name in names if name.endswith(".md")]


def _best_first(hit: Hit) -> tuple[int, float, str]:
    """Score, then recency, then id: a tie is broken by what is newer, never by
    where the file happens to sit in the directory."""
    return (-hit.score, -_moment(hit.updated), hit.id)


def _moment(value: str) -> float:
    """*value* as a sortable number; an unreadable stamp sorts oldest."""
    moment: datetime | None = parse_stamp(value)
    if moment is not None:
        return moment.timestamp()
    try:
        return datetime.combine(date.fromisoformat(value), datetime.min.time()).timestamp()
    except ValueError:
        return 0.0
