"""The built-in journal-compliance judge: registered only while journaling is
on, and only through the actual lazy-loading path a real chat session uses."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.journal_compliance import (
    build_journal_compliance_hook_config,
    register_journal_compliance_hook,
)
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent, HookType


def _mock_agent_cls(output: str = "skip"):
    """A patchable pydantic_ai.Agent whose run() resolves immediately."""
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    return MagicMock(return_value=agent_instance)


def test_hook_config_shape():
    config = build_journal_compliance_hook_config()
    assert config.name == "journal-compliance-judge"
    assert config.events == [HookEvent.STOP]
    assert config.type == HookType.AGENT
    assert config.config.tools == ["LogActivity", "WriteJournalNote", "SearchJournal"]
    assert config.is_async is True
    assert len(config.matchers) == 1
    matcher = config.matchers[0]
    assert matcher.field == "event_data.journal_worthy"
    assert matcher.value is True


@pytest.mark.asyncio
async def test_registers_when_journal_enabled():
    """A registered hook actually fires (as a backgrounded task, since it's
    async) for a Stop event that wrote files — checked behaviorally, not by
    reaching into HookManager's private registration dicts.

    `HookManager()` seeds `register_journal_compliance_hook` as a default
    factory, run by `_ensure_loaded()` on the `execute_hooks` call below — so
    the CFG mock must still be active then, not just around a manual call
    (the test suite's own ambient default is journal-disabled — see
    conftest.py's `_TEST_ENV` — precisely so a manager built this way is
    inert unless a test opts back in like this one does)."""
    manager = HookManager(search_dirs=[])
    agent_cls = _mock_agent_cls()
    with (
        patch("zrb.llm.hook.journal_compliance.CFG") as mock_cfg,
        patch("zrb.llm.hook.creator.resolve_configured_model") as mock_resolve_model,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_cfg.LLM_JOURNAL_ENABLED = True
        mock_resolve_model.return_value = "resolved"
        results = await manager.execute_hooks(
            HookEvent.STOP, {"wrote_files": True, "journal_worthy": True}
        )

    assert results == []  # fire-and-forget contributes no result
    assert manager.has_pending_background_hooks is True
    await manager.shutdown()


@pytest.mark.asyncio
async def test_fires_on_a_stated_preference_with_no_file_write():
    """The widened trigger: `journal_worthy` is `wrote_files OR
    turn_states_preference`, computed at dispatch (runner.py) — so a turn
    that only stated a preference, with `wrote_files` false, still fires the
    judge. Closes the blind spot WriteJournalNote's own docstring calls
    highest-value: a preference said once, with no file edit."""
    manager = HookManager(search_dirs=[])
    agent_cls = _mock_agent_cls()
    with (
        patch("zrb.llm.hook.journal_compliance.CFG") as mock_cfg,
        patch("zrb.llm.hook.creator.resolve_configured_model") as mock_resolve_model,
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    ):
        mock_cfg.LLM_JOURNAL_ENABLED = True
        mock_resolve_model.return_value = "resolved"
        results = await manager.execute_hooks(
            HookEvent.STOP, {"wrote_files": False, "journal_worthy": True}
        )

    assert results == []
    assert manager.has_pending_background_hooks is True
    await manager.shutdown()


@pytest.mark.asyncio
async def test_does_not_register_when_journal_disabled():
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.hook.journal_compliance.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_ENABLED = False
        results = await manager.execute_hooks(
            HookEvent.STOP, {"wrote_files": True, "journal_worthy": True}
        )

    assert results == []
    assert manager.has_pending_background_hooks is False


@pytest.mark.asyncio
async def test_factory_fires_via_the_normal_lazy_load_path():
    """`add_hook_factory` used to only run through a manual `scan()`/
    `reload()` call — the automatic lazy path (`execute_hooks` on first use,
    which is what every real chat session actually takes) skipped factories
    entirely, so a hook registered this way was silently never installed.
    This exercises that real path, not the manual one."""
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.hook.journal_compliance.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_ENABLED = True
        manager.add_hook_factory(register_journal_compliance_hook)

        # No manual scan()/reload() — this is the first hook access a real
        # `LLMChatTask` run makes.
        await manager.execute_hooks(HookEvent.NOTIFICATION, {})

        agent_cls = _mock_agent_cls()
        with (
            patch("zrb.llm.hook.creator.resolve_configured_model") as mock_resolve_model,
            patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
        ):
            mock_resolve_model.return_value = "resolved"
            await manager.execute_hooks(
                HookEvent.STOP, {"wrote_files": True, "journal_worthy": True}
            )

    assert manager.has_pending_background_hooks is True
    await manager.shutdown()
