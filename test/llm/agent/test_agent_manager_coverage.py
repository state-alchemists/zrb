from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.manager import SubAgentDefinition, SubAgentManager


def test_sub_agent_manager_add_tool():
    manager = SubAgentManager(auto_load=False)
    tool = MagicMock()
    tool.__name__ = "my_tool"
    manager.add_tool(tool)
    assert "my_tool" in manager._tool_registry


def test_sub_agent_manager_scan():
    manager = SubAgentManager(auto_load=False)
    # Scan with empty list should not crash
    manager.scan([])
    assert isinstance(manager.get_search_directories(), list)


def test_sub_agent_manager_create_agent_config():
    config = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="A test agent",
        system_prompt="You are a helper",
    )
    assert config.name == "test-agent"
    assert config.system_prompt == "You are a helper"


def test_sub_agent_manager_filter_delegate_tools():
    manager = SubAgentManager(auto_load=False)

    # 1. Create a regular tool
    def regular_tool():
        """Regular tool"""
        return "ok"

    # 2. Create a delegate tool
    def delegate_tool():
        """Delegate tool"""
        return "nested"
    delegate_tool.zrb_is_delegate_tool = True

    manager.add_tool(regular_tool, delegate_tool)

    # 3. Setup an agent definition that uses both
    agent_def = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=["regular_tool", "delegate_tool"]
    )
    manager.add_agent(agent_def)

    # 4. Create the agent and check tools
    with patch("zrb.llm.agent.manager.create_agent") as mock_create_agent:
        manager.create_agent("test-agent")
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args.kwargs
        resolved_tools = call_kwargs["tools"]

        # Verify only regular_tool is present
        assert regular_tool in resolved_tools
        assert delegate_tool not in resolved_tools


def test_sub_agent_manager_filter_delegate_tools_from_factory():
    manager = SubAgentManager(auto_load=False)

    def delegate_tool():
        """Delegate tool"""
        return "nested"
    delegate_tool.zrb_is_delegate_tool = True

    # Add a factory that returns a delegate tool
    manager.add_tool_factory(lambda ctx: delegate_tool)

    agent_def = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=[]
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.manager.create_agent") as mock_create_agent:
        manager.create_agent("test-agent")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]
        assert delegate_tool not in resolved_tools
