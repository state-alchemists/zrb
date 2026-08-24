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

    manager.append_tool(t1)

    agent_def = SubAgentDefinition(
        name="tool-test", path=".", description="d", system_prompt="p", tools=["t1"]
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
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

    manager.append_tool(t1, t2)

    agent_def = SubAgentDefinition(
        name="dis-test",
        path=".",
        description="d",
        system_prompt="p",
        tools=["t1", "t2"],
        disallowed_tools=["t2"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
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

    manager.append_tool_factory(factory)

    agent_def = SubAgentDefinition(
        name="dis-factory",
        path=".",
        description="d",
        system_prompt="p",
        disallowed_tools=["t2"],
    )
    manager.add_agent(agent_def)

    with patch("zrb.llm.agent.subagent.manager.create_agent") as mock_create:
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
    md_file = tmp_path / "dis-str.agent.md"
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


def test_loader_registers_python_agent_definition(manager, tmp_path):
    """AGENT.py exporting a SubAgentDefinition registers it under its own name."""
    agent_dir = tmp_path / "py-def-agent"
    agent_dir.mkdir()
    (agent_dir / "AGENT.py").write_text(
        "from zrb.llm.agent.subagent.manager import SubAgentDefinition\n"
        "agent = SubAgentDefinition(\n"
        '    name="py-def", path=__file__, description="from python",\n'
        '    system_prompt="be brief",\n'
        ")\n",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("py-def")
    assert agent is not None
    assert agent.description == "from python"
    assert agent.system_prompt == "be brief"


def test_loader_wraps_bare_pydantic_agent_under_folder_name(manager, tmp_path):
    """A .agent.py exporting a bare pydantic-ai Agent is wrapped; the folder
    name becomes the identifier."""
    agent_dir = tmp_path / "bare-agent"
    agent_dir.mkdir()
    (agent_dir / "AGENT.py").write_text(
        "from pydantic_ai import Agent\n"
        "agent = Agent('openai:gpt-4o', instructions='hi')\n",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("bare-agent")
    assert agent is not None
    assert agent.agent_instance is not None
    assert agent.system_prompt == ""


def test_loader_registers_get_agent_factory(manager, tmp_path):
    """A .agent.py exposing a callable get_agent() registers a factory definition
    keyed by the folder name."""
    agent_dir = tmp_path / "factory-agent"
    agent_dir.mkdir()
    (agent_dir / "tool.agent.py").write_text(
        "def get_agent():\n    return 'built-agent'\n",
    )
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("factory-agent")
    assert agent is not None
    assert agent.agent_factory is not None
    assert agent.agent_factory() == "built-agent"


def test_loader_skips_python_file_without_recognised_export(manager, tmp_path):
    """An AGENT.py with neither an agent/AGENT/get_agent export leaves the
    registry untouched instead of raising."""
    agent_dir = tmp_path / "empty-agent"
    agent_dir.mkdir()
    (agent_dir / "AGENT.py").write_text("x = 1\n")
    manager.scan([str(tmp_path)])
    assert manager.get_agent_definition("empty-agent") is None


def test_loader_survives_broken_python_agent_file(manager, tmp_path):
    """A syntax-broken AGENT.py is skipped (debug-logged) without failing the scan."""
    agent_dir = tmp_path / "broken-agent"
    agent_dir.mkdir()
    (agent_dir / "AGENT.py").write_text("def broken(:\n")
    manager.scan([str(tmp_path)])  # must not raise
    assert manager.get_agent_definition("broken-agent") is None


def test_loader_h1_fallback_names_agent_and_uses_full_body(manager, tmp_path):
    """Without frontmatter, the first H1 heading names the agent and the whole
    file content becomes the system prompt."""
    md_file = tmp_path / "h1.agent.md"
    md_file.write_text("# My H1 Agent\n\nYou are helpful.\n")
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("My H1 Agent")
    assert agent is not None
    assert agent.system_prompt.startswith("# My H1 Agent")
    assert agent.description == "No description"


def test_loader_malformed_frontmatter_falls_back_to_h1(manager, tmp_path):
    """Unparseable frontmatter degrades to the H1/body fallback instead of
    dropping the file."""
    md_file = tmp_path / "bad-fm.agent.md"
    md_file.write_text("---\n: : not: valid: yaml: [\n---\n# Fallback Name\nBody")
    manager.scan([str(tmp_path)])
    agent = manager.get_agent_definition("Fallback Name")
    assert agent is not None


def test_loader_plain_md_only_inside_agents_dir(manager, tmp_path):
    """A plain README.md in agents/ is ignored, but a sibling .md file is loaded;
    the same files outside agents/ are ignored."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "README.md").write_text("# Just Docs")
    (agents_dir / "helper.md").write_text("# Helper Agent\nDo things.")
    (tmp_path / "outside.md").write_text("# Outside Agent")
    manager.scan([str(tmp_path)])
    assert manager.get_agent_definition("Helper Agent") is not None
    assert manager.get_agent_definition("Just Docs") is None
    assert manager.get_agent_definition("Outside Agent") is None


def test_loader_scan_of_missing_directory_does_not_raise(manager):
    """Scanning a non-existent directory logs and moves on."""
    manager.scan(["/non/existent/agent/dir"])
