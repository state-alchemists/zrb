"""The memory tools: one search, two verbs.

There is no `log`, `diary`, `handover`, `pin` or `supersede` tool. A fact, a loop,
a diary entry and a handover are one call with different fields, so there is one
validation path, one refusal vocabulary and one commit rule — the journal's five
verbs, each with its own frontmatter requirements, are what made writing cost
attention that recall never got back.

Writing is the *only* way a memory changes, and every write is a merge: an
argument left out keeps its stored value. A reviewer restating a claim therefore
cannot silently drop the pin, and a session appending a diary paragraph cannot
wipe the handover left by the session before it. `body_mode='a'` adds a paragraph
to the day it names instead of replacing the body, so a day can grow without the
caller reading it back and sending it again.
"""

from __future__ import annotations

import os
from typing import Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.memory import paths, render, search, store
from zrb.llm.memory.model import (
    BODY_APPEND,
    BODY_MODES,
    BODY_REPLACE,
    KIND_DIARY,
    KIND_FACT,
    KIND_LOOP,
    KINDS,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    Diary,
    Fact,
    body_error,
    body_limit,
    body_overflow,
    claim_error,
    date_error,
    handover_error,
    id_error,
    is_date_shaped,
    reason_error,
)
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.purpose import Purpose, requires_purpose
from zrb.util.file_lock import FileLockTimeout

_NOT_A_KIND = (
    f"`kind` is one of {', '.join(KINDS)}. A fact is a belief, a loop is a fact "
    "you owe, a diary entry is a day."
)


@requires_purpose
def search_memory(
    query: Annotated[
        str,
        Field(
            description=(
                "Plain words describing the subject. Stop words are dropped and "
                "any word may match, so 'how do I deploy staging' looks for "
                "deploy and staging."
            )
        ),
    ],
    scope: Annotated[
        str,
        Field(
            description=(
                "facts (default), diary, log, all, or retired. `retired` answers "
                "'what did I believe, and why did I stop'."
            )
        ),
    ] = search.SCOPE_FACTS,
    limit: Annotated[int, Field(description="Most hits to return.")] = 10,
    purpose: Purpose = "",
) -> str:
    """Searches your memory for claims, days and log lines.

    Results are pointers: the claim and the path holding it, never the body. Read
    the path when the one sentence is not enough. Search before you remember a
    subject you may already know — the id *is* the subject, so a second id for
    one subject is the only way a duplicate can still happen.

    A zero-hit answer is not proof the subject was never known: try the words a
    claim about it would use, or `did_you_mean`.
    """
    try:
        hits = search.search(query, scope=scope, limit=limit)
    except ValueError as e:
        return f"{e} [SYSTEM SUGGESTION]: retry with one of the listed scopes."
    return search.format_hits(query, hits)


