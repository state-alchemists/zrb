'The built-in journal-compliance judge: registered only while journaling is'

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.journal_compliance import (
    build_journal_compliance_hook_config,
    register_journal_compliance_hook,
)
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent, HookType


def _mock_agent_cls(output: str = "skip"):
    'A patchable pydantic_ai.Agent whose run() resolves immediately.'
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    return MagicMock(return_value=agent_instance)


def test_hook_config_shape():
    config = build_journal_compliance_hook_config()
    assert config.name == "journal-compliance-judge"
    assert config.events == [HookEvent.STOP]
    assert config.type == HookType.AGENT
    assert config.config.tools == [
        "LogActivity",
        "WriteJournalNote",
        "SearchJournal",
    ]
    assert config.is_async is True
    assert len(config.matchers) == 1
    matcher = config.matchers[0]
    assert matcher.field == "event_data.journal_worthy"
    assert matcher.value is True


@pytest.mark.asyncio
async def test_registers_when_journal_enabled():
    "A registered hook actually fires (as a backgrounded task, since it's"
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

    assert results == []
    assert manager.has_pending_background_hooks is True
    await manager.shutdown()


@pytest.mark.asyncio
async def test_fires_on_a_stated_preference_with_no_file_write():
    'The widened trigger: `journal_worthy` is `wrote_files OR'
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
    '`add_hook_factory` used to only run through a manual `scan()`/'
    manager = HookManager(search_dirs=[])
    with patch("zrb.llm.hook.journal_compliance.CFG") as mock_cfg:
        mock_cfg.LLM_JOURNAL_ENABLED = True
        manager.add_hook_factory(register_journal_compliance_hook)



        await manager.execute_hooks(HookEvent.NOTIFICATION, {})

        agent_cls = _mock_agent_cls()
        with (
            patch(
                "zrb.llm.hook.creator.resolve_configured_model"
            ) as mock_resolve_model,
            patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
        ):
            mock_resolve_model.return_value = "resolved"
            await manager.execute_hooks(
                HookEvent.STOP, {"wrote_files": True, "journal_worthy": True}
            )

    assert manager.has_pending_background_hooks is True
    await manager.shutdown()


def test_hook_config_keeps_a_resolved_model_object():
    "The run's own model is a pydantic-ai `Model`, and `str()` of one is its"
    resolved = MagicMock()
    with patch(
        "zrb.llm.hook.journal_compliance.resolve_configured_small_model",
        return_value=resolved,
    ):
        config = build_journal_compliance_hook_config()
    assert config.config.model is resolved
