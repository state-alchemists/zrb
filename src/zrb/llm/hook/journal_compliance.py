"""The built-in journal-compliance judge — a Stop hook, active whenever
`LLM_JOURNAL_ENABLED` is on, with no separate switch of its own.

Registered as a hook factory (`add_hook_factory`) on the default `hook_manager`
singleton, so any code path that reaches the lazy-loaded default gets it for
free. It mirrors the `journal-compliance-judge` recipe documented in
`docs/llm/hooks.md` and shipped (disabled) in
`examples/llm-hooks/.zrb/hooks.json` — that JSON entry stays as a worked
example of writing your own agent hook; this module is what actually runs.
"""

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.schema import AgentHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from zrb.llm.hook.manager import HookManager

_NAME = "journal-compliance-judge"


#: A tool-calling round-trip measured ~15s even on a small model.
#: `HookManager.shutdown` waits this long before cancelling the async hook, so
#: a one-shot `zrb llm chat` doesn't kill the judge on exit. Fire-and-forget,
#: so generous costs nothing.
_TIMEOUT_SECONDS = 60


def build_journal_compliance_hook_config() -> HookConfig:
    """The judge's `HookConfig` — the small/fast model keeps it cheap by
    default (the same model summarization already uses), not the potentially
    expensive main model. Resolved from the current run's UI-level override
    (`/model small ...`) when there is one, else `CFG.LLM_SMALL_MODEL`.

    The system prompt is loaded fresh via `get_prompt("journal_compliance")`
    (not a module constant) so it goes through the normal prompt-override
    chain — a project's `LLM_PROMPT_DIR`/`markdown/journal_compliance.md`, or
    `ZRB_LLM_PROMPT_JOURNAL_COMPLIANCE` — the same way `message_summarizer`
    and the other internal-agent prompts are overridable."""
    return HookConfig(
        name=_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt=get_prompt("journal_compliance"),
            tools=["LogActivity", "WriteJournalNote", "SearchJournal"],
            # Not `str()`: the fallback may be a `Model` instance, whose repr
            # is not a model name.
            model=resolve_configured_small_model(),
        ),
        matchers=[
            MatcherConfig(
                # wrote_files OR looks like a stated preference (see
                # `turn_evidence.turn_states_preference`) — computed together
                # at dispatch (`runner.py`) since MatcherConfig has no OR.
                field="event_data.journal_worthy",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        timeout=_TIMEOUT_SECONDS,
    )


def register_journal_compliance_hook(manager: "HookManager") -> None:
    """Hook factory: register the judge on *manager*, unless journaling is
    off. The tool-resolution skip-guard in `create_agent_hook` would also
    make it a no-op in that case (the journal tools don't exist to resolve),
    but checking here avoids registering — and matcher-evaluating on every
    Stop — a hook that can never do anything."""
    if not CFG.LLM_JOURNAL_ENABLED:
        return
    manager.register_hook_config(
        build_journal_compliance_hook_config(), source="builtin"
    )
