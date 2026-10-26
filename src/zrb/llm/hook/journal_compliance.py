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
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
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
    manager.register_hook_config(
        build_journal_compliance_hook_config(), source="builtin"
    )
