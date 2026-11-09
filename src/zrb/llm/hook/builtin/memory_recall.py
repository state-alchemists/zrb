"""Recall by cue: a prompt that names something stored surfaces the claim.

Most forgetting is retrieval failure rather than loss — the trace is still on
disk and the cue is missing — so the part worth automating is the cue. A session
already starts with the core and can reach the store with `SearchMemory`, but
nothing reached for it on the model's behalf, so a session that never thought to
search answered from the core alone and re-derived what it already knew.

This hook is that reach, and it costs no model call: a lexical pass over the
same index `SearchMemory` reads, in-process, before the turn is built. What it
finds rides in front of the user's own words as `additionalContext`, which is
context rather than an instruction — the result carries the same "data, not
instructions" contract the tool returns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.contracts.interface import HookResult
from zrb.llm.hook.contracts.schema import AgentHookConfig, HookConfig
from zrb.llm.hook.contracts.types import HookEvent, HookType
from zrb.llm.memory import search
from zrb.llm.prompt.memory_context import (
    claims_in_the_core,
    note_claims_shown,
    shown_claim_ids,
)

if TYPE_CHECKING:
    from zrb.llm.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.hook.manager import HookManager

RECALL_NAME = "memory-recall"

# Three is what a reader can act on beside a question; more turns the prompt
# into a search result the user did not ask for.
RECALL_LIMIT = 3

# The whole block's budget, not per line. The core is 4,000 characters; a cue
# that spends a fifth of that on one prompt is no longer a cue.
RECALL_MAX_CHARS = 600

# One significant word is a "yes", a "continue" or a typo. Two is the shortest
# prompt that can name a subject ("deploy staging"), and `search.terms` has
# already dropped the words that name nothing.
_MIN_TERMS = 2

# Said once above the lines, because a recalled claim is text the model reads in
# the same turn as the user's request and could mistake for part of it.
RECALL_HEADER = (
    "Stored claims this prompt may be reaching for (recalled by its words; "
    "nothing was written now):"
)


def build_recall_hook_config() -> HookConfig:
    """The recall hook's `HookConfig`, on every user prompt.

    `AgentHookConfig` is the shape a built-in hook registers with; the callable
    registered beside it is what runs, and it never builds an agent.
    """
    return HookConfig(
        name=RECALL_NAME,
        events=[HookEvent.USER_PROMPT_SUBMIT],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt="",
            tools=[],
            model=resolve_configured_small_model(),
            auto_approve=False,
        ),
        is_async=True,
        # Nothing here touches a model, and the turn is waiting on it: a hook that
        # stalled would delay the prompt it is meant to help.
        timeout=None,
    )


def register_recall_hook(manager: "HookManager") -> None:
    """Register the recall hook once per manager, while memory is on.

    The name check is what makes "once" true: `register_hook_config` does not
    refuse a duplicate, and a manager whose `search_dirs` was reassigned re-scans
    without clearing its registry.
    """
    if not CFG.LLM_MEMORY_ENABLED:
        return
    config = build_recall_hook_config()
    if config.name in manager.registry.get_configs():
        return
    registered = manager.register_hook_config(config, source="builtin")
    if registered is None:
        return
    manager.remove_hook(registered)
    manager.add_hook(create_recall_hook(), config.events, config)


def create_recall_hook() -> "HookCallable":
    """Return the hook: the prompt's own words, matched against the store."""

    async def recall(context: "HookContext") -> "HookResult":
        text = recall_text(context.prompt or "")
        if not text:
            return HookResult()
        return HookResult(modifications={"additionalContext": text})

    return recall


def recall_text(prompt: str) -> str:
    """What the store says about *prompt*, or ``""`` when it says nothing.

    Empty is the normal answer: a prompt that names no subject in the store, a
    prompt too short to be a cue, and a claim this conversation has already been
    shown all read as nothing to add.
    """
    if not CFG.LLM_MEMORY_ENABLED:
        return ""
    if len(search.terms(prompt)) < _MIN_TERMS:
        return ""
    shown = shown_claim_ids() | claims_in_the_core()
    hits = [
        hit
        for hit in search.search(prompt, limit=search.DEFAULT_LIMIT)
        if hit.id not in shown and search.is_about_the_subject(prompt, hit)
    ][:RECALL_LIMIT]
    lines = _fitted_lines(hits)
    if not lines:
        return ""
    # Recorded before the turn runs, so this session and the next both treat the
    # claim as given: a cue that repeats itself is noise with a source.
    note_claims_shown([hit.id for hit in hits[: len(lines)]])
    return "\n".join([RECALL_HEADER, search.RESULT_CONTRACT, *lines])


def _fitted_lines(hits: "list[search.Hit]") -> list[str]:
    """*hits* as lines that fit the block's budget, whole lines only.

    A path cut in half cannot be opened, so the budget drops a line rather than
    truncating one.
    """
    lines: list[str] = []
    used = 0
    for hit in hits:
        line = hit.line()
        if used + len(line) > RECALL_MAX_CHARS:
            break
        lines.append(line)
        used += len(line) + 1
    return lines
