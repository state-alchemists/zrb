"""The built-in journal-compliance judge: a Stop hook active whenever
`LLM_JOURNAL_ENABLED` is on.

Registered as a hook factory on the default `hook_manager`. The
`journal-compliance-judge` entry in `examples/llm-hooks/.zrb/hooks.json` is the
same recipe written as user config.
"""

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.schema import AgentHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator
from zrb.llm.journal_usage_log import record_judged, record_judging
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
    from zrb.llm.hook.manager import HookManager

_NAME = "journal-compliance-judge"


# A tool-calling round-trip takes ~15s even on a small model; shutdown waits
# this long before cancelling, so a one-shot `zrb llm chat` doesn't kill it.
_TIMEOUT_SECONDS = 60


def build_journal_compliance_hook_config() -> HookConfig:
    """The judge's `HookConfig`, run on the configured small model.

    The prompt is fetched per call so the usual prompt overrides apply."""
    return HookConfig(
        name=_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt=get_prompt("journal_compliance"),
            # The handover writer is deliberately absent. This hook fires at the
            # STOP of every turn the matcher selects, not at the end of a
            # session, so a handover written here would claim a stop that did not
            # happen — and could replace the one the session itself left. The day
            # block names `WriteDayHandover` for the agent that is actually
            # leaving.
            tools=["LogActivity", "WriteJournalNote", "SearchJournal"],
            # Not `str()`: the fallback may be a `Model` instance, whose repr
            # is not a model name.
            model=resolve_configured_small_model(),
        ),
        matchers=[
            MatcherConfig(
                # A turn that wrote files or stated a preference, or a conversation
                # that has run long enough to be checked. Precomputed in `runner.py`
                # because MatcherConfig has no OR.
                field="event_data.journal_due",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        timeout=_TIMEOUT_SECONDS,
    )


def register_journal_compliance_hook(manager: "HookManager") -> None:
    """Hook factory: register the judge on *manager* unless journaling is off, or
    `LLM_JOURNAL_COMPLIANCE_ENABLED` says no. Its own switch exists so the judge can
    be left out while the rest of journaling carries on — the same shape
    `LLM_SELF_REVIEW_ENABLED` gives the self-review gate."""
    if not CFG.LLM_JOURNAL_ENABLED or not CFG.LLM_JOURNAL_COMPLIANCE_ENABLED:
        return
    config = build_journal_compliance_hook_config()
    hook = manager.register_hook_config(config, source="builtin")
    if hook is None:
        return
    # The judge is an async hook, so it is spawned fire-and-forget: nothing
    # downstream sees whether it ran or what it decided, and "no entry" cannot be
    # told apart from "never fired". The replacement callable records both ends.
    manager.remove_hook(hook)
    manager.add_hook(_recorded(hook), config.events, config)


def _recorded(hook: "HookCallable") -> "HookCallable":
    """*hook*, with each run written to the journal usage log.

    `judging` before the model call and `judged` after, so a run that never comes
    back is a start with no end rather than silence.
    """

    async def recorded(context: "HookContext") -> "HookResult":
        record_judging()
        try:
            result = await hook(context)
        except Exception:
            record_judged(tool_calls=0, failed=True)
            raise
        record_judged(tool_calls=result.tool_calls, failed=not result.success)
        return result

    return recorded
