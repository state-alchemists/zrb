from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager


def test_sub_agent_manager_add_tool():
    manager = SubAgentManager()

    def my_tool():
        """My tool"""
        return "ok"

    manager.append_tool(my_tool)

    agent_def = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=["my_tool"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create_agent:
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

    manager.append_tool(regular_tool, delegate_tool)

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
    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create_agent:
        manager.create_agent("test-agent")
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args.kwargs
        resolved_tools = call_kwargs["tools"]

        # Verify only regular_tool is present
        assert regular_tool in resolved_tools
        assert delegate_tool not in resolved_tools


def test_sub_agent_manager_maps_bash_tool_to_shell():
    """A Claude-written sub-agent that lists ``Bash`` gets zrb's ``Shell`` tool.

    ``Bash`` is not a zrb tool; the registry holds ``Shell``. Both the tool
    resolution and the ``disallowedTools`` filter map the Claude name over.
    """
    manager = SubAgentManager()

    def shell_tool():
        """Shell tool"""
        return "ok"

    shell_tool.__name__ = "Shell"
    manager.append_tool(shell_tool)

    agent_def = SubAgentDefinition(
        name="claude-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=["Bash"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create_agent:
        manager.create_agent("claude-agent")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]
        assert shell_tool in resolved_tools


def test_sub_agent_manager_maps_bash_disallowed_tool_to_shell():
    """``disallowedTools: [Bash]`` excludes the ``Shell`` tool."""
    manager = SubAgentManager()

    def shell_tool():
        """Shell tool"""
        return "ok"

    shell_tool.__name__ = "Shell"
    manager.append_tool(shell_tool)

    agent_def = SubAgentDefinition(
        name="claude-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=["Shell"],
        disallowed_tools=["Bash"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create_agent:
        manager.create_agent("claude-agent")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]
        assert shell_tool not in resolved_tools


def test_sub_agent_manager_filter_delegate_tools_from_factory():
    manager = SubAgentManager()

    def delegate_tool():
        """Delegate tool"""
        return "nested"

    delegate_tool.zrb_is_delegate_tool = True

    # Add a factory that returns a delegate tool
    manager.append_tool_factory(lambda ctx: delegate_tool)

    agent_def = SubAgentDefinition(
        name="test-agent",
        path=".",
        description="Test",
        system_prompt="Prompt",
        tools=[],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create_agent:
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
    manager.append_toolset(ts)

    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
        manager.create_agent("test")
        resolved_ts = mock_create.call_args.kwargs["toolsets"]
        assert ts in resolved_ts


def test_sub_agent_manager_add_toolset_factory():
    manager = SubAgentManager()
    ts = MagicMock()
    factory = MagicMock(return_value=ts)
    manager.append_toolset_factory(factory)

    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
        manager.create_agent("test")
        resolved_ts = mock_create.call_args.kwargs["toolsets"]
        assert ts in resolved_ts
        factory.assert_called_once()


def test_sub_agent_definition_defaults_inherit_sections_none():
    """SubAgentDefinition without inherit_sections keeps its own prompt only
    (no parent persona/workflow injected)."""
    agent_def = SubAgentDefinition(
        name="standalone",
        path=".",
        description="d",
        system_prompt="You are a standalone agent.",
    )
    assert agent_def.inherit_sections is None


def test_sub_agent_manager_without_inherit_sections_skips_inheritance():
    """Agents with inherit_sections=None get only body + own guidance —
    no # Persona / # Workflow from the main agent."""
    manager = SubAgentManager()
    agent_def = SubAgentDefinition(
        name="standalone",
        path=".",
        description="d",
        system_prompt="You are a standalone agent. Do X.",
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
        manager.create_agent("standalone")
        prompt = mock_create.call_args.kwargs["system_prompt"]
    assert "You are a standalone agent. Do X." in prompt
    assert "# Persona" not in prompt
    assert "# Workflow" not in prompt


def test_sub_agent_manager_inherit_sections_composes_parent_sections():
    """inherit_sections=[persona, workflow] prepends those rendered sections
    above the agent body."""
    manager = SubAgentManager()
    agent_def = SubAgentDefinition(
        name="inheriting",
        path=".",
        description="d",
        system_prompt="You are an inheriting agent.",
        inherit_sections=["persona", "workflow"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
        manager.create_agent("inheriting")
        prompt = mock_create.call_args.kwargs["system_prompt"]

    persona_idx = prompt.find("# Persona")
    workflow_idx = prompt.find("# Workflow")
    body_idx = prompt.find("You are an inheriting agent.")
    assert persona_idx != -1
    assert workflow_idx != -1
    assert body_idx != -1
    # Inherited sections appear above the agent body.
    assert persona_idx < body_idx
    assert workflow_idx < body_idx


def test_sub_agent_manager_inherits_journal_index():
    """A sub-agent is single-turn, so always "the first turn": the journal index
    is folded into its system prompt (ADR-0042). With no journal prompt section
    left, the flag is honoured inside render_journal_index itself."""
    manager = SubAgentManager()
    agent_def = SubAgentDefinition(
        name="journaler",
        path=".",
        description="d",
        system_prompt="Body.",
        inherit_sections=["persona"],
    )
    manager.add_agent(agent_def)

    journal_block = "<journal-index>\nProject Hub\n</journal-index>"
    with (
        patch(
            "zrb.llm.agent.subagent.manager.render_journal_index",
            return_value=journal_block,
        ),
        patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create,
    ):
        manager.create_agent("journaler")
        prompt = mock_create.call_args.kwargs["system_prompt"]
    assert "Project Hub" in prompt


def test_sub_agent_manager_inherit_sections_empty_list_means_opt_out():
    """inherit_sections=[] explicitly opts out (same observable result as
    None, but documents intent in the agent file)."""
    manager = SubAgentManager()
    agent_def = SubAgentDefinition(
        name="optout",
        path=".",
        description="d",
        system_prompt="Body only.",
        inherit_sections=[],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
        manager.create_agent("optout")
        prompt = mock_create.call_args.kwargs["system_prompt"]
    assert "# Persona" not in prompt
    assert "Body only." in prompt
