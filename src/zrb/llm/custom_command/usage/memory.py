"""The `/usage` Memory section: what the store holds, and what the window wrote.

The store writes no event log — its record is the files it leaves — so the
section reads two sources instead: the store on disk for the numbers a window
cannot bound (`core`, `store`), and the usage log's per-tool counts for the
window's own activity (`writes`, `recall`).

What that costs is stated rather than filled in. A search's outcome is recorded
nowhere, so "how many found nothing" is absent instead of guessed, and the
reviewer's own runs never reach the usage log (`_record_run_usage` is called from
the runner, not from a hook), so there is no `judge` line to draw.
"""

from __future__ import annotations

from dataclasses import dataclass

from zrb.config.config import CFG
from zrb.llm.memory import render, store
from zrb.llm.memory.model import KIND_FACT, KIND_LOOP
from zrb.llm.shared.usage_log import UsageRecord

# The store's three tools. Nothing else writes it, so these calls are the whole
# of a window's trace of it.
REMEMBER = "Remember"
FORGET = "Forget"
SEARCH = "SearchMemory"
# The journal section's column: an eight-character label, then a space.
_LABEL_WIDTH = 9


@dataclass(frozen=True)
class MemorySnapshot:
    """The store as it is now — the part a time window cannot change.

    `read_snapshot` reads it; a caller that already holds one passes it in, so a
    test need not build a store on disk to render a section.
    """

    core_chars: int
    core_cap: int
    pinned: int
    loops: int
    active: int
    retired: int
    diary_days: int


def read_snapshot() -> MemorySnapshot:
    """Read the store on disk. A store that is not there reads empty, not created.

    `load_facts` and `load_diaries` only list a directory, so asking `/usage` on
    a machine that never used memory writes nothing — no store, no conversion.
    """
    facts = store.load_facts()
    return MemorySnapshot(
        core_chars=len(render.render_core(facts)),
        core_cap=CFG.LLM_MEMORY_CORE_MAX_CHARS,
        # The counts mirror what the core renders: a pin is a standing belief,
        # and an open loop renders whether or not it is pinned.
        pinned=sum(1 for fact in facts if fact.pin and fact.kind == KIND_FACT),
        loops=sum(1 for fact in facts if fact.kind == KIND_LOOP),
        active=len(facts),
        retired=len(store.load_facts(include_retired=True)) - len(facts),
        diary_days=len(store.load_diaries()),
    )


def render_memory_section(
    records: list[UsageRecord], snapshot: MemorySnapshot | None = None
) -> list[str]:
    """The lines of the Memory section; empty when there is nothing to report.

    *snapshot* is read from the store when left out, and injected by a caller
    that already holds one.

    Memory off means no section, not an empty one: `LLM_MEMORY_ENABLED` is the
    privacy switch, and a session that reads no memory must not report what the
    store on disk holds. `/usage` is a reader like any other.
    """
    if not CFG.LLM_MEMORY_ENABLED:
        return []
    state = read_snapshot() if snapshot is None else snapshot
    lines = _state_lines(state) + _window_lines(records)
    if not lines:
        return []
    return ["  Memory", *(f"    {line}" for line in lines)]


def _state_lines(state: MemorySnapshot) -> list[str]:
    """What is on disk now; absent when the store holds nothing at all."""
    if not (state.active or state.retired or state.diary_days):
        return []
    return [_core_line(state), _store_line(state)]


def _core_line(state: MemorySnapshot) -> str:
    ratio = state.core_chars / state.core_cap if state.core_cap else 0.0
    return _line(
        "core",
        f"{state.core_chars} of {state.core_cap} chars ({ratio:.0%})",
        f"{state.pinned} pinned",
        f"{state.loops} open loop(s)",
    )


def _store_line(state: MemorySnapshot) -> str:
    return _line(
        "store",
        f"{state.active} fact(s)",
        f"{state.retired} retired",
        f"{state.diary_days} diary day(s)",
    )


def _window_lines(records: list[UsageRecord]) -> list[str]:
    """What the window did to the store, from the usage log's tool counts.

    A window that wrote nothing has no `writes` line rather than a `0 written`,
    the way the journal section omitted a line whose events it did not hold.
    """
    written = _calls(records, REMEMBER)
    forgotten = _calls(records, FORGET)
    searched = _calls(records, SEARCH)
    lines: list[str] = []
    if written or forgotten or searched:
        lines.append(
            _line(
                "writes",
                f"{written} written",
                f"{forgotten} forgotten",
                f"{searched} search(es)",
            )
        )
    if searched and records:
        lines.append(
            _line(
                "recall",
                f"{searched / len(records):.1f} search(es) per run over "
                f"{len(records)} run(s)",
            )
        )
    return lines


def _calls(records: list[UsageRecord], name: str) -> int:
    return sum(record.tool_counts.get(name, 0) for record in records)


def _line(label: str, *parts: str) -> str:
    return f"{label:<{_LABEL_WIDTH}}" + " · ".join(parts)
