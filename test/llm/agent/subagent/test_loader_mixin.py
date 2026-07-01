import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager


@pytest.fixture
def manager():
    return SubAgentManager()


def test_sub_agent_manager_scan_public(manager, tmp_path):
    """Test public scan() method and its effect on agent registry."""
    # Setup tmp directory structure
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # We use a real file to test the scanner
    md_agent = agents_dir / "test.agent.md"
    md_agent.write_text("""---
name: MD_Agent
description: desc
---
prompt""")

    # scan is public
    manager.scan([str(tmp_path)])

    # get_agent_definition is public
    agent = manager.get_agent_definition("MD_Agent")
    assert agent is not None
    assert agent.name == "MD_Agent"


def test_load_agent_from_markdown_frontmatter_public(manager, tmp_path):
    """Verify that scanning a markdown file with frontmatter populates the registry correctly."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text("""---
name: CustomName
description: Custom description
model: gpt-4
tools: [tool1, tool2]
---
System prompt here""")

    manager.scan([str(tmp_path)])

    agent = manager.get_agent_definition("CustomName")
    assert agent is not None
    assert agent.description == "Custom description"
    assert agent.model == "gpt-4"
    assert agent.tools == ["tool1", "tool2"]
    assert agent.system_prompt == "System prompt here"


def test_create_agent_from_instance_public(manager):
    """Test public create_agent using an added instance."""
    mock_agent = MagicMock()
    agent_def = SubAgentDefinition(
        name="inst-agent",
        path=".",
        description="desc",
        system_prompt="prompt",
        agent_instance=mock_agent,
    )
    # add_agent is public
    manager.add_agent(agent_def)
    # create_agent is public
    assert manager.create_agent("inst-agent") == mock_agent


def test_create_agent_from_factory_public(manager):
    """Test public create_agent using an added factory."""
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


def test_sub_agent_manager_add_tool_list_public(manager):
    """Test public add_tool and its effect on agent creation."""

    def t1():
        """t1"""
        pass

    manager.add_tool(t1)

    agent_def = SubAgentDefinition(
        name="tool-test", path=".", description="d", system_prompt="p", tools=["t1"]
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("tool-test")
        resolved_tools = mock_create.call_args.kwargs["tools"]
        assert t1 in resolved_tools


def test_sub_agent_manager_disallowed_tools_filters_registry(manager):
    """disallowedTools removes tools from the resolved set."""

    def t1():
        """t1"""
        pass

    def t2():
        """t2"""
        pass

    manager.add_tool(t1, t2)

    agent_def = SubAgentDefinition(
        name="dis-test",
        path=".",
        description="d",
        system_prompt="p",
        tools=["t1", "t2"],
        disallowed_tools=["t2"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("dis-test")
        resolved_tools = mock_create.call_args.kwargs["tools"]
        assert t1 in resolved_tools
        assert t2 not in resolved_tools


def test_sub_agent_manager_disallowed_tools_filters_factory(manager):
    """disallowedTools removes factory-created tools from the resolved set."""

    def t2():
        """t2"""
        pass

    def factory(ctx):
        return t2

    manager.add_tool_factory(factory)

    agent_def = SubAgentDefinition(
        name="dis-factory",
        path=".",
        description="d",
        system_prompt="p",
        disallowed_tools=["t2"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.manager.create_agent") as mock_create:
        manager.create_agent("dis-factory")
        resolved_tools = mock_create.call_args.kwargs["tools"]
        assert t2 not in resolved_tools


def test_loader_parses_inherit_sections_list(manager, tmp_path):
    """inherit_sections in frontmatter as a YAML list is parsed into a list."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: inh-list
description: d
inherit_sections: [persona, mandate, system_context]
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("inh-list")
    assert agent is not None
    assert agent.inherit_sections == ["persona", "mandate", "system_context"]


def test_loader_parses_inherit_sections_comma_string(manager, tmp_path):
    """inherit_sections in frontmatter as a comma-separated string is normalised
    into a list (Claude-Code-compatible spelling)."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: inh-str
description: d
inherit_sections: "persona, mandate , project_context"
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("inh-str")
    assert agent is not None
    assert agent.inherit_sections == ["persona", "mandate", "project_context"]


def test_loader_omitted_inherit_sections_is_none(manager, tmp_path):
    """When inherit_sections is omitted from frontmatter the agent stays in
    legacy mode (inherit_sections=None, no parent sections injected)."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: legacy
description: d
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("legacy")
    assert agent is not None
    assert agent.inherit_sections is None


def test_loader_parses_tools_comma_string(manager, tmp_path):
    """tools as a comma-separated string (Claude-Code-compat) is split into a list."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: tool-str
description: d
tools: Read, Glob, Grep, Edit, Write, Bash
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("tool-str")
    assert agent is not None
    assert agent.tools == ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]


def test_loader_parses_tools_yaml_list(manager, tmp_path):
    """tools as a YAML flow list is parsed correctly (existing behaviour)."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: tool-list
description: d
tools: [Read, Glob, Grep]
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("tool-list")
    assert agent is not None
    assert agent.tools == ["Read", "Glob", "Grep"]


def test_loader_parses_disallowed_tools_list(manager, tmp_path):
    """disallowedTools as a YAML list is parsed correctly."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: dis-list
description: d
disallowedTools: [Edit, Write]
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("dis-list")
    assert agent is not None
    assert agent.disallowed_tools == ["Edit", "Write"]


def test_loader_parses_disallowed_tools_comma_string(manager, tmp_path):
    """disallowedTools as a comma-separated string is split into a list."""
    md_file = tmp_path / "test.agent.md"
    md_file.write_text(
        """---
name: dis-str
description: d
disallowedTools: Edit, Write
---
Body""",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("dis-str")
    assert agent is not None
    assert agent.disallowed_tools == ["Edit", "Write"]
