"""Filesystem scanning and agent-file parsing for `SubAgentManager`.

Loads agents from `AGENT.py` / `*.agent.py` (Python) and `AGENT.md` /
`*.agent.md` / plain `*.md` (Markdown with optional YAML frontmatter).
Registers each parsed `SubAgentDefinition` on `self._agents`.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from zrb.util.load import load_module_from_path

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager import SubAgentDefinition


class LoaderMixin:
    """Filesystem walker + agent-file parsers for `SubAgentManager`."""

    def _scan_dir(self, directory: Path, max_depth: int) -> None:
        try:
            search_path = Path(directory).resolve()
            self._scan_dir_recursive(search_path, search_path, max_depth, 0)
        except Exception:
            pass

    def _scan_dir_recursive(
        self,
        base_dir: Path,
        current_dir: Path,
        max_depth: int,
        current_depth: int,
    ) -> None:
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

                    if item.name == "AGENT.py" or item.name.endswith(".agent.py"):
                        self._load_agent_from_python(rel_path, full_path)
                    else:
                        is_agent_file = item.name == "AGENT.md" or item.name.endswith(
                            ".agent.md"
                        )
                        # Claude also accepts plain `.md` files inside `agents/`.
                        if not is_agent_file and item.suffix.lower() == ".md":
                            if (
                                item.name.lower() != "readme.md"
                                and item.parent.name.lower() == "agents"
                            ):
                                is_agent_file = True
                        if is_agent_file:
                            self._load_agent_from_markdown(rel_path, full_path)
        except (PermissionError, OSError):
            pass

    def _load_agent_from_python(self, rel_path: str, full_path: str) -> None:
        from pydantic_ai import Agent

        from zrb.llm.agent.subagent.manager import SubAgentDefinition

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
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            default_name = os.path.basename(os.path.dirname(full_path))
            name = default_name
            description = "No description"
            system_prompt = ""
            model = None
            tools: list[str] = []
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
                            tools = frontmatter.get("tools", [])
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
            )
        except Exception:
            pass
