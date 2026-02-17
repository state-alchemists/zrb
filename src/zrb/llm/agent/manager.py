from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.agent.common import create_agent
from zrb.llm.history_processor.summarizer import (
    create_summarizer_history_processor,
)
from zrb.llm.tool.bash import run_shell_command
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import (
    analyze_file,
    glob_files,
    list_files,
    read_file,
    read_files,
    replace_in_file,
    search_files,
    write_file,
    write_files,
)
from zrb.llm.tool.mcp import load_mcp_config
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.web import open_web_page, search_internet
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool
from zrb.util.load import load_module_from_path

if TYPE_CHECKING:
    from pydantic_ai import Agent, Tool
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

_IGNORE_DIRS = [
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    "dist",
    "build",
    "htmlcov",
]


class SubAgentDefinition:
    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        system_prompt: str,
        model: str | None = None,
        tools: list[str] = [],
        agent_instance: Any | None = None,
        agent_factory: Callable[[], Any] | None = None,
    ):
        self.name = name
        self.path = path
        self.description = description
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools
        self.agent_instance = agent_instance
        self.agent_factory = agent_factory


class SubAgentManager:
    def __init__(
        self,
        auto_load: bool = True,
        tool_registry: dict[str, Callable] | None = None,
        root_dir: str = ".",
        search_dirs: list[str | Path] | None = None,
        max_depth: int = 1,
        ignore_dirs: list[str] | None = None,
    ):
        self._tool_registry = tool_registry if tool_registry is not None else {}
        self._tool_factories: list[Callable[[AnyContext], Tool | ToolFuncEither]] = []
        self._toolsets: list[AbstractToolset[None]] = []
        self._toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]] = (
            []
        )
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._agents: dict[str, SubAgentDefinition] = {}
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        if auto_load:
            self.scan(self._search_dirs)

    def _get_tool_registry(self) -> dict[str, Callable]:
        return self._tool_registry

    def _get_all_toolsets(self, ctx: AnyContext) -> list[AbstractToolset[None]]:
        """Get all toolsets including those resolved from factories."""
        all_toolsets = list(self._toolsets)
        for factory in self._toolset_factories:
            toolset = factory(ctx)
            if isinstance(toolset, list):
                all_toolsets.extend(toolset)
            else:
                all_toolsets.append(toolset)
        return all_toolsets

    def add_tool(self, *tool: Callable):
        """
        Register tools.
        """
        self.append_tool(*tool)

    def append_tool(self, *tool: Callable):
        """
        Append tools.
        """
        for single_tool in tool:
            tool_name = getattr(single_tool, "__name__", str(single_tool))
            self._tool_registry[tool_name] = single_tool

    def add_tool_factory(self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]):
        """
        Register tool factories.
        """
        self.append_tool_factory(*factory)

    def append_tool_factory(
        self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]
    ):
        """
        Append tool factories.
        """
        for single_factory in factory:
            self._tool_factories.append(single_factory)

    def add_toolset(self, *toolset: AbstractToolset[None]):
        """
        Register toolsets.
        """
        self.append_toolset(*toolset)

    def append_toolset(self, *toolset: AbstractToolset[None]):
        """
        Append toolsets.
        """
        self._toolsets += list(toolset)

    def add_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """
        Register toolset factories.
        """
        self.append_toolset_factory(*factory)

    def append_toolset_factory(
        self, *factory: Callable[[AnyContext], AbstractToolset[None]]
    ):
        """
        Append toolset factories.
        """
        self._toolset_factories += list(factory)

    def scan(
        self, search_dirs: list[str | Path] | None = None
    ) -> list[SubAgentDefinition]:
        self._agents = {}
        target_search_dirs = search_dirs
        if target_search_dirs is None:
            target_search_dirs = (
                self._search_dirs
                if self._search_dirs is not None
                else self.get_search_directories()
            )
        # Scan in order of precedence: global -> project
        for search_dir in target_search_dirs:
            self._scan_dir(search_dir, max_depth=self._max_depth)
        return list(self._agents.values())

    def get_search_directories(self) -> list[str | Path]:
        search_dirs: list[str | Path] = []
        zrb_agent_dir_name = f".{CFG.ROOT_GROUP_NAME}/agents"

        # 0. Plugins (Default Plugin -> User Plugins)
        # Default Plugin
        default_plugin_path = (
            Path(os.path.dirname(__file__)).parent.parent / "llm_plugin"
        )
        if default_plugin_path.exists() and default_plugin_path.is_dir():
            agent_path = default_plugin_path / "agents"
            if agent_path.exists() and agent_path.is_dir():
                search_dirs.append(agent_path)

        # User Plugins
        for plugin_path_str in CFG.LLM_PLUGIN_DIRS:
            plugin_path = Path(plugin_path_str)
            if plugin_path.exists() and plugin_path.is_dir():
                agent_path = plugin_path / "agents"
                if agent_path.exists() and agent_path.is_dir():
                    search_dirs.append(agent_path)

        # 1. User global config (~/.claude/agents and ~/.zrb/agents)
        try:
            home = Path.home()
            # Claude style
            global_claude_agents = home / ".claude" / "agents"
            if global_claude_agents.exists() and global_claude_agents.is_dir():
                search_dirs.append(global_claude_agents)
            # Zrb style
            global_zrb_agents = home / zrb_agent_dir_name
            if global_zrb_agents.exists() and global_zrb_agents.is_dir():
                search_dirs.append(global_zrb_agents)
        except Exception:
            pass

        # 2. Project directories (.claude/agents and .zrb/agents)
        try:
            cwd = Path(self._root_dir).resolve()
            project_dirs = list(cwd.parents)[::-1] + [cwd]
            for project_dir in project_dirs:
                # Claude style
                local_claude_agents = project_dir / ".claude" / "agents"
                if local_claude_agents.exists() and local_claude_agents.is_dir():
                    search_dirs.append(local_claude_agents)
                # Zrb style
                local_zrb_agents = project_dir / zrb_agent_dir_name
                if local_zrb_agents.exists() and local_zrb_agents.is_dir():
                    search_dirs.append(local_zrb_agents)
        except Exception:
            pass

        # 3. The root_dir itself (recursive)
        search_dirs.append(Path(self._root_dir))

        return search_dirs

    def _scan_dir(self, directory: Path, max_depth: int):
        try:
            search_path = Path(directory).resolve()
            self._scan_dir_recursive(search_path, search_path, max_depth, 0)
        except Exception:
            pass

    def _scan_dir_recursive(
        self, base_dir: Path, current_dir: Path, max_depth: int, current_depth: int
    ):
        if current_depth > max_depth:
            return

        try:
            for item in current_dir.iterdir():
                if item.is_dir():
                    if item.name in self._ignore_dirs or item.name.startswith("."):
                        continue
                    self._scan_dir_recursive(
                        base_dir, item, max_depth, current_depth + 1
                    )
                elif item.is_file():
                    full_path = str(item)
                    rel_path = os.path.relpath(full_path, self._root_dir)

                    # Check for Python agent files
                    if item.name == "AGENT.py" or item.name.endswith(".agent.py"):
                        self._load_agent_from_python(rel_path, full_path)

                    # Check for Markdown agent files
                    else:
                        is_agent_file = item.name == "AGENT.md" or item.name.endswith(
                            ".agent.md"
                        )
                        # Claude also supports simple .md files in the agents/ directory
                        if not is_agent_file and item.suffix.lower() == ".md":
                            if item.name.lower() != "readme.md":
                                is_agent_file = True

                        if is_agent_file:
                            self._load_agent_from_markdown(rel_path, full_path)
        except (PermissionError, OSError):
            pass

    def _load_agent_from_python(self, rel_path: str, full_path: str):
        from pydantic_ai import Agent

        try:
            module_name = f"zrb_agent_{uuid.uuid4().hex}"
            module = load_module_from_path(module_name, full_path)
            if not module:
                return
            agent_def = None
            # Look for 'agent' or 'AGENT' variable
            if hasattr(module, "agent"):
                agent_def = getattr(module, "agent")
            elif hasattr(module, "AGENT"):
                agent_def = getattr(module, "AGENT")
            if isinstance(agent_def, SubAgentDefinition):
                self._agents[agent_def.name] = agent_def
            elif isinstance(agent_def, Agent):
                # Wrapped as definition
                name = os.path.basename(os.path.dirname(full_path))
                # Try to get name from module if possible? No, stick to folder/convention or let user define SubAgentDefinition
                self._agents[name] = SubAgentDefinition(
                    name=name,
                    path=full_path,
                    description="Python Agent",
                    system_prompt="",
                    agent_instance=agent_def,
                )
            elif hasattr(module, "get_agent") and callable(module.get_agent):
                # Factory
                name = os.path.basename(os.path.dirname(full_path))
                self._agents[name] = SubAgentDefinition(
                    name=name,
                    path=full_path,
                    description="Python Agent Factory",
                    system_prompt="",
                    agent_factory=module.get_agent,
                )
        except Exception:
            pass

    def _load_agent_from_markdown(self, rel_path: str, full_path: str):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            default_name = os.path.basename(os.path.dirname(full_path))
            name = default_name
            description = "No description"
            system_prompt = ""
            model = None
            tools = []
            is_name_resolved = False

            # 1. Parse YAML Frontmatter
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        system_prompt = parts[2].strip()
                        if frontmatter:
                            if "name" in frontmatter:
                                name = frontmatter["name"]
                                is_name_resolved = True
                            description = frontmatter.get("description", description)
                            model = frontmatter.get("model", None)
                            tools = frontmatter.get("tools", [])
                except Exception:
                    pass

            # 2. Fallback: Parse Markdown for Header 1 if not fully resolved or no frontmatter
            if not is_name_resolved:
                # If no frontmatter or parse failed, treat whole content as prompt
                # But try to find name in H1
                lines = content.splitlines()
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        name = stripped[2:].strip()
                        is_name_resolved = True
                        break
                if not system_prompt:
                    system_prompt = content

            self._agents[name] = SubAgentDefinition(
                name=name,
                path=full_path,
                description=description,
                system_prompt=system_prompt,
                model=model,
                tools=tools,
            )

        except Exception:
            pass

    def _load_agent(self, rel_path: str, full_path: str):
        # Backward compatibility
        self._load_agent_from_markdown(rel_path, full_path)

    def add_agent(self, definition: SubAgentDefinition):
        """
        Manually register a sub-agent definition.
        """
        self._agents[definition.name] = definition

    def set_tool_registry(self, tool_registry: dict[str, Callable]):
        """
        Update the tool registry used by sub-agents.
        """
        self._tool_registry = tool_registry

    def get_agent_definition(self, name: str) -> SubAgentDefinition | None:
        agent = self._agents.get(name)
        if not agent:
            # Try partial match or path match
            for a in self._agents.values():
                if a.name == name or a.path == name:
                    agent = a
                    break
        return agent

    def create_agent(
        self, name: str, ctx: AnyContext | None = None
    ) -> "Agent[None, Any] | None":
        definition = self.get_agent_definition(name)
        if not definition:
            return None
        if definition.agent_instance:
            return definition.agent_instance
        if definition.agent_factory:
            try:
                return definition.agent_factory()
            except Exception:
                pass
        # Resolve Tools
        if ctx is None:
            from zrb.context.context import Context
            from zrb.context.shared_context import SharedContext

            ctx = Context(
                shared_ctx=SharedContext(),
                task_name="sub-agent-task",
                color=0,
                icon="🤖",
            )

        resolved_tools = []
        registry = self._get_tool_registry()
        # Add tools from registry
        for tool_name in definition.tools:
            if tool_name in registry:
                tool = registry[tool_name]
                if not getattr(tool, "zrb_is_delegate_tool", False):
                    resolved_tools.append(tool)

        # Add tools from factories
        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                for single_tool in tool:
                    if not getattr(single_tool, "zrb_is_delegate_tool", False):
                        resolved_tools.append(single_tool)
            elif not getattr(tool, "zrb_is_delegate_tool", False):
                resolved_tools.append(tool)

        # Get all toolsets including those from factories
        resolved_toolsets = self._get_all_toolsets(ctx)

        return create_agent(
            model=definition.model,
            system_prompt=definition.system_prompt,
            tools=resolved_tools,
            toolsets=resolved_toolsets,
            history_processors=[
                create_summarizer_history_processor(
                    token_threshold=CFG.LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD,
                    summary_window=CFG.LLM_HISTORY_SUMMARIZATION_WINDOW,
                )
            ],
        )


sub_agent_manager = SubAgentManager(auto_load=True)

# Add tools
sub_agent_manager.add_tool(
    run_shell_command,
    analyze_code,
    list_files,
    glob_files,
    read_file,
    read_files,
    write_file,
    write_files,
    replace_in_file,
    search_files,
    analyze_file,
    search_internet,
    open_web_page,
)

# Add tool factories
sub_agent_manager.add_tool_factory(
    lambda ctx: create_list_zrb_task_tool(),
    lambda ctx: create_run_zrb_task_tool(),
    lambda ctx: create_activate_skill_tool(),
)

# Add toolset factories
sub_agent_manager.add_toolset_factory(
    lambda ctx: load_mcp_config(),
)
