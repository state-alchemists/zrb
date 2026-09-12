"""zrb-shipped LLM tools — one module per tool family.

Re-exports every tool whose module has no module-level dependency on
`zrb.llm.agent` — verified empirically, not just by inspection: hoisting a
tool import here and running `import zrb` from every plausible entry point
must not raise, or it doesn't belong in this file.

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
Every name below resolves on first access (PEP 562) rather than at package
import. `registry.py` keeps its built-in tool list behind a lazy seed so the
heavy imports run on the first agent build; re-exporting eagerly here undoes
that, because importing `zrb.llm.tool.registry` runs this module first.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.tool.file import (  # noqa: F401
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
    from zrb.llm.tool.journal import (  # noqa: F401
        search_journal,
    )
    from zrb.llm.tool.journal_write import (  # noqa: F401
        log_activity,
        write_journal_note,
    )
    from zrb.llm.tool.mcp import (  # noqa: F401
        load_mcp_config,
    )
    from zrb.llm.tool.plan import (  # noqa: F401
        create_plan_tools,
        get_todos,
        write_todos,
    )
    from zrb.llm.tool.rag import (  # noqa: F401
        create_rag_from_directory,
    )
    from zrb.llm.tool.registry import (  # noqa: F401
        ToolRegistry,
        tool_name,
        tool_registry,
    )
    from zrb.llm.tool.shell import (  # noqa: F401
        run_shell_command,
    )
    from zrb.llm.tool.shell_background import (  # noqa: F401
        create_monitor_process_tool,
    )
    from zrb.llm.tool.skill import (  # noqa: F401
        create_activate_skill_tool,
        create_search_skill_tool,
    )
    from zrb.llm.tool.web import (  # noqa: F401
        open_web_page,
        search_internet,
    )
    from zrb.llm.tool.zrb_task import (  # noqa: F401
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )


_MODULE_OF = {
    "analyze_file": "file",
    "glob_files": "file",
    "list_files": "file",
    "move_file": "file",
    "read_file": "file",
    "remove_file": "file",
    "replace_in_file": "file",
    "search_files": "file",
    "write_file": "file",
    "search_journal": "journal",
    "log_activity": "journal_write",
    "write_journal_note": "journal_write",
    "load_mcp_config": "mcp",
    "create_plan_tools": "plan",
    "get_todos": "plan",
    "write_todos": "plan",
    "create_rag_from_directory": "rag",
    "ToolRegistry": "registry",
    "tool_name": "registry",
    "tool_registry": "registry",
    "run_shell_command": "shell",
    "create_monitor_process_tool": "shell_background",
    "create_activate_skill_tool": "skill",
    "create_search_skill_tool": "skill",
    "open_web_page": "web",
    "search_internet": "web",
    "create_list_zrb_task_tool": "zrb_task",
    "create_run_zrb_task_tool": "zrb_task",
}


def __getattr__(name: str):
    """Import the owning tool module on first access to `name`."""
    module = _MODULE_OF.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(f"zrb.llm.tool.{module}"), name)
    globals()[name] = value  # cache, so later reads skip this path
    return value


def __dir__():
    return sorted(__all__)


__all__ = [
    "ToolRegistry",
    "analyze_file",
    "create_activate_skill_tool",
    "create_list_zrb_task_tool",
    "create_monitor_process_tool",
    "create_plan_tools",
    "create_rag_from_directory",
    "create_run_zrb_task_tool",
    "create_search_skill_tool",
    "get_todos",
    "glob_files",
    "list_files",
    "load_mcp_config",
    "log_activity",
    "move_file",
    "open_web_page",
    "read_file",
    "remove_file",
    "replace_in_file",
    "run_shell_command",
    "search_files",
    "search_internet",
    "search_journal",
    "tool_name",
    "tool_registry",
    "write_file",
    "write_journal_note",
    "write_todos",
]
