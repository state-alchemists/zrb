"""Tests for BuilderMixin (registration API, properties, agent/prompt assembly).

Exercised through the public ``LLMTask`` surface, which composes BuilderMixin.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.fixture
def shared_ctx():
    return SharedContext()


@pytest.fixture
def session(shared_ctx):
    return Session(shared_ctx=shared_ctx, state_logger=MagicMock())


class TestProperties:
    def test_tool_confirmation_and_prompt_manager(self):
        task = LLMTask(name="test-task")
        conf = MagicMock()
        task.tool_confirmation = conf
        assert task.tool_confirmation == conf
        assert task.prompt_manager is not None

    def test_custom_model_names_constructor_and_property(self):
        names = ["my-model", "other-model"]
        task = LLMTask(name="test-task", custom_model_names=names)
        assert task.custom_model_names == names

    def test_custom_model_names_setter(self):
        task = LLMTask(name="test-task")
        task.custom_model_names = ["updated-model"]
        assert task.custom_model_names == ["updated-model"]

    def test_history_manager_property(self):
        task = LLMTask(name="test-task")
        assert task.history_manager is None
        manager = MagicMock()
        task.history_manager = manager
        assert task.history_manager is manager

    def test_approval_channel_property(self):
        task = LLMTask(name="test-task")
        assert task.approval_channel is None
        channel = MagicMock()
        task.approval_channel = channel
        assert task.approval_channel is channel

    def test_permissions_constructor_and_property(self):
        from zrb.llm.permission import ALLOW, PermissionPolicy, Rule

        policy = PermissionPolicy((Rule("*", ALLOW),))
        task = LLMTask(name="test-task", permissions=policy)
        assert task.permissions is policy

    def test_permissions_setter(self):
        from zrb.llm.permission import DENY, PermissionPolicy, Rule

        policy = PermissionPolicy((Rule("*", DENY),))
        task = LLMTask(name="test-task")
        assert task.permissions is None
        task.permissions = policy
        assert task.permissions is policy

    def test_sandbox_constructor_and_property(self):
        from zrb.llm.sandbox import SandboxPolicy

        policy = SandboxPolicy(enabled=True)
        task = LLMTask(name="test-task", sandbox=policy)
        assert task.sandbox is policy

    def test_sandbox_setter(self):
        from zrb.llm.sandbox import SandboxPolicy

        policy = SandboxPolicy(enabled=True)
        task = LLMTask(name="test-task")
        assert task.sandbox is None
        task.sandbox = policy
        assert task.sandbox is policy


class TestRegistration:
    def test_append_tool_and_get_all_tools(self):
        tool_a, tool_b = MagicMock(), MagicMock()
        task = LLMTask(name="test-task")
        task.add_tool(tool_a)
        task.append_tool(tool_b)
        resolved = task._get_all_tools(MagicMock())
        assert tool_a in resolved and tool_b in resolved

    def test_tool_factory_resolved_in_get_all_tools(self):
        tool = MagicMock()
        task = LLMTask(name="test-task")
        task.add_tool_factory(lambda ctx: tool)
        assert tool in task._get_all_tools(MagicMock())

    def test_append_toolset_and_get_all_toolsets(self):
        toolset = MagicMock()
        task = LLMTask(name="test-task")
        task.add_toolset(toolset)
        assert toolset in task._get_all_toolsets(MagicMock())

    def test_toolset_factory_resolved_in_get_all_toolsets(self):
        toolset = MagicMock()
        task = LLMTask(name="test-task")
        task.add_toolset_factory(lambda ctx: toolset)
        assert toolset in task._get_all_toolsets(MagicMock())

    def test_set_ui_replaces_and_append_ui_adds(self):
        ui_a, ui_b = MagicMock(), MagicMock()
        task = LLMTask(name="test-task", ui=ui_a)
        task.append_ui(ui_b)
        # set_ui replaces the whole list
        task.set_ui(ui_a)
        # append again to confirm list semantics
        task.append_ui(ui_b)
        assert task._uis == [ui_a, ui_b]

    @pytest.mark.asyncio
    async def test_add_hook_factory_isolates_and_reaches_runner(self, session):
        """add_hook_factory must (a) register the hook so it fires, and (b) NOT
        mutate the shared global manager — the first registration swaps in a
        task-local manager, which is the one handed to the runner."""
        from zrb.llm.hook.interface import HookContext, HookResult
        from zrb.llm.hook.manager import hook_manager as global_manager
        from zrb.llm.hook.types import HookEvent

        fired: list[str] = []

        async def my_hook(context: HookContext) -> HookResult:
            fired.append(context.event.value)
            return HookResult()

        task = LLMTask(name="test-task", message="hello")
        task.add_hook_factory(
            lambda mgr: mgr.register(my_hook, events=[HookEvent.SESSION_START])
        )

        with (
            patch("zrb.llm.task.llm_task.create_agent"),
            patch(
                "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
        ):
            mock_run_agent.return_value = ("Response", [])
            await task.async_run(session)
            _, kwargs = mock_run_agent.call_args
            task_manager = kwargs["hook_manager"]

        # The task got its own manager, not the shared global.
        assert task_manager is not global_manager
        # The hook fires on the task-local manager (behavioral, public API)...
        await task_manager.execute_hooks(HookEvent.SESSION_START, {})
        assert fired == ["SessionStart"]
        # ...but the global manager was left untouched (no leak).
        fired.clear()
        await global_manager.execute_hooks(HookEvent.SESSION_START, {})
        assert fired == []


class TestAssembly:
    def test_get_model_defaults_to_llm_config_model(self):
        task = LLMTask(name="test-task")
        assert task._get_model(MagicMock()) == task.llm_config.model

    def test_get_model_uses_explicit_model(self):
        task = LLMTask(name="test-task", model="explicit-model", render_model=False)
        assert task._get_model(MagicMock()) == "explicit-model"

    def test_get_model_treats_blank_string_as_unset(self):
        task = LLMTask(name="test-task", model="   ", render_model=False)
        # Blank explicit model falls back to the config default.
        assert task._get_model(MagicMock()) == task.llm_config.model

    def test_get_model_settings_falls_back_to_config(self):
        task = LLMTask(name="test-task")
        assert task._get_model_settings(MagicMock()) == task.llm_config.model_settings

    def test_tool_guidance_factory_is_resolved_with_context(self):
        from zrb.llm.prompt.tool_guidance import ToolGuidance

        guidance = ToolGuidance(
            group_name="MyGroup",
            tool_name="MyTool",
            when_to_use="when X",
            key_rule="do Y",
        )
        factory = MagicMock(return_value=guidance)
        task = LLMTask(name="test-task")
        task.add_tool_guidance_factory(factory)
        ctx = MagicMock()
        task._resolve_tool_guidance_factories(ctx)
        factory.assert_called_once_with(ctx)

    def test_tool_guidance_section_factory_sets_sections(self):
        task = LLMTask(name="test-task")
        task.add_tool_guidance_section_factory(lambda ctx, model: "## Extra section")
        task._resolve_tool_guidance_factories(MagicMock())
        assert task.prompt_manager.tool_guidance_sections == ["## Extra section"]
