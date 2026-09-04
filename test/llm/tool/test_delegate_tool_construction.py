from unittest.mock import MagicMock

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import (
    agent_not_found_message,
    agent_roster_doc,
    create_delegate_to_agent_tool,
    create_search_agent_tool,
)


@pytest.fixture
def mock_sub_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    # Setup scan return value
    agent_def = SubAgentDefinition(
        name="test-agent",
        path="path",
        description="A test agent",
        system_prompt="prompt",
    )
    manager.scan.return_value = [agent_def]
    return manager


def _missing_param_descriptions(fn) -> list[str]:
    from pydantic_ai import Tool

    schema = Tool(fn).function_schema.json_schema
    return [
        param
        for param, spec in schema.get("properties", {}).items()
        if not spec.get("description")
    ]


def _many_agents(count: int) -> list[SubAgentDefinition]:
    return [
        SubAgentDefinition(
            name=f"agent-{i:02d}",
            path="path",
            description=f"Agent {i:02d}",
            system_prompt="prompt",
        )
        for i in range(count)
    ]


def test_create_delegate_tool_docstring(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    assert "test-agent" in tool.__doc__
    assert "A test agent" in tool.__doc__


def test_delegate_to_agent_params_carry_descriptions(mock_sub_agent_manager):
    """Not registered via common_tools.py (main-agent-only, added directly by
    LLMChatTask), so `test_every_registered_tool_parameter_carries_a_description`
    in test/llm/test_common_tools.py never sees this one — pinned here instead."""
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    missing = _missing_param_descriptions(tool)
    assert not missing, f"DelegateToAgent params with no description: {missing}"


def test_search_agent_params_carry_descriptions(mock_sub_agent_manager):
    """Same rationale as test_delegate_to_agent_params_carry_descriptions."""
    tool = create_search_agent_tool(mock_sub_agent_manager)
    missing = _missing_param_descriptions(tool)
    assert not missing, f"SearchAgent params with no description: {missing}"


def test_agent_roster_doc_truncates_with_search_pointer(
    mock_sub_agent_manager, monkeypatch
):
    """A fleet over the cap lists only the first entries and points at
    SearchAgent for the rest."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-00" in doc
    assert "agent-02" in doc
    assert "agent-03" not in doc
    assert "5 more" in doc
    assert "SearchAgent" in doc


def test_agent_roster_doc_stays_complete_under_cap(mock_sub_agent_manager, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(2)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-01" in doc
    assert "more" not in doc


def test_agent_roster_doc_puts_core_agents_first(mock_sub_agent_manager, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "1")
    core = SubAgentDefinition(
        name="generalist",
        path="src/zrb/llm_plugin/core_agents/generalist.agent.md",
        description="Core generalist",
        system_prompt="prompt",
    )
    optional = SubAgentDefinition(
        name="alpha",
        path="src/zrb/llm_plugin/agents/alpha.agent.md",
        description="Optional agent",
        system_prompt="prompt",
    )
    mock_sub_agent_manager.scan.return_value = [optional, core]

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "`generalist`" in doc
    assert "`alpha`" not in doc


def test_agent_roster_doc_cap_zero_is_unlimited(mock_sub_agent_manager, monkeypatch):
    """0 disables the cap: the whole roster is listed, no truncation note."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "0")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-07" in doc
    assert "more" not in doc


def test_agent_not_found_message_truncates(mock_sub_agent_manager, monkeypatch):
    """The recovery error must not dump a huge roster either — a working
    subset plus a pointer to SearchAgent."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    result = agent_not_found_message("nope", mock_sub_agent_manager)

    assert "agent-00" in result
    assert "agent-03" not in result
    assert "5 more" in result
    assert "SearchAgent" in result


class TestSearchAgentTool:
    """SearchAgent: on-demand window onto the truncated agent roster."""

    @pytest.mark.asyncio
    async def test_matches_name(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="test")

        assert "test-agent" in result
        assert "A test agent" in result

    @pytest.mark.asyncio
    async def test_matches_description(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="agent")

        assert "test-agent" in result

    @pytest.mark.asyncio
    async def test_no_match_names_the_way_back(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="nothing")

        assert "No agents match 'nothing'" in result
        assert "[SYSTEM SUGGESTION]" in result

    @pytest.mark.asyncio
    async def test_empty_query_lists_every_delegatable_agent(
        self, mock_sub_agent_manager
    ):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="")

        assert "test-agent" in result

    @pytest.mark.asyncio
    async def test_truncates_runaway_results(self, mock_sub_agent_manager, monkeypatch):
        mock_sub_agent_manager.scan.return_value = [
            SubAgentDefinition(
                name=f"match-{i:02d}",
                path="path",
                description="shares the keyword",
                system_prompt="prompt",
            )
            for i in range(40)
        ]
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="keyword")

        assert "match-29" in result
        assert "match-30" not in result
        assert "more match" in result

    def test_is_a_delegate_tool(self, mock_sub_agent_manager):
        """SearchAgent belongs to the delegate family: sub-agents filter it out
        and the `minimal` profile drops it with the rest."""
        tool = create_search_agent_tool(mock_sub_agent_manager)

        assert tool.__name__ == "SearchAgent"
        assert getattr(tool, "zrb_is_delegate_tool", False) is True


@pytest.mark.asyncio
async def test_delegate_tool_agent_not_found(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = None
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    result = await tool(
        agent_name="non-existent",
        deliverable="a result",
        task="task",
        non_goals=[],
    )
    assert "Error" in result
    assert "not found" in result
    # The roster is in the error, so the retry is a correction, not a guess.
    assert "test-agent" in result


@pytest.mark.asyncio
async def test_delegate_tool_not_found_suggests_closest_name(
    mock_sub_agent_manager,
):
    mock_sub_agent_manager.create_agent.return_value = None
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    result = await tool(
        agent_name="test-agnt",
        deliverable="a result",
        task="task",
        non_goals=[],
    )
    assert "Did you mean 'test-agent'?" in result


def test_agent_not_found_message_without_registered_agents():
    manager = MagicMock(spec=SubAgentManager)
    manager.scan.return_value = []

    result = agent_not_found_message("anything", manager)

    assert "no sub-agents are registered" in result
    # No roster to offer, so it must not tell the model to retry with a name.
    assert "Call again" not in result
