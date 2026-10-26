"""Tests for a built-in hook's own on/off switch.

Each switch is a boolean named like every other feature flag in the config
(`LLM_SELF_REVIEW_ENABLED`, `LLM_JOURNAL_GIT_ENABLED`) rather than one shared
list of names: a list has no schema, is invisible in a config listing, and a typo
in it silently disables nothing. These tests pin that each switch decides its own
hook, and that journaling off still takes both out.
"""

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

from zrb.config.config import CFG
from zrb.llm.hook.journal_compliance import register_journal_compliance_hook
from zrb.llm.hook.journal_day_flush import register_journal_day_flush_hook

if TYPE_CHECKING:
    from zrb.llm.hook.manager import HookManager


class _FakeManager:
    def __init__(self):
        self.registered = []

    def add_hook(self, hook, events=None, config=None):
        self.registered.append(hook)

    def register_hook_config(self, config, source=None):
        self.registered.append(config)


FACTORIES = {
    "journal_day_flush": (
        register_journal_day_flush_hook,
        "LLM_JOURNAL_DAY_FLUSH_ENABLED",
    ),
    "journal_compliance": (
        register_journal_compliance_hook,
        "LLM_JOURNAL_COMPLIANCE_ENABLED",
    ),
}


def _register(
    module: str, journal_on: bool = True, hook_on: bool = True
) -> "_FakeManager":
    """Register one built-in hook's factory with both of its switches set.

    The factory reads `CFG` under its own module's name, so patching that one
    binding leaves the other hook's factory on the real config — which is what
    makes the two switches independent rather than merely different fields.
    """
    factory, switch = FACTORIES[module]
    manager = _FakeManager()
    with patch(f"zrb.llm.hook.{module}.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = journal_on
        setattr(cfg, switch, hook_on)
        factory(cast("HookManager", manager))
    return manager


def test_the_flush_has_its_own_switch():
    assert len(_register("journal_day_flush", hook_on=True).registered) == 1
    assert _register("journal_day_flush", hook_on=False).registered == []


def test_the_compliance_judge_has_its_own_switch():
    assert len(_register("journal_compliance", hook_on=True).registered) == 1
    assert _register("journal_compliance", hook_on=False).registered == []


def test_journaling_off_still_takes_both_out():
    assert _register("journal_day_flush", journal_on=False).registered == []
    assert _register("journal_compliance", journal_on=False).registered == []


def test_both_switches_default_to_on():
    """The hook is on out of the box, like `LLM_JOURNAL_GIT_ENABLED`: a record a
    journal-less setup does not get is the thing the day tier was built to fix."""
    assert CFG.DEFAULT_LLM_JOURNAL_DAY_FLUSH_ENABLED == "on"
    assert CFG.DEFAULT_LLM_JOURNAL_COMPLIANCE_ENABLED == "on"
