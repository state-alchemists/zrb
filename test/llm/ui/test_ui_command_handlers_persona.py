from unittest.mock import MagicMock, patch

import pytest


class TestBaseUIPersonaSwap:
    """Tests for BaseUI command handler methods."""

    @pytest.fixture
    def simple_ui_instance(self):
        """Create a SimpleUI instance for testing BaseUI methods."""
        from zrb.context.context import Context
        from zrb.context.shared_context import SharedContext
        from zrb.llm.ui import SimpleUI, UIConfig

        class TestSimpleUI(SimpleUI):
            async def print(self, text: str, kind: str = "text"):
                pass

            async def get_input(self, prompt: str) -> str:
                return "test"

        ctx = Context(SharedContext(), "test", 0, "")
        return TestSimpleUI(
            ctx=ctx,
            llm_task=MagicMock(),
            history_manager=MagicMock(),
            config=UIConfig.default(),
        )

    def test_load_ordinary_session_does_not_touch_persona(self, simple_ui_instance):
        """Loading a plain (non-delegated) session name, never having swapped
        away, must not touch the persona at all."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            assert ui.handle_load_command("/load my-project-chat") is True

        mock_manager.get_agent_definition.assert_not_called()
        assert ui.active_subagent_persona is None

    def test_load_delegated_session_swaps_persona(self, simple_ui_instance):
        """Loading a delegated sub-agent's transcript must swap the running
        task's tools/toolsets/prompt_manager and the UI's model to match."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        original_toolsets = ["original-toolset"]
        original_prompt_manager = MagicMock()
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = original_toolsets
        ui.llm_task.prompt_manager = original_prompt_manager
        ui.model = "main-model"

        definition = SubAgentDefinition(
            name="code-reviewer", path=".", description="d", system_prompt="p"
        )
        resolved = MagicMock(
            model="reviewer-model",
            system_prompt="You are a code reviewer.",
            tools=["reviewer-tool"],
            toolsets=["reviewer-toolset"],
        )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = definition
            mock_manager.resolve_agent_build.return_value = resolved

            result = ui.handle_load_command("/load sess1-sub-code-reviewer-a1b2c3d4")

        assert result is True
        mock_manager.get_agent_definition.assert_called_once_with("code-reviewer")
        assert ui.llm_task.tools == ["reviewer-tool"]
        assert ui.llm_task.toolsets == ["reviewer-toolset"]
        assert ui.llm_task.prompt_manager is not original_prompt_manager
        assert ui.model == "reviewer-model"
        assert ui.active_subagent_persona == "code-reviewer"

    def test_load_delegated_session_unknown_agent_reports_error(
        self, simple_ui_instance
    ):
        """An unresolvable agent must not silently swap — report and stay on
        the main agent."""
        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        ui.append_to_output = MagicMock()

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = None
            result = ui.handle_load_command("/load sess1-sub-ghost-agent-deadbeef")

        assert result is True
        assert ui.active_subagent_persona is None
        assert any(
            "ghost-agent" in str(call) for call in ui.append_to_output.call_args_list
        )

    def test_load_back_to_ordinary_session_restores_main_persona(
        self, simple_ui_instance
    ):
        """/load-ing back to an ordinary session name after a swap restores
        the original (main-agent) tools/toolsets/prompt_manager/model."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        original_toolsets = ["original-toolset"]
        original_prompt_manager = MagicMock()
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = original_toolsets
        ui.llm_task.prompt_manager = original_prompt_manager
        ui.model = "main-model"

        definition = SubAgentDefinition(
            name="researcher", path=".", description="d", system_prompt="p"
        )
        resolved = MagicMock(
            model="researcher-model",
            system_prompt="You research.",
            tools=["researcher-tool"],
            toolsets=["researcher-toolset"],
        )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.return_value = definition
            mock_manager.resolve_agent_build.return_value = resolved
            ui.handle_load_command("/load sess1-sub-researcher-deadbeef")

            result = ui.handle_load_command("/load my-project-chat")

        assert result is True
        assert ui.llm_task.tools == original_tools
        assert ui.llm_task.toolsets == original_toolsets
        assert ui.llm_task.prompt_manager is original_prompt_manager
        assert ui.model == "main-model"
        assert ui.active_subagent_persona is None

    def test_load_second_subagent_keeps_the_original_main_snapshot(
        self, simple_ui_instance
    ):
        """Swapping A -> B must restore the ORIGINAL main persona when going
        back, not B's persona re-labeled as "main"."""
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        ui = simple_ui_instance
        ui.load_commands = ["/load"]
        ui.history_manager.load = MagicMock(return_value=[])
        original_tools = ["original-tool"]
        ui.llm_task.tools = original_tools
        ui.llm_task.toolsets = []
        ui.llm_task.prompt_manager = MagicMock()
        ui.model = "main-model"

        def make_definition(name):
            return SubAgentDefinition(
                name=name, path=".", description="d", system_prompt="p"
            )

        with patch("zrb.llm.agent.subagent.manager.sub_agent_manager") as mock_manager:
            mock_manager.get_agent_definition.side_effect = (
                lambda name: make_definition(name)
            )
            mock_manager.resolve_agent_build.side_effect = lambda definition, **_: (
                MagicMock(
                    model=f"{definition.name}-model",
                    system_prompt=f"You are {definition.name}.",
                    tools=[f"{definition.name}-tool"],
                    toolsets=[],
                )
            )

            ui.handle_load_command("/load sess1-sub-researcher-deadbeef")
            ui.handle_load_command("/load sess1-sub-code-reviewer-a1b2c3d4")
            ui.handle_load_command("/load my-project-chat")

        assert ui.llm_task.tools == original_tools
        assert ui.model == "main-model"
        assert ui.active_subagent_persona is None
