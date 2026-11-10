"""The `<memory>` block, and the small diff a later turn sees.

Two layers, both on the *user* turn rather than the system prompt: the core
changes whenever the agent learns, and a mutable block in the cached prefix
invalidates that cache on every write.

* **The block** — the core and `## Recent`, on a conversation's first turn and
  again after a compaction.
* **The delta** — facts written or revised since that block went in, because a
  core emitted once cannot show a claim recorded at turn four. This is what keeps
  a session from answering as though it had never recorded what it just recorded.

The session's start is written to disk when the block is rendered, keyed by the
owning conversation. A web runner that builds every message in a fresh process
therefore still finds the start its own conversation wrote, while a CLI run with
no conversation identity is keyed by its process, so this run's first turn starts
the clock instead of inheriting the last run's.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from zrb.config.config import CFG
from zrb.llm.memory import paths, render, store
from zrb.llm.memory.model import Fact
from zrb.llm.shared.ambient_state import get_session_ownership_key
from zrb.util.owner_only import makedirs_owner_only, write_text_owner_only

# The process's own start, so two CLI runs in one directory are two sessions.
_PROCESS_START = datetime.now().replace(microsecond=0).isoformat()

# The fallback key `get_session_ownership_key` returns outside a chat run.
_FALLBACK_KEY = "default"


def is_memory_on() -> bool:
    return bool(CFG.LLM_MEMORY_ENABLED)


def render_memory_block() -> str | None:
    """The injected block, or ``None`` when there is nothing to remember yet."""
    if not is_memory_on():
        return None
    try:
        store_root = paths.prepare()
        facts = store.load_facts()
    except OSError:
        # An unwritable store is reported by the tools that write to it; a first
        # turn must not fail because a directory could not be created.
        return None
    core_cap = CFG.LLM_MEMORY_CORE_MAX_CHARS
    core = render.cut_lines(render.render_core(facts), core_cap)
    today_day = store.today()
    recent = render.cut_lines(
        render.render_recent(
            store.latest_handover(today_day),
            store.load_diary(today_day),
            store.recent_log_lines(CFG.LLM_MEMORY_RECENT_LOG_LINES),
            previous_entry=store.latest_diary_before(today_day),
            week_note=store.latest_week_note(today_day),
        ),
        CFG.LLM_MEMORY_RECENT_MAX_CHARS,
    )
    # The baseline is recorded whether or not the block has content. An empty
    # store is a first turn too: without the record, a fact remembered during
    # that turn has nothing to be "new" against, and the next turn shows nothing.
    #
    # Two facts are kept apart: `known` is the store as of this turn (so a delta
    # reports changes, not the whole store), and `shown` is what the cap actually
    # rendered (so "forget this claim" is only said about a claim the model was
    # given). A migrated store larger than the cap stays reachable because its
    # overflow is not in `shown`; an ordinary unpinned fact never earns a
    # tombstone because it was never in the block either.
    rendered = set(core.splitlines())
    shown = _shown_so_far(_core_claim_ids(facts, rendered))
    today_entry = store.load_diary(store.today())
    _write_state(
        [render.claim_key(fact) for fact in facts],
        shown,
        render.diary_key(today_entry) if today_entry is not None else "",
    )
    if not core.strip() and not recent.strip():
        return None
    # The block carries its own address and budget: it tells the model to read
    # `facts/<id>.md`, and a relative path with no root is one it cannot open.
    return render.compose_memory(
        core, recent, store_root, render.core_budget(facts, core_cap)
    )


def render_memory_delta() -> str | None:
    """Changes and removals since the block went in, or ``None`` when neither."""
    if not is_memory_on():
        return None
    state = _read_state()
    if state is None:
        # No baseline: this turn is a first turn too — a conversation resumed after
        # a restart, or one whose state was never written. It gets the block, which
        # is also what reads an unconverted notes directory on the first turn after
        # an upgrade; answering with nothing is what an upgrade used to look like.
        return render_memory_block()
    known, shown, diary = state
    today_entry = store.load_diary(store.today())
    try:
        facts = store.load_facts(include_retired=True)
    except OSError:
        return None
    plan = render.plan_delta(facts, known, shown, today_entry, diary)
    if not plan.text:
        # Today's entry may still have advanced; keep the baseline current so it
        # is not re-emitted on the next turn.
        _write_state(known, shown, plan.diary_key)
        return None
    # Advance the baseline only by what this delta actually said: a fact left out
    # by the three-line cap stays unseen and appears on the next turn.
    emitted_ids = [render.id_of(key) for key in plan.emitted]
    replaced = set(plan.forgotten) | set(emitted_ids)
    kept = [key for key in known if render.id_of(key) not in replaced]
    still_shown = [fact_id for fact_id in shown if fact_id not in plan.forgotten]
    _write_state(
        kept + list(plan.emitted),
        still_shown + [item for item in emitted_ids if item not in still_shown],
        plan.diary_key,
    )
    return plan.text


def _session_key() -> str:
    """The conversation's key, or this process's when there is no conversation."""
    key = get_session_ownership_key()
    if key == _FALLBACK_KEY:
        return f"{_FALLBACK_KEY}:{_PROCESS_START}"
    return key


def _write_state(known, shown, diary_key: str = "") -> None:
    """Remember which versions the block knew, and which claims it showed.

    Versions, not a timestamp: a fact recorded in the same second as the block is
    neither before nor after by a clock, and a revised claim has to be shown
    again. This is the journal's own hard-won rule — deduplicating by slug alone
    froze out every correction.
    """
    path = paths.state_path(_session_key())
    try:
        makedirs_owner_only(os.path.dirname(path))
        write_text_owner_only(
            path,
            json.dumps(
                {"known": list(known), "shown": list(shown), "diary": diary_key}
            ),
        )
    except OSError:
        # Without a record there is no delta, which costs a repeated claim in a
        # later turn. Failing the turn over it would cost the turn.
        pass


def claims_in_the_core() -> frozenset[str]:
    """The claim ids this turn's core carries — or would carry, once rendered.

    The block is written after the hooks run, so a conversation's first turn has
    no `shown` list yet. A cue that asks only for what was already shown would
    then offer a pinned claim that the core is about to state a few lines later.
    Reading the store directly closes that window without depending on order.
    """
    try:
        facts = store.load_facts()
    except OSError:
        return frozenset()
    core_cap = CFG.LLM_MEMORY_CORE_MAX_CHARS
    core = render.cut_lines(render.render_core(facts), core_cap)
    return frozenset(_core_claim_ids(facts, set(core.splitlines())))


def _core_claim_ids(facts: "list[Fact]", rendered: "set[str]") -> list[str]:
    """The ids whose core line survived the cap."""
    return [
        fact.id
        for fact in facts
        if (line := render.core_line(fact)) is not None and line in rendered
    ]


def _shown_so_far(core_ids: list[str]) -> list[str]:
    """The core's claims plus whatever an earlier layer already showed.

    The block is written after the hooks have run, so a recall on this turn has
    already put a claim in front of the model and recorded it. Writing `shown`
    from the core alone forgot that: the next cue offered the same claim again,
    and a claim retired after being shown never earned its "Forget this claim"
    line, because the tombstone is decided from this list. A compaction
    re-renders the block through the same function, so the overwrite lost the
    same ids a second way.

    The state file is keyed by conversation, so the union cannot carry another
    session's claims into this one.
    """
    shown = list(core_ids)
    state = _read_state()
    if state is None:
        return shown
    for claim_id in state[1]:
        if claim_id not in shown:
            shown.append(claim_id)
    return shown


def shown_claim_ids() -> frozenset[str]:
    """The claim ids this conversation has already put in front of the model.

    Written by whichever layer showed them — the block, the delta, or a recall —
    so "already shown" is one fact about the conversation rather than one per
    caller. An empty store, or a store whose state was never written, reads as
    nothing shown: the next claim is worth surfacing until something says it was.
    """
    state = _read_state()
    return frozenset(state[1]) if state is not None else frozenset()


def note_claims_shown(claim_ids: "list[str]") -> None:
    """Record claims shown outside the block, so a later turn does not repeat them.

    The same list the block writes, and for the same reason: a claim the model
    has been given is not news. A recalled claim that is retired afterwards then
    earns its "Forget this claim" line, which is right — the model had it.
    """
    state = _read_state()
    # No state yet is a conversation's first turn, and the hooks run before the
    # block is written: starting from an empty baseline instead of returning keeps
    # the claim out of the next cue, and the block unions it in a moment later.
    known, shown, diary = state if state is not None else ([], [], "")
    added = [claim_id for claim_id in claim_ids if claim_id and claim_id not in shown]
    if added:
        _write_state(known, shown + added, diary)


def _read_state() -> tuple[list[str], list[str], str] | None:
    try:
        with open(paths.state_path(_session_key()), encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    known = payload.get("known")
    if not isinstance(known, list):
        return None
    shown = payload.get("shown")
    # A state file written before `shown` existed names its known ids, which is
    # the old behaviour: every fact the store held counted as shown.
    if not isinstance(shown, list):
        shown = [render.id_of(item) for item in known if isinstance(item, str)]
    diary = payload.get("diary")
    return (
        [item for item in known if isinstance(item, str)],
        [item for item in shown if isinstance(item, str)],
        diary if isinstance(diary, str) else "",
    )
