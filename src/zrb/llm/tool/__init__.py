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
"""

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
from zrb.llm.tool.plan import (
    create_plan_tools,
    get_todos,
    write_todos,
)
from zrb.llm.tool.rag import create_rag_from_directory
from zrb.llm.tool.registry import ToolRegistry, tool_name, tool_registry
from zrb.llm.tool.shell import run_shell_command
from zrb.llm.tool.shell_background import create_monitor_process_tool
from zrb.llm.tool.skill import (
    create_activate_skill_tool,
    create_search_skill_tool,
)
from zrb.llm.tool.web import open_web_page, search_internet
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool

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
