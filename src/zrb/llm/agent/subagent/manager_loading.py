"""Filesystem scanning and agent-file parsing for ``SubAgentManager``.

Loads agents from ``AGENT.py`` / ``*.agent.py`` (Python) and ``AGENT.md`` /
``*.agent.md`` / plain ``*.md`` (Markdown with optional YAML frontmatter).
Registers each parsed ``SubAgentDefinition`` on ``self._agents``.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from zrb.config.config import CFG
from zrb.util.asset_scanner import scan_files
from zrb.util.frontmatter import parse_frontmatter
from zrb.util.load import load_module_from_path

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager import SubAgentDefinition


_Default = TypeVar("_Default")


def _as_str_list(raw: Any, default: _Default) -> "list[str] | _Default":
    """Coerce a frontmatter field to a clean list of strings.

    Accepts the canonical list form or a comma-separated string
    (Claude-compatible), dropping blank entries either way. Anything else —
    including a missing key — yields `default`, which lets a caller distinguish
    "absent" (None) from "present but empty" ([]).
    """
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    return default


class SubAgentManagerLoading:
    """Filesystem walker + agent-file parsers for ``SubAgentManager``.

    `ignore_dirs` and `agents` are owned by `SubAgentManager.__init__` and
    handed in once here; `agents` is the *same* dict object the owner holds
    (never reassigned wholesale — `SubAgentManager.reload` clears it in place)
    so mutations made here stay visible to the owner. `root_dir` is passed per
    call instead of cached, since it can change after construction.
    """

    def __init__(self, ignore_dirs: list[str], agents: "dict[str, SubAgentDefinition]"):
        self._ignore_dirs = ignore_dirs
        self._agents = agents

    def _scan_dir(self, directory: Path, max_depth: int, root_dir: str) -> None:
        try:
            scan_files(
                Path(directory),
                max_depth,
                lambda item: self._on_file_found(item, root_dir),
                self._ignore_dirs,
            )
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to scan agent directory {directory}: {e}")

    def _on_file_found(self, item: Path, root_dir: str) -> None:
        full_path = str(item)
        rel_path = os.path.relpath(full_path, root_dir)

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
        # this part; hoisting would create a circular import.
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
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to load Python agent {full_path}: {e}")

    def _load_agent_from_markdown(self, rel_path: str, full_path: str) -> None:
        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.agent.subagent.manager import SubAgentDefinition

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            name = os.path.basename(os.path.dirname(full_path))
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
                    frontmatter, system_prompt = parse_frontmatter(content)
                    if "name" in frontmatter:
                        name = frontmatter["name"]
                        is_name_resolved = True
                    description = frontmatter.get("description", description)
                    model = frontmatter.get("model", None)
                    tools = _as_str_list(frontmatter.get("tools"), tools)
                    disallowed_tools = _as_str_list(
                        frontmatter.get("disallowedTools"), disallowed_tools
                    )
                    inherit_sections = _as_str_list(
                        frontmatter.get("inherit_sections"), inherit_sections
                    )
                except Exception as e:
                    CFG.LOGGER.debug(f"Failed to parse agent frontmatter: {e}")

            # 2. Fallback: H1 in markdown body, full file as system prompt.
            if not is_name_resolved:
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        name = stripped[2:].strip()
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
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to load Markdown agent {full_path}: {e}")
