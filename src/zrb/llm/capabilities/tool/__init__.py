"""zrb-shipped LLM tools, grouped by the domain they act on.

A domain with several modules is a package — `file/`, `delegate/`, `shell/`,
`plan/`, `web/`, `code/` — and its `__init__` re-exports the names the flat
module used to export, so `from zrb.llm.capabilities.tool.file import read_file` still
resolves. A tool that is one module stays a module.

Re-exports resolve lazily through PEP 562 `__getattr__`, so importing one
submodule does not load the whole family (~94ms).

`code` and `delegate` are not re-exported here: they need the agent run loop
throughout, so import them from their own package.

File tools resolve through `file/__init__.py`, which sets each one's `__name__`
to its schema name (`Read`, `Write`, ...).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.capabilities.tool.file import (
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
    from zrb.llm.capabilities.tool.mcp import load_mcp_config
    from zrb.llm.capabilities.tool.plan import create_plan_tools, get_todos, write_todos
    from zrb.llm.capabilities.tool.shell import run_shell_command
    from zrb.llm.capabilities.tool.shell.background import create_monitor_process_tool
    from zrb.llm.capabilities.tool.skill import (
        create_activate_skill_tool,
        create_search_skill_tool,
    )
    from zrb.llm.capabilities.tool.web import open_web_page, search_internet
    from zrb.llm.capabilities.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )
    from zrb.llm.contracts.shared.tool_registry import (
        ToolRegistry,
        tool_name,
        tool_registry,
    )

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
    "load_mcp_config",
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
    "ToolRegistry": "zrb.llm.contracts.shared.tool_registry",
    "analyze_file": "zrb.llm.capabilities.tool.file",
    "create_activate_skill_tool": "zrb.llm.capabilities.tool.skill",
    "create_list_zrb_task_tool": "zrb.llm.capabilities.tool.zrb_task",
    "create_monitor_process_tool": "zrb.llm.capabilities.tool.shell.background",
    "create_plan_tools": "zrb.llm.capabilities.tool.plan",
    "create_run_zrb_task_tool": "zrb.llm.capabilities.tool.zrb_task",
    "create_search_skill_tool": "zrb.llm.capabilities.tool.skill",
    "get_todos": "zrb.llm.capabilities.tool.plan",
    "glob_files": "zrb.llm.capabilities.tool.file",
    "list_files": "zrb.llm.capabilities.tool.file",
    "load_mcp_config": "zrb.llm.capabilities.tool.mcp",
    "move_file": "zrb.llm.capabilities.tool.file",
    "open_web_page": "zrb.llm.capabilities.tool.web",
    "read_file": "zrb.llm.capabilities.tool.file",
    "remove_file": "zrb.llm.capabilities.tool.file",
    "replace_in_file": "zrb.llm.capabilities.tool.file",
    "run_shell_command": "zrb.llm.capabilities.tool.shell",
    "search_files": "zrb.llm.capabilities.tool.file",
    "search_internet": "zrb.llm.capabilities.tool.web",
    "tool_name": "zrb.llm.contracts.shared.tool_registry",
    "tool_registry": "zrb.llm.contracts.shared.tool_registry",
    "write_file": "zrb.llm.capabilities.tool.file",
    "write_todos": "zrb.llm.capabilities.tool.plan",
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
