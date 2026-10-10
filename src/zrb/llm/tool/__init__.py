"""zrb-shipped LLM tools — one module per tool family.

Re-exports resolve lazily through PEP 562 `__getattr__`, so importing one
submodule does not load the whole family (~94ms).

`code.py` and `delegate.py` are not re-exported: they need the agent run loop
throughout, so import them from their own module.

File tools resolve through `file.py`, which sets each one's `__name__` to its
schema name (`Read`, `Write`, ...).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.tool.file import (
        analyze_file,
        glob_files,
        list_files,
        move_file,
        read_file,
        remove_file,
        replace_in_file,
        search_files,
        write_file,
    )
    from zrb.llm.tool.journal import search_journal
    from zrb.llm.tool.journal_write import log_activity, write_journal_note
    from zrb.llm.tool.mcp import load_mcp_config
    from zrb.llm.tool.plan import create_plan_tools, get_todos, write_todos
    from zrb.llm.tool.rag import create_rag_from_directory
    from zrb.llm.tool.shell import run_shell_command
    from zrb.llm.tool.shell_background import create_monitor_process_tool
    from zrb.llm.tool.skill import create_activate_skill_tool, create_search_skill_tool
    from zrb.llm.tool.web import open_web_page, search_internet
    from zrb.llm.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )
    from zrb.llm.tool_registry import ToolRegistry, tool_name, tool_registry

__all__ = [
    "run_shell_command",
    "ToolRegistry",
    "tool_name",
    "tool_registry",
    "glob_files",
    "list_files",
    "read_file",
    "write_file",
    "replace_in_file",
    "search_files",
    "analyze_file",
    "remove_file",
    "move_file",
    "search_journal",
    "log_activity",
    "write_journal_note",
    "load_mcp_config",
    "create_rag_from_directory",
    "create_activate_skill_tool",
    "create_search_skill_tool",
    "open_web_page",
    "search_internet",
    "create_list_zrb_task_tool",
    "create_run_zrb_task_tool",
    "create_monitor_process_tool",
    "create_plan_tools",
    "write_todos",
    "get_todos",
]

_SOURCES = {
    "ToolRegistry": "zrb.llm.tool_registry",
    "analyze_file": "zrb.llm.tool.file",
    "create_activate_skill_tool": "zrb.llm.tool.skill",
    "create_list_zrb_task_tool": "zrb.llm.tool.zrb_task",
    "create_monitor_process_tool": "zrb.llm.tool.shell_background",
    "create_plan_tools": "zrb.llm.tool.plan",
    "create_rag_from_directory": "zrb.llm.tool.rag",
    "create_run_zrb_task_tool": "zrb.llm.tool.zrb_task",
    "create_search_skill_tool": "zrb.llm.tool.skill",
    "get_todos": "zrb.llm.tool.plan",
    "glob_files": "zrb.llm.tool.file",
    "list_files": "zrb.llm.tool.file",
    "load_mcp_config": "zrb.llm.tool.mcp",
    "log_activity": "zrb.llm.tool.journal_write",
    "move_file": "zrb.llm.tool.file",
    "open_web_page": "zrb.llm.tool.web",
    "read_file": "zrb.llm.tool.file",
    "remove_file": "zrb.llm.tool.file",
    "replace_in_file": "zrb.llm.tool.file",
    "run_shell_command": "zrb.llm.tool.shell",
    "search_files": "zrb.llm.tool.file",
    "search_internet": "zrb.llm.tool.web",
    "search_journal": "zrb.llm.tool.journal",
    "tool_name": "zrb.llm.tool_registry",
    "tool_registry": "zrb.llm.tool_registry",
    "write_file": "zrb.llm.tool.file",
    "write_journal_note": "zrb.llm.tool.journal_write",
    "write_todos": "zrb.llm.tool.plan",
}


def __getattr__(name: str):
    source = _SOURCES.get(name)
    if source is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # lazy: transitively heavy via internal — tool modules reach pdfplumber, mcp, prompt_toolkit
    import importlib

    value = getattr(importlib.import_module(source), name)
    globals()[name] = value
    return value
