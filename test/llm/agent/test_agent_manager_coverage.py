import pytest
from unittest.mock import MagicMock, patch
from zrb.llm.agent.manager import SubAgentManager, SubAgentDefinition

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
        system_prompt="You are a helper"
    )
    assert config.name == "test-agent"
    assert config.system_prompt == "You are a helper"
