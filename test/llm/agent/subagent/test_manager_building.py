from unittest.mock import MagicMock, patch

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.common_tools import apply_common_tools


def test_sub_agent_manager_add_toolset_factory():
    manager = SubAgentManager()
    ts = MagicMock()
    factory = MagicMock(return_value=ts)
    manager.append_toolset_factory(factory)

    agent_def = SubAgentDefinition("test", ".", "d", "p")
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.building.create_agent") as mock_create:
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

    with patch("zrb.llm.agent.subagent.building.create_agent") as mock_create:
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

    with patch("zrb.llm.agent.subagent.building.create_agent") as mock_create:
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
            "zrb.llm.agent.subagent.building.render_journal_index",
            return_value=journal_block,
        ),
        patch("zrb.llm.agent.subagent.building.create_agent") as mock_create,
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

    with patch("zrb.llm.agent.subagent.building.create_agent") as mock_create:
        manager.create_agent("optout")
        prompt = mock_create.call_args.kwargs["system_prompt"]
    assert "# Persona" not in prompt
    assert "Body only." in prompt


def test_create_llm_chat_task_returns_none_for_unknown_agent():
    manager = SubAgentManager()
    assert manager.create_llm_chat_task("nope") is None


def test_create_llm_chat_task_returns_none_for_agent_instance_definition():
    """A pre-built pydantic-ai Agent has no system_prompt/tools/model triple
    to re-derive a task's config from."""
    manager = SubAgentManager()
    mock_agent = MagicMock()
    manager.add_agent(
        SubAgentDefinition(
            name="inst-agent",
            path=".",
            description="d",
            system_prompt="p",
            agent_instance=mock_agent,
        )
    )
    assert manager.create_llm_chat_task("inst-agent") is None


def test_create_llm_chat_task_returns_none_for_agent_factory_definition():
    manager = SubAgentManager()
    manager.add_agent(
        SubAgentDefinition(
            name="fact-agent",
            path=".",
            description="d",
            system_prompt="p",
            agent_factory=lambda: MagicMock(),
        )
    )
    assert manager.create_llm_chat_task("fact-agent") is None


def test_create_llm_chat_task_builds_task_from_resolved_persona():
    """The resolved system prompt / tools / model — the same resolution
    `create_agent` uses — must reach the constructed LLMChatTask, so resuming
    a delegated session talks to the actual sub-agent, not the main agent.

    Uses a name that doesn't collide with any real *.agent.md on disk —
    `get_agent_definition` triggers a real filesystem scan on first call
    (`_ensure_loaded`), which would otherwise clobber a manually `add_agent`'d
    stub sharing a name with a built-in agent (e.g. "researcher")."""
    manager = SubAgentManager()

    def stub_researcher_tool():
        """A stub-researcher-only tool."""
        return "ok"

    def delegate_tool():
        """A delegate tool, must never reach a sub-agent."""
        return "nested"

    delegate_tool.zrb_is_delegate_tool = True
    manager.append_tool(stub_researcher_tool, delegate_tool)
    manager.add_agent(
        SubAgentDefinition(
            name="stub-researcher",
            path=".",
            description="Research agent",
            system_prompt="You are a stub researcher.",
            tools=["stub_researcher_tool", "delegate_tool"],
            model="test-model",
        )
    )

    mock_task = MagicMock()
    with (
        patch("zrb.llm.task.chat.task.LLMChatTask", return_value=mock_task) as MockTask,
        patch(
            "zrb.llm.agent.subagent.building.resolve_configured_model",
            return_value="resolved-test-model",
        ),
    ):
        result = manager.create_llm_chat_task("stub-researcher")

    assert result is mock_task
    MockTask.assert_called_once()
    call_kwargs = MockTask.call_args.kwargs
    assert "You are a stub researcher." in call_kwargs["system_prompt"]
    assert stub_researcher_tool in call_kwargs["tools"]
    assert delegate_tool not in call_kwargs["tools"]
    assert call_kwargs["model"] == "resolved-test-model"
    assert call_kwargs["name"] == "resumed-stub-researcher"


def test_common_tools_are_name_gated_for_sub_agents():
    manager = SubAgentManager()
    apply_common_tools(manager)
    manager.add_agent(
        SubAgentDefinition(
            name="read-only",
            path=".",
            description="Read-only agent",
            system_prompt="Read files only.",
            tools=["Read"],
        )
    )

    with patch("zrb.llm.agent.subagent.building.create_agent") as mock_create_agent:
        manager.create_agent("read-only")
        resolved_tools = mock_create_agent.call_args.kwargs["tools"]

    names = {
        getattr(tool, "name", getattr(tool, "__name__", "")) for tool in resolved_tools
    }
    assert "Read" in names
    assert "Write" not in names
    assert "Shell" not in names