@requires_purpose
def remember(
    id: Annotated[
        str,
        Field(
            description=(
                "The subject, kebab-case: `staging-ssh-port`, not a title or a "
                "path. Re-using an id revises that claim — that is the whole "
                "deduplication rule."
            )
        ),
    ],
    claim: Annotated[
        str | None,
        Field(
            description=(
                "One sentence, at most 160 characters, saying what is true. This "
                "is what a future session reads; the evidence goes in `body`. "
                "Omit it only when revising a diary that already has one — a "
                "handover that moved does not rewrite the day's claim."
            )
        ),
    ] = None,
    kind: Annotated[
        str | None,
        Field(
            description=(
                "fact (default) for a belief; loop for a fact you owe and have "
                "not closed; diary for a day. A diary entry's id is its date. "
                "Omit it when revising: the existing kind is kept, so revising a "
                "loop with the normal form does not turn it into a fact."
            )
        ),
    ] = None,
    pin: Annotated[
        bool | None,
        Field(
            description=(
                "True keeps the claim in the core, read on every first turn. "
                "Omit to keep what the fact already says; False unpins."
            )
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(description="Free words search matches at medium weight."),
    ] = None,
    applies_when: Annotated[
        str | None,
        Field(
            description=(
                "Prose saying when the claim stops being true, e.g. 'until "
                "hosts/staging.yml changes'. Read by a later session, never "
                "evaluated by code."
            )
        ),
    ] = None,
    source: Annotated[
        str | None,
        Field(
            description=(
                "Where it came from: `user` for something they said, "
                "`observed`, or `session <date>`. This is what separates 'you "
                "told me' from 'I inferred it'."
            )
        ),
    ] = None,
    handover: Annotated[
        str | None,
        Field(
            description=(
                "Diary only: the state of play for the next session, at most 700 "
                "characters. It replaces the day's previous handover."
            )
        ),
    ] = None,
    body: Annotated[
        str | None,
        Field(
            description=(
                "Evidence: quotes, links, what was tried. Never injected, so it "
                "may be as long as a page (8,000 characters; a diary's page is "
                "shorter, and that cap is a setting)."
            )
        ),
    ] = None,
    body_mode: Annotated[
        str | None,
        Field(
            description=(
                "Diary only: 'w' replaces the body (the default); 'a' appends this "
                "paragraph to the one already stored, so adding to a day does not "
                "mean reading it back and sending it again. An append is measured "
                "against the diary body cap as the whole it becomes."
            )
        ),
    ] = None,
    purpose: Purpose = "",
) -> str:
    """Records a claim, an open loop, a diary entry, or a day's handover.

    Use it when a later session would otherwise rediscover what this one learned:
    a decision still in force, a root cause, a preference the user stated, a fact
    about a host or a repository, or a thread left open. A moment between you and
    the user belongs in the diary's body, quoted, with one line of why it
    mattered — a note may not, because a note is a claim about the world.

    The core is capped and enforced by refusal: if pinning would exceed it,
    nothing is written and the refusal names the deficit. Forget something first
    rather than shortening the claim to fit.
    """
    wanted_kind = kind.strip().lower() if kind is not None else None
    id = id.strip()
    if wanted_kind is None and date_error(id) is None:
        # A date names a diary entry and nothing else, so a revision that omits
        # `kind` lands on the day rather than being refused as a fact id.
        wanted_kind = KIND_DIARY
    if wanted_kind is not None and wanted_kind not in KINDS:
        return f"{_NOT_A_KIND} [SYSTEM SUGGESTION]: retry with one of them."
    if body_mode is not None and wanted_kind != KIND_DIARY:
        return (
            "`body_mode` governs a diary body only: a fact's body is evidence "
            "about one subject and is replaced as a whole. [SYSTEM SUGGESTION]: "
            "re-send without it; nothing was written."
        )
    if wanted_kind == KIND_DIARY:
        if pin is not None:
            return (
                "A diary entry never enters the core, so `pin` does not apply to "
                "one. [SYSTEM SUGGESTION]: re-send without it; nothing was "
                "written."
            )
        problem = _body_mode_error(body_mode, body)
        if problem:
            return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
        append = (body_mode or "").strip().lower() == BODY_APPEND
        return _remember_diary(id, claim, handover, source, body, append)
    if claim is None:
        return (
            "A fact needs a `claim`: one sentence saying what is true. Omit it "
            "only when revising a diary that already has one. [SYSTEM "
            "SUGGESTION]: re-send with the sentence."
        )
    return _remember_fact(id, claim, wanted_kind, pin, tags, applies_when, source, body)


@requires_purpose
def forget(
    id: Annotated[
        str,
        Field(description="The subject id (or a diary date) to retire."),
    ],
    reason: Annotated[
        str,
        Field(
            description=(
                "wrong (it was never true), stale (it stopped being true), or "
                "done (a loop is closed). A diary entry is only ever `wrong`."
            )
        ),
    ],
    purpose: Purpose = "",
) -> str:
    """Retires a claim without deleting it.

    The file stays, with its reason and the date, so "what did I believe, and why
    did I stop" stays answerable through `SearchMemory(scope='retired')`. A retired
    fact leaves the core on the next write, which is what makes forgetting visible
    in the prompt rather than only in the file.

    `done` closes an open loop, so use it when the thing you owed is finished.
    """
    wanted_reason = reason.strip().lower()
    id = id.strip()
    if id_error(id) is not None and date_error(id) is not None:
        return (
            f"{id!r} is neither a subject id nor a diary date, and an id becomes "
            "a file name. [SYSTEM SUGGESTION]: search for the subject and pass "
            "the id it reports; nothing was written."
        )
    try:
        paths.prepare()
        with store.locked():
            return _forget_locked(id, wanted_reason)
    except FileLockTimeout:
        return _busy()
    except OSError as e:
        return _unwritable(e)


def _forget_locked(fact_id: str, reason: str) -> str:
    fact = store.load_fact(fact_id, include_retired=True)
    if fact is not None:
        problem = reason_error(reason, fact.kind)
        if problem:
            return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
        path = paths.fact_path(fact.id)
        previous = store.read_document(path)
        _retire(fact, reason)
        try:
            store.write_core()
        except OSError:
            # A retirement the core cannot reflect is not a retirement: the claim
            # would stay in every future block while the file said otherwise.
            _restore_document(path, previous)
            raise
        store.git_commit(f"forget: {fact.id} ({reason})")
        return (
            f"Forgot {fact.id} ({reason}). The file stays; `scope='retired'` finds it."
        )
    entry = store.load_diary(fact_id)
    if entry is not None:
        problem = reason_error(reason, KIND_DIARY)
        if problem:
            return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
        _retire(entry, reason)
        store.git_commit(f"forget: {entry.id} ({reason})")
        return f"Forgot diary {entry.id} ({reason})."
    return (
        f"Nothing is remembered under {fact_id!r}. [SYSTEM SUGGESTION]: search "
        "for the subject before forgetting it; an id is a subject, not a title."
    )


def _retire(entry: Fact | Diary, reason: str) -> None:
    entry.status = STATUS_RETIRED
    entry.reason = reason
    entry.retired_on = store.today()
    entry.updated = store.now()
    if isinstance(entry, Diary):
        store.save_diary(entry)
    else:
        store.save_fact(entry)


def _remember_fact(
    fact_id: str,
    claim: str,
    kind: str | None,
    pin: bool | None,
    tags: list[str] | None,
    applies_when: str | None,
    source: str | None,
    body: str | None,
) -> str:
    if is_date_shaped(fact_id):
        return (
            f"`{fact_id}` is written as a date, and a date names a diary entry. "
            "[SYSTEM SUGGESTION]: pass kind='diary' for a real day, or choose the "
            "subject an id would name for a fact. Nothing was written."
        )
    for problem in (
        id_error(fact_id),
        claim_error(claim),
        body_error(body, kind or KIND_FACT),
    ):
        if problem:
            return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
    try:
        paths.prepare()
        with store.locked():
            return _remember_fact_locked(
                fact_id, claim, kind, pin, tags, applies_when, source, body
            )
    except FileLockTimeout:
        return _busy()
    except OSError as e:
        return _unwritable(e)


def _remember_fact_locked(
    fact_id: str,
    claim: str,
    kind: str | None,
    pin: bool | None,
    tags: list[str] | None,
    applies_when: str | None,
    source: str | None,
    body: str | None,
) -> str:
    # The read is inside the lock: two sessions revising one subject must not
    # each read the old claim.
    old = store.load_fact(fact_id, include_retired=True)
    fact = _merged_fact(
        old, fact_id, claim, kind, pin, tags, applies_when, source, body
    )
    fact.updated = store.now()
    active = _with_fact(fact)
    occupied = fact.pin or fact.kind == KIND_LOOP
    core = render.render_core(active)
    if occupied and len(core) > CFG.LLM_MEMORY_CORE_MAX_CHARS:
        return _over_core(fact, core)
    path = paths.fact_path(fact.id)
    previous = store.read_document(path)
    store.save_fact(fact)
    try:
        store.write_core(active)
    except OSError:
        # The fact and the core are one answer; if the core cannot be written the
        # fact must not survive a reply that says nothing was written.
        _restore_document(path, previous)
        raise
    store.git_commit(f"remember: {fact.id}")
    return _remembered(fact, len(core))


def _restore_document(path: str, previous: str) -> None:
    """Put *path* back as it was, or remove it when it did not exist.

    Best effort: the write that failed is already being reported, and a restore
    that also fails must not replace the reason with a second one.
    """
    try:
        if previous:
            store.write_document(path, previous)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _merged_fact(
    old: Fact | None,
    fact_id: str,
    claim: str,
    kind: str | None,
    pin: bool | None,
    tags: list[str] | None,
    applies_when: str | None,
    source: str | None,
    body: str | None,
) -> Fact:
    """*old* with this call's fields applied; an omitted argument keeps its value.

    `kind` is one of them: a revision that does not repeat `kind="loop"` leaves a
    loop a loop. Only a new subject takes the default.

    Re-remembering a retired fact revives it: the subject is true again, and the
    reason it was retired survives in git rather than blocking the new claim.
    """
    base = old or Fact(id=fact_id, claim=claim)
    return Fact(
        id=fact_id,
        claim=claim,
        kind=kind or base.kind,
        status=STATUS_ACTIVE,
        pin=base.pin if pin is None else pin,
        tags=base.tags if tags is None else tuple(tag.strip() for tag in tags if tag),
        applies_when=(
            base.applies_when if applies_when is None else applies_when.strip()
        ),
        source=base.source if source is None else source.strip(),
        updated=base.updated,
        body=base.body if body is None else body,
    )


def _with_fact(fact: Fact) -> list[Fact]:
    others = [item for item in store.load_facts() if item.id != fact.id]
    return [*others, fact] if fact.is_active else others


def _over_core(fact: Fact, core: str) -> str:
    """The refusal: what did not fit, by how much, and what to do about it.

    The core shown is the one *before* this write. Showing the rejected render
    would hand the model a document that does not exist on disk and ask it to
    decide what to drop from it.
    """
    limit = CFG.LLM_MEMORY_CORE_MAX_CHARS
    previous = render.render_core(store.load_facts())
    deficit = len(core) - limit
    return (
        f"[SYSTEM SUGGESTION]: adding `{fact.id}` brings the memory core to "
        f"{len(core)}/{limit} characters, {deficit} over. Nothing was written. "
        "Free the room first — `forget(<id>, 'stale')` for a claim that no longer "
        "holds, or `remember(<id>, pin=False)` for one that need not be resident — "
        "then record this again. The cap is checked only on the result.\n"
        f"current core:\n{previous or '(the core is empty)'}"
    )


def _remembered(fact: Fact, core_chars: int) -> str:
    where = (
        "in the core" if fact.pin or fact.kind == KIND_LOOP else "reachable by search"
    )
    return (
        f"Remembered {fact.id} ({where}; core {core_chars}/"
        f"{CFG.LLM_MEMORY_CORE_MAX_CHARS} characters)."
    )


def _body_mode_error(body_mode: str | None, body: str | None) -> str | None:
    """Why *body_mode* cannot govern this write, or ``None``."""
    if body_mode is None:
        return None
    mode = body_mode.strip().lower()
    if mode not in BODY_MODES:
        return (
            f"`body_mode` is {BODY_REPLACE!r} (replace the body) or "
            f"{BODY_APPEND!r} (append to it); {body_mode!r} is neither."
        )
    if mode == BODY_APPEND and not (body or "").strip():
        return "An append has nothing to append: `body` is empty."
    return None


def _body_after(old: Diary | None, body: str | None, append: bool) -> str:
    """The body this call leaves behind: added to, replaced, or left as it was."""
    if append:
        return _appended_body(old.body if old else "", body or "")
    if body is None and old:
        return old.body
    return body or ""


def _appended_body(previous: str, paragraph: str) -> str:
    """*paragraph* after *previous*, one blank line apart."""
    if not previous.strip():
        return paragraph.strip()
    return f"{previous.rstrip()}\n\n{paragraph.strip()}"


def _remember_diary(
    day: str,
    claim: str | None,
    handover: str | None,
    source: str | None,
    body: str | None,
    append: bool,
) -> str:
    """Write a day. *claim* may be ``None``, which keeps the stored sentence.

    A handover that moved is not a new answer to "what was this day": the claim
    is rendered as the `Today` line of every later session and as that day's line
    in the week view, so rewriting it from one turn's transcript would make the
    day a log of its last turn. Every other field already follows the merge rule
    — omitted means kept — and the claim was the one exception.
    """
    for problem in (
        date_error(day),
        claim_error(claim) if claim is not None else None,
        body_error(body, KIND_DIARY),
        handover_error(handover),
    ):
        if problem:
            return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
    try:
        paths.prepare()
        with store.locked():
            return _remember_diary_locked(day, claim, handover, source, body, append)
    except FileLockTimeout:
        return _busy()
    except OSError as e:
        return _unwritable(e)


def _claim_to_store(claim: str | None, old: "Diary | None") -> str | None:
    """The sentence a diary write stores, or ``None`` when a new day has none.

    Omitted keeps the stored one, the rule every other field follows: a handover
    that moved is not a new answer to what the day was, and a reviewer that never
    read the day must not rewrite its `Today` line.
    """
    if claim is not None:
        return claim
    return old.claim if old is not None else None


def _remember_diary_locked(
    day: str,
    claim: str | None,
    handover: str | None,
    source: str | None,
    body: str | None,
    append: bool,
) -> str:
    old = store.load_diary(day)
    if old is None and not body:
        return (
            "A new diary entry needs a `body`: the day in the first person, what "
            "it was rather than what happened (the log holds that). "
            "[SYSTEM SUGGESTION]: nothing was written."
        )
    claim = _claim_to_store(claim, old)
    if claim is None:
        return (
            "A new diary entry needs a `claim`: the day in one line, at most "
            "160 characters. [SYSTEM SUGGESTION]: nothing was written."
        )
    body_text = _body_after(old, body, append)
    # Only an append needs the whole: the fragment the caller sent passed
    # `body_error` already, and the cap is a question about what the day becomes.
    problem = body_overflow(body_text) if append else None
    if problem:
        return f"{problem} [SYSTEM SUGGESTION]: nothing was written."
    entry = Diary(
        id=day,
        claim=claim,
        handover=old.handover if handover is None and old else (handover or ""),
        status=STATUS_ACTIVE,
        source=old.source if source is None and old else (source or ""),
        updated=store.now(),
        body=body_text,
    )
    store.save_diary(entry)
    store.git_commit(f"diary: {entry.id}")
    if append:
        # The paragraph as it was stored: padding is trimmed on the way in, and the
        # blank line that separates it is not part of what the caller wrote.
        added = len((body or "").strip())
        return (
            f"Appended {added} characters to the day {entry.id} (body "
            f"{len(entry.body)}/{body_limit(KIND_DIARY)} characters)."
        )
    return f"Remembered the day {entry.id} ({len(entry.body)} characters of body)."


def _busy() -> str:
    return (
        "[SYSTEM SUGGESTION]: another session is writing to memory right now and "
        f"the lock was not free within {CFG.LLM_MEMORY_LOCK_TIMEOUT}s. Nothing "
        "was written; retry once, and do not retry a third time."
    )


def _unwritable(error: OSError) -> str:
    """The store could not be read or written: say so, and carry on without it.

    A tool that raises takes the turn with it, and a memory that is unavailable is
    not a reason to lose an answer that was already composed.
    """
    return (
        f"[SYSTEM SUGGESTION]: the memory store could not be written ({error}). "
        "Nothing was written. Do not retry: report it to the user and carry on "
        "without recording this."
    )


search_memory.__name__ = "SearchMemory"
remember.__name__ = "Remember"
forget.__name__ = "Forget"
# Reading is one call; the two verbs change the store.
tag(search_memory, Capability.READ)
tag(remember, Capability.EDIT)
tag(forget, Capability.EDIT)
