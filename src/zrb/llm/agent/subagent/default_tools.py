"""Default tool registration for the module-level `sub_agent_manager`.

Kept separate from `agent/manager.py` so the registered tool surface is
visible at one glance and the manager class itself stays focused on
loading/creating sub-agents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.lsp.tools import create_lsp_tools
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

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager import SubAgentManager


def register_default_tools(manager: "SubAgentManager") -> None:
    """Register the standard zrb-shipped tools onto the given manager."""
    manager.add_tool(
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
    manager.add_tool_factory(
        lambda ctx: create_list_zrb_task_tool(),
        lambda ctx: create_run_zrb_task_tool(),
        lambda ctx: create_activate_skill_tool(),
    )
    manager.add_toolset_factory(
        lambda ctx: load_mcp_config(),
    )
    manager.add_tool(*create_lsp_tools())
    manager.add_tool(*_get_todo_tools())


def _get_todo_tools():
    """Lazy import to avoid circular dependency with `tool.plan`."""
    from zrb.llm.tool.plan import clear_todos, get_todos, update_todo, write_todos

    return [write_todos, get_todos, update_todo, clear_todos]
