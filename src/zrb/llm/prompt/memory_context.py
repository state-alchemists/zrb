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
from zrb.llm.ambient_state import get_session_ownership_key
from zrb.llm.memory import paths, render, store
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
        paths.prepare()
        facts = store.load_facts()
    except OSError:
        # An unwritable store is reported by the tools that write to it; a first
        # turn must not fail because a directory could not be created.
        return None
    core = render.cut_lines(
        render.render_core(facts), CFG.LLM_MEMORY_CORE_MAX_CHARS
    )
    recent = render.cut_lines(
        render.render_recent(
            store.latest_handover(),
            store.load_diary(store.today()),
            store.recent_log_lines(CFG.LLM_MEMORY_RECENT_LOG_LINES),
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
    shown = [
        fact.id
        for fact in facts
        if (line := render.core_line(fact)) is not None and line in rendered
    ]
    today_entry = store.load_diary(store.today())
    _write_state(
        [render.claim_key(fact) for fact in facts],
        shown,
        render.diary_key(today_entry) if today_entry is not None else "",
    )
    if not core.strip() and not recent.strip():
        return None
    return render.compose_memory(core, recent)


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
