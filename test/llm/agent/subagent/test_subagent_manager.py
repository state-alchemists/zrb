from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.prompt.tool_guidance import ToolGuidance


def test_sub_agent_manager_add_tool():
    manager = SubAgentManager()

    def my_tool():
        """My tool"""
        return "ok"

    manager.add_tool(my_tool)

    agent_def = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=["my_tool"],
    )
    manager.add_agent(agent_def)

    with patch(
        "zrb.llm.agent.subagent.manager.manager.create_agent"
    ) as mock_create_agent:
        manager.create_agent("test-agent")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]
        assert my_tool in resolved_tools


def test_sub_agent_manager_scan():
    manager = SubAgentManager()
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
    manager = SubAgentManager()

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
        tools=["regular_tool", "delegate_tool"],
    )
    manager.add_agent(agent_def)

    # 4. Create the agent and check tools
    with patch(
        "zrb.llm.agent.subagent.manager.manager.create_agent"
    ) as mock_create_agent:
        manager.create_agent("test-agent")
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args.kwargs
        resolved_tools = call_kwargs["tools"]

        # Verify only regular_tool is present
        assert regular_tool in resolved_tools
        assert delegate_tool not in resolved_tools


def test_sub_agent_manager_filter_delegate_tools_from_factory():
    manager = SubAgentManager()

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
        tools=[],
    )
    manager.add_agent(agent_def)

    with patch(
        "zrb.llm.agent.subagent.manager.manager.create_agent"
    ) as mock_create_agent:
        manager.create_agent("test-agent")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]
        assert delegate_tool not in resolved_tools


def test_sub_agent_manager_get_agent_definition_not_found():
    manager = SubAgentManager()
    # manager has some default tools but no default agents registered unless scanned
    # Since we didn't scan, it should be empty
    assert manager.get_agent_definition("non-existent") is None


def test_sub_agent_manager_create_agent_not_found():
    manager = SubAgentManager()
    assert manager.create_agent("non-existent") is None


def test_sub_agent_manager_create_agent_from_instance():
    manager = SubAgentManager()
    mock_agent = MagicMock()
    agent_def = SubAgentDefinition(
        name="inst-agent",
        path=".",
        description="desc",
        system_prompt="prompt",
        agent_instance=mock_agent,
    )
    manager.add_agent(agent_def)
    assert manager.create_agent("inst-agent") == mock_agent


def test_sub_agent_manager_create_agent_from_factory():
    manager = SubAgentManager()
    mock_agent = MagicMock()
    factory = MagicMock(return_value=mock_agent)
    agent_def = SubAgentDefinition(
        name="fact-agent",
        path=".",
        description="desc",
        system_prompt="prompt",
        agent_factory=factory,
    )
    manager.add_agent(agent_def)
    assert manager.create_agent("fact-agent") == mock_agent
    factory.assert_called_once()


def test_sub_agent_manager_reload():
    manager = SubAgentManager()
    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)
    assert manager.get_agent_definition("test") == agent_def

    with patch.object(manager, "_scan_and_load"):
        manager.reload()
    assert manager.get_agent_definition("test") is None


def test_sub_agent_manager_add_toolset():
    manager = SubAgentManager()
    ts = MagicMock()
    manager.add_toolset(ts)

    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        resolved_ts = mock_create.call_args.kwargs["toolsets"]
        assert ts in resolved_ts


def test_sub_agent_manager_add_toolset_factory():
    manager = SubAgentManager()
    ts = MagicMock()
    factory = MagicMock(return_value=ts)
    manager.add_toolset_factory(factory)

    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        resolved_ts = mock_create.call_args.kwargs["toolsets"]
        assert ts in resolved_ts
        factory.assert_called_once()


