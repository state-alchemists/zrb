"""Filesystem scanning and agent-file parsing for ``SubAgentManager``.

Loads agents from ``AGENT.py`` / ``*.agent.py`` (Python) and ``AGENT.md`` /
``*.agent.md`` / plain ``*.md`` (Markdown with optional YAML frontmatter).
Registers each parsed ``SubAgentDefinition`` on ``self._agents``.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from zrb.util.asset_scanner import scan_files
from zrb.util.load import load_module_from_path

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager.manager import SubAgentDefinition


class LoaderMixin:
    """Filesystem walker + agent-file parsers for ``SubAgentManager``."""

    # Host-class contract: these attributes are owned by the class that mixes
    # this in (see ``SubAgentManager.__init__``). Declared here so static type
    # checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _ignore_dirs: list[str]
        _root_dir: str
        _agents: dict[str, SubAgentDefinition]

    def _scan_dir(self, directory: Path, max_depth: int) -> None:
        try:
            scan_files(
                Path(directory),
                max_depth,
                self._on_file_found,
                self._ignore_dirs,
            )
        except Exception:
            pass

    def _on_file_found(self, item: Path) -> None:
        full_path = str(item)
        rel_path = os.path.relpath(full_path, self._root_dir)

        if item.name == "AGENT.py" or item.name.endswith(".agent.py"):
            self._load_agent_from_python(rel_path, full_path)
        else:
            is_agent_file = item.name == "AGENT.md" or item.name.endswith(".agent.md")
            # Claude also accepts plain ``.md`` files inside ``agents/``.
            if not is_agent_file and item.suffix.lower() == ".md":
                if (
                    item.name.lower() != "readme.md"
                    and item.parent.name.lower() == "agents"
                ):
                    is_agent_file = True
            if is_agent_file:
                self._load_agent_from_markdown(rel_path, full_path)

    def _load_agent_from_python(self, rel_path: str, full_path: str) -> None:
        # lazy: heavy third-party
        from pydantic_ai import Agent

        # lazy: SubAgentDefinition lives in the sibling module that imports
        # this mixin; hoisting would create a circular import.
        from zrb.llm.agent.subagent.manager.manager import SubAgentDefinition

        try:
            module_name = f"zrb_agent_{uuid.uuid4().hex}"
            module = load_module_from_path(module_name, full_path)
            if not module:
                return

            agent_def = None
            if hasattr(module, "agent"):
                agent_def = getattr(module, "agent")
            elif hasattr(module, "AGENT"):
                agent_def = getattr(module, "AGENT")

            if isinstance(agent_def, SubAgentDefinition):
                self._agents[agent_def.name] = agent_def
                return
            if isinstance(agent_def, Agent):
                # Wrap a bare pydantic-ai Agent — folder name is the identifier.
                name = os.path.basename(os.path.dirname(full_path))
                self._agents[name] = SubAgentDefinition(
                    name=name,
                    path=full_path,
                    description="Python Agent",
                    system_prompt="",
                    agent_instance=agent_def,
                )
                return
            if hasattr(module, "get_agent") and callable(module.get_agent):
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

    def _load_agent_from_markdown(self, rel_path: str, full_path: str) -> None:
        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.agent.subagent.manager.manager import SubAgentDefinition

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            default_name = os.path.basename(os.path.dirname(full_path))
            name = default_name
            description = "No description"
            system_prompt = ""
            model = None
            tools: list[str] = []
            disallowed_tools: list[str] = []
            inherit_sections: list[str] | None = None
            is_name_resolved = False

            # 1. YAML frontmatter (preferred)
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
                            # Accept list form (canonical) or comma string (Claude-compat).
                            raw_tools = frontmatter.get("tools", [])
                            if isinstance(raw_tools, list):
                                tools = [
                                    str(t).strip() for t in raw_tools if str(t).strip()
                                ]
                            elif isinstance(raw_tools, str):
                                tools = [
                                    t.strip() for t in raw_tools.split(",") if t.strip()
                                ]
                            raw_disallowed = frontmatter.get("disallowedTools", [])
                            if isinstance(raw_disallowed, list):
                                disallowed_tools = [
                                    str(t).strip()
                                    for t in raw_disallowed
                                    if str(t).strip()
                                ]
                            elif isinstance(raw_disallowed, str):
                                disallowed_tools = [
                                    t.strip()
                                    for t in raw_disallowed.split(",")
                                    if t.strip()
                                ]
                            # Accept list form (canonical) or comma string (Claude-compat).
                            raw_inherit = frontmatter.get("inherit_sections")
                            if isinstance(raw_inherit, list):
                                inherit_sections = [
                                    str(s).strip()
                                    for s in raw_inherit
                                    if str(s).strip()
                                ]
                            elif isinstance(raw_inherit, str):
                                inherit_sections = [
                                    s.strip()
                                    for s in raw_inherit.split(",")
                                    if s.strip()
                                ]
                except Exception:
                    pass

            # 2. Fallback: H1 in markdown body, full file as system prompt.
            if not is_name_resolved:
                for line in content.splitlines():
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
                disallowed_tools=disallowed_tools,
                inherit_sections=inherit_sections,
            )
        except Exception:
            pass
