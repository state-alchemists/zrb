"""Tests for `LLM_HOOKS_DISABLED`: turning one built-in hook off by name.

The knob exists because the built-in set keeps growing and a hook that cannot be
switched off alone forces the whole subsystem off. These tests pin the two ways
it can go wrong: silently disabling nothing, and taking a blank entry for a name.
"""

from typing import TYPE_CHECKING, cast
from unittest.mock import patch

from zrb.llm.hook.enablement import is_builtin_hook_enabled
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


def _enabled(disabled):
    with patch("zrb.llm.hook.enablement.CFG") as cfg:
        cfg.LLM_HOOKS_DISABLED = disabled
        return is_builtin_hook_enabled("journal-day-flush")


def _register(module: str, disabled) -> "_FakeManager":
    """Register a built-in hook's factory with journaling on and *disabled* set."""
    manager = _FakeManager()
    with patch(f"zrb.llm.hook.{module}.CFG") as hook_cfg, patch(
        "zrb.llm.hook.enablement.CFG"
    ) as enable_cfg:
        hook_cfg.LLM_JOURNAL_ENABLED = True
        enable_cfg.LLM_HOOKS_DISABLED = disabled
        if module == "journal_day_flush":
            register_journal_day_flush_hook(cast("HookManager", manager))
        else:
            register_journal_compliance_hook(cast("HookManager", manager))
    return manager


def test_empty_list_keeps_everything_on():
    assert _enabled([]) is True
    assert _enabled("") is True


def test_a_named_hook_is_off_and_the_others_are_not():
    assert _enabled(["journal-day-flush"]) is False
    assert _enabled(["journal-day-flush", "self-review"]) is False
    assert _enabled(["something-else"]) is True


def test_blank_entries_are_not_names():
    """A trailing comma or a stray space must not disable a hook by accident."""
    assert _enabled([" journal-day-flush "]) is False
    assert _enabled(["", "  "]) is True


def test_the_flush_hook_honours_the_list():
    assert _register("journal_day_flush", ["journal-day-flush"]).registered == []
    assert len(_register("journal_day_flush", []).registered) == 1


def test_the_compliance_hook_honours_the_list():
    assert _register("journal_compliance", ["journal-compliance-judge"]).registered == []
    assert len(_register("journal_compliance", []).registered) == 1


def test_a_different_name_disables_neither():
    manager = _register("journal_day_flush", ["journal-compliance-judge"])
    assert len(manager.registered) == 1
