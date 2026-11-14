"""The week note: one sentence closing a finished week.

The store keeps a ladder — day, week, month — and the middle rung was the one
nothing wrote. A session opens with the core, today's claim and the last day
written; a month of day claims cannot ride in `## Recent`, so "what have we been
doing" survived only for as long as the days did.

A week note is that rung: one sentence, written once, from the day claims of the
week that just ended. It costs one small-model call per week, and it runs on the
session's first turn rather than on a schedule — a note is owed the first time
somebody is there to read it, and a cron job would spend the call whether or not
anyone was.

The trigger is the week boundary, not a model's judgement about one: this is the
half of remembering that happens *to* you, and a reviewer looking at a single
turn cannot see a week.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.contracts.interface import HookResult
from zrb.llm.hook.contracts.schema import (
    AgentHookConfig,
    HookConfig,
    MatcherConfig,
)
from zrb.llm.hook.contracts.types import HookEvent, HookType, MatcherOperator
from zrb.llm.memory import store
from zrb.llm.memory.model import (
    MAX_CLAIM_CHARS,
    Diary,
    WeekNote,
    injection_reason,
    iso_week,
    week_span,
)
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.shared.usage_log import COMPONENT_HOOK, record_agent_usage
from zrb.llm.shared.agent_runner import create_agent

if TYPE_CHECKING:
    from zrb.llm.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.hook.manager import HookManager

WEEK_NAME = "memory-week"

# What wrote the note, in its frontmatter. `week` is the hook; a hand-edited note
# keeps whatever it said, so the two are told apart in the file rather than in
# the reader.
SOURCE = "week"

# A single completion, on a sentence the model has been handed the material for.
# Long enough for a slow provider, short enough that a first turn does not hang
# on one that is not answering — and it only runs when a week is actually owed.
_TIMEOUT_SECONDS = 60


def build_week_note_hook_config() -> HookConfig:
    """The week note's `HookConfig`, on every completed turn.

    A completed turn rather than a session's first one, for two reasons. The
    block a session opens with is rendered *after* the startup hooks, so a note
    written there would cost the first turn a model call; and a test that fires
    a startup hook by hand would then read whatever store the machine has.

    The `memory_due` matcher is the reviewer's, and for the same reason: it is
    the flag the runner computes, and a hook nobody gated would fire in every
    test that builds an empty context.
    """
    return HookConfig(
        name=WEEK_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt="",
            tools=[],
            model=resolve_configured_small_model(),
            auto_approve=False,
        ),
        matchers=[
            MatcherConfig(
                field="event_data.memory_due",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        timeout=_TIMEOUT_SECONDS,
    )


def register_week_note_hook(manager: "HookManager") -> None:
    """Register the week note hook once per manager, while memory is on.

    Behind the reviewer's switch as well: both spend a model call on memory's
    behalf, and a user who turned the reviewer off to stop those calls did not
    mean "except on Mondays".
    """
    if not (CFG.LLM_MEMORY_ENABLED and CFG.LLM_MEMORY_REVIEWER_ENABLED):
        return
    config = build_week_note_hook_config()
    if config.name in manager.registry.get_configs():
        return
    registered = manager.register_hook_config(config, source="builtin")
    if registered is None:
        return
    manager.remove_hook(registered)
    manager.add_hook(create_week_note_hook(), config.events, config)


def create_week_note_hook() -> "HookCallable":
    """Return the hook: close a finished week in one sentence, once."""

    async def week_note(_context: "HookContext") -> "HookResult":
        request = await asyncio.to_thread(week_note_request)
        if request is None:
            return HookResult()
        week, material = request
        claim = await _ask_model(material)
        if claim:
            await asyncio.to_thread(_save_note, week, claim)
        return HookResult()

    return week_note


def week_note_request(today_day: str | None = None) -> tuple[str, str] | None:
    """``(week, material)`` when a finished week still owes a note, else ``None``.

    Only the week that has just ended is considered. An older gap is left alone
    on purpose: the block shows one note, and a model call spent on a week
    nothing will read is how a background job becomes a bill.
    """
    if not (CFG.LLM_MEMORY_ENABLED and CFG.LLM_MEMORY_REVIEWER_ENABLED):
        return None
    week = previous_week(iso_week(today_day or store.today()))
    if store.load_week(week) is not None:
        return None
    material = week_material(week)
    if not material:
        return None
    return week, material


def week_material(week: str) -> str:
    """What the week was, for the model: its day claims, and how many are missing.

    The gap is counted rather than filled. A week with two written days out of
    seven is mostly a gap, and the note has to know that before it invents a
    theme for the other five.
    """
    start, end = week_span(week)
    lines = [f"- {day}: {entry.claim}" for day, entry in _written_days(start, end)]
    if not lines:
        return ""
    header = f"Week {week} ({start} to {end}), {len(lines)} of 7 days written:"
    return "\n".join([header, *lines])


def _written_days(start: str, end: str) -> list[tuple[str, Diary]]:
    """Every day in ``[start, end]`` that has an active entry with a claim."""
    first = date.fromisoformat(start)
    found: list[tuple[str, Diary]] = []
    for offset in range((date.fromisoformat(end) - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        entry = store.load_diary(day)
        if entry is not None and entry.is_active and entry.claim.strip():
            found.append((day, entry))
    return found


def previous_week(week: str) -> str:
    """The ISO week before *week*.

    Public because the block's tests need the same week the hook will write
    about, and computing it a second way in a test is how a test drifts from the
    code it is testing.
    """
    monday, _ = week_span(week)
    return iso_week((date.fromisoformat(monday) - timedelta(days=7)).isoformat())


async def _ask_model(material: str) -> str:
    """The week in one sentence, or ``""`` when the model gives nothing usable."""
    try:
        agent = create_agent(
            model=resolve_configured_small_model(),
            system_prompt=get_prompt("memory_week"),
            resolve_model=False,
        )
        result = await agent.run(material)
        record_agent_usage(result, component=COMPONENT_HOOK)
    except (OSError, RuntimeError) as error:
        # The two shapes a one-shot call fails in: a model that could not be
        # resolved or did not answer, which pydantic-ai raises as a
        # `RuntimeError`, and a transport or store that was not there. Nothing
        # downstream needs this note in this turn, so a failed week is a missing
        # line — the next session finds the week still owed and tries again.
        CFG.LOGGER.debug(f"memory-week: the small model failed: {error}")
        return ""
    return claim_from(str(result.output or ""))


def claim_from(text: str) -> str:
    """The sentence in *text*, or ``""`` when there is none the store can hold.

    The model is asked for a sentence and may decorate it — a bullet, a heading,
    a quote. The decoration is stripped rather than refused. The sentence itself
    is checked, because a week note is read back inside a prompt and text that
    reads as an instruction is not a claim.
    """
    for raw in text.splitlines():
        line = _undecorated(raw)
        if not line:
            continue
        if injection_reason(line):
            return ""
        return _bounded(line)
    return ""


def _undecorated(raw: str) -> str:
    """One line of the reply with the decoration a model adds removed.

    Bullets, headings, quotation marks and emphasis are stripped in that order:
    a model asked for one sentence often wraps it in the shape of one anyway,
    and `**The week.**` is the sentence with a costume on.
    """
    line = raw.strip().lstrip(">-*# ").strip()
    line = line.strip("\"'“”").strip()
    return line.strip("*_").strip()


def _bounded(text: str) -> str:
    """*text* cut to a claim's length at a word boundary, or returned whole.

    The store refuses an over-long claim to a model that can be corrected; this
    writer cannot be, so it clips the way the log line does — a week keeps the
    start of a sentence rather than losing the sentence to its last clause.
    """
    if len(text) <= MAX_CLAIM_CHARS:
        return text
    head = text[: MAX_CLAIM_CHARS - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    if not head:
        head = text[: MAX_CLAIM_CHARS - 1]
    return f"{head}…"


def _save_note(week: str, claim: str) -> None:
    """Write the note under the store's lock, and commit it like any other write.

    The question that triggered this call — "is the week still owed?" — was asked
    outside the lock, and a model call sits between the two. Two sessions can pass
    that check on the same week and both come back with a sentence; without the
    second question below, the later writer replaces the earlier note and the week
    says something nobody chose twice. The lock asks it again, so the first note
    stands and the second is dropped.

    The duplicate model call is the price of not holding the store's lock across a
    network wait: the note is at most a small call a week, and a lock held for ten
    seconds would stall every log line and every reviewer write in the meantime.
    """
    try:
        with store.locked():
            if store.load_week(week) is not None:
                return
            store.save_week(
                WeekNote(id=week, claim=claim, source=SOURCE, updated=store.now())
            )
            store.git_commit(f"week: {week}")
    except OSError as error:
        CFG.LOGGER.debug(f"memory-week: {week} was not written: {error}")
