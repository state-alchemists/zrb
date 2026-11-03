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

# How many log lines `## Recent` carries. Four is the journal's number and it has
# held up: enough to see the shape of the day, few enough to stay cheap.
_RECENT_LOG_LINES = 4

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
        paths.ensure_store()
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
            store.recent_log_lines(_RECENT_LOG_LINES),
        ),
        CFG.LLM_MEMORY_RECENT_MAX_CHARS,
    )
    if not core.strip() and not recent.strip():
        return None
    _write_shown(facts)
    return render.compose_memory(core, recent)


def render_memory_delta() -> str | None:
    """Facts not in the block — recorded or revised since it went in."""
    if not is_memory_on():
        return None
    known = _read_shown()
    if known is None:
        return None
    try:
        facts = store.load_facts()
    except OSError:
        return None
    block = render.compose_delta(facts, known)
    return block or None


def _session_key() -> str:
    """The conversation's key, or this process's when there is no conversation."""
    key = get_session_ownership_key()
    if key == _FALLBACK_KEY:
        return f"{_FALLBACK_KEY}:{_PROCESS_START}"
    return key


def _write_shown(facts) -> None:
    """Remember which versions the block injected.

    Versions, not a timestamp: a fact recorded in the same second as the block is
    neither before nor after by a clock, and a revised claim has to be shown
    again. This is the journal's own hard-won rule — deduplicating by slug alone
    froze out every correction.
    """
    path = paths.state_path(_session_key())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {"known": [render.claim_key(fact) for fact in facts]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        # Without a record there is no delta, which costs a repeated claim in a
        # later turn. Failing the turn over it would cost the turn.
        pass


def _read_shown() -> list[str] | None:
    try:
        with open(paths.state_path(_session_key()), encoding="utf-8") as f:
            value = json.load(f).get("known")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, str)]
