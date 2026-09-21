"""zrb-shipped LLM tools — one module per tool family.

Re-exports resolve through PEP 562 `__getattr__` (ADR-0096's pattern), so
importing one submodule loads that module alone. Eager re-exports here cost
every importer the whole family — 29 modules and ~94ms, paid by a `zrb --help`
that never reaches an LLM, because importing any submodule runs this file.

Two families are deliberately NOT re-exported here, because their tools
genuinely need the agent run loop for more than one call path each:

- `code.py` (`AnalyzeCode`) delegates to a sub-agent across several internal
  helpers, not just one function — making that lazy would mean repeating the
  same import at each call site for one tool, worse than just importing it
  from its own module.
- `delegate.py` (`DelegateToAgent`, `SearchAgent`) — delegation *is* what
  these tools do; `zrb.llm.agent`/`SubAgentManager` aren't an occasional
  side path, they're the whole function body.

Import those two directly from their own module instead, e.g.
`from zrb.llm.tool.code import analyze_code`. Every other tool here that
*does* occasionally need the agent (e.g. `open_web_page`'s summarization
step) keeps that import lazy, function-scoped, inside just the one path that
needs it — see `web.py::_summarize_web_content` for the pattern.

The file tools resolve through `file.py` rather than their own leaf modules
(`file_read`, `file_write`, …) on purpose: `file.py` rewrites each one's
`__name__` to the schema name the model sees (`Read`, `Write`, `Edit`, …),
so reaching a leaf directly would register a tool under its Python name.
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
    from zrb.llm.tool.registry import ToolRegistry, tool_name, tool_registry
    from zrb.llm.tool.shell import run_shell_command
    from zrb.llm.tool.shell_background import create_monitor_process_tool
    from zrb.llm.tool.skill import create_activate_skill_tool, create_search_skill_tool
    from zrb.llm.tool.web import open_web_page, search_internet
    from zrb.llm.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
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
    # Planning tools
    "create_plan_tools",
    "write_todos",
    "get_todos",
]

_SOURCES = {
    "ToolRegistry": "zrb.llm.tool.registry",
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
    "tool_name": "zrb.llm.tool.registry",
    "tool_registry": "zrb.llm.tool.registry",
    "write_file": "zrb.llm.tool.file",
    "write_journal_note": "zrb.llm.tool.journal_write",
    "write_todos": "zrb.llm.tool.plan",
}


def __getattr__(name: str):
    source = _SOURCES.get(name)
    if source is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # lazy: transitively heavy via internal — resolving one name eagerly
    # re-exported all 29 tool modules (94ms on `import zrb`), and several of
    # them reach pdfplumber, mcp and prompt_toolkit.
    import importlib

    value = getattr(importlib.import_module(source), name)
    globals()[name] = value
    return value
