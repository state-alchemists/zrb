from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic_ai import Agent

if TYPE_CHECKING:
    from pydantic_ai import Tool
    from pydantic_ai.tools import ToolFuncEither

    from zrb.context.any_context import AnyContext

from zrb.config.config import CFG
from zrb.llm.agent.common import create_agent
from zrb.util.load import load_module_from_path

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
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._agents: dict[str, SubAgentDefinition] = {}
        self._ignore_dirs = _IGNORE_DIRS if ignore_dirs is None else ignore_dirs
        if auto_load:
            self.scan(self._search_dirs)

    def _get_tool_registry(self) -> dict[str, Callable]:
        return self._tool_registry

    def add_tool(self, *tool: Callable):
        """
        Register tools.
        """
        for single_tool in tool:
            tool_name = getattr(single_tool, "__name__", str(single_tool))
            self._tool_registry[tool_name] = single_tool

    def add_tool_factory(self, *factory: Callable[[AnyContext], Tool | ToolFuncEither]):
        """
        Register tool factories.
        """
        for single_factory in factory:
            self._tool_factories.append(single_factory)

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
    ) -> Agent[None, Any] | None:
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

            ctx = Context()

        resolved_tools = []
        registry = self._get_tool_registry()
        # Add tools from registry
        for tool_name in definition.tools:
            if tool_name in registry:
                resolved_tools.append(registry[tool_name])

        # Add tools from factories
        for factory in self._tool_factories:
            tool = factory(ctx)
            if isinstance(tool, list):
                resolved_tools.extend(tool)
            else:
                resolved_tools.append(tool)

        return create_agent(
            model=definition.model,
            system_prompt=definition.system_prompt,
            tools=resolved_tools,
        )


sub_agent_manager = SubAgentManager(auto_load=True)