def test_sub_agent_manager_add_tool_guidance():
    manager = SubAgentManager()
    manager.add_tool_guidance(
        ToolGuidance(
            group_name="My Group",
            tool_name="MyTool",
            when_to_use="When doing X",
            key_rule="Always do Y first.",
        )
    )

    agent_def = SubAgentDefinition(
        name="test", path=".", description="Test agent", system_prompt="You are a bot"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        assert "# Tool Usage Guide" in system_prompt
        assert "## My Group" in system_prompt
        assert "**MyTool**" in system_prompt
        assert "When doing X" in system_prompt
        assert "Always do Y first." in system_prompt
        # Original prompt preserved
        assert "You are a bot" in system_prompt


def test_sub_agent_manager_add_tool_guidance_factory():
    manager = SubAgentManager()

    # Factory produces guidance for a dynamically-named tool
    manager.add_tool_guidance_factory(
        lambda ctx: ToolGuidance(
            group_name="Dynamic",
            tool_name="DynamicTool",
            when_to_use="When something changes",
            key_rule="Check ctx first.",
        )
    )

    agent_def = SubAgentDefinition(
        name="test", path=".", description="Test agent", system_prompt="You are a bot"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        assert "# Tool Usage Guide" in system_prompt
        assert "## Dynamic" in system_prompt
        assert "**DynamicTool**" in system_prompt
        assert "When something changes" in system_prompt
        assert "Check ctx first." in system_prompt


def test_sub_agent_manager_add_tool_guidance_factory_multiple():
    manager = SubAgentManager()

    manager.add_tool_guidance_factory(
        lambda ctx: ToolGuidance("Zrb Tasks", "ListZrbTasks", "List tasks"),
        lambda ctx: ToolGuidance(
            "Zrb Tasks", "RunZrbTask", "Run a task", "Verify first"
        ),
    )

    agent_def = SubAgentDefinition(
        name="test", path=".", description="desc", system_prompt="prompt"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        assert "**ListZrbTasks**" in system_prompt
        assert "**RunZrbTask**" in system_prompt
        assert "Verify first" in system_prompt


def test_sub_agent_manager_add_tool_guidance_section_factory():
    manager = SubAgentManager()

    # Section factory that prepends a model-aware note
    manager.add_tool_guidance_section_factory(
        lambda ctx, model: "## Custom Section\n- Model note here."
    )

    agent_def = SubAgentDefinition(
        name="test", path=".", description="desc", system_prompt="prompt"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        assert "## Custom Section" in system_prompt
        assert "Model note here." in system_prompt


def test_sub_agent_manager_add_tool_guidance_section_factory_silent():
    """Section factory returning None/empty should not inject anything."""
    manager = SubAgentManager()

    manager.add_tool_guidance_section_factory(lambda ctx, model: None)
    manager.add_tool_guidance_section_factory(lambda ctx, model: "")

    agent_def = SubAgentDefinition(
        name="test", path=".", description="desc", system_prompt="base"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        # No guidance registered, no sections rendered → just the base prompt
        assert system_prompt == "base"


def test_sub_agent_manager_add_tool_guidance_section_factory_with_guidance():
    """Section factory output appears above per-tool guidance."""
    manager = SubAgentManager()

    manager.add_tool_guidance(ToolGuidance("Group", "MyTool", "Use it.", "Key rule."))
    manager.add_tool_guidance_section_factory(
        lambda ctx, model: "## Policy\n- Parallel calls not supported."
    )

    agent_def = SubAgentDefinition(
        name="test", path=".", description="desc", system_prompt="You are a bot"
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("test")
        system_prompt = mock_create.call_args.kwargs["system_prompt"]
        # Section appears above per-tool group
        policy_idx = system_prompt.index("## Policy")
        group_idx = system_prompt.index("## Group")
        assert policy_idx < group_idx


def test_sub_agent_manager_add_tool_guidance_section_factory_with_model():
    """Section factory receives the resolved model."""
    manager = SubAgentManager()
    captured_models = []

    manager.add_tool_guidance_section_factory(
        lambda ctx, model: captured_models.append(model) or None
    )

    agent_def = SubAgentDefinition(
        name="test",
        path=".",
        description="desc",
        system_prompt="prompt",
        model="openai:gpt-4o",
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent"):
        manager.create_agent("test")
        assert len(captured_models) == 1
        assert captured_models[0] is not None
