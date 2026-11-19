"""The built-in tool surface, and the seed that carries it to `tool_registry`.

`apply_common_tools` hands a host what zrb ships; the set itself is written
down here, and importing this module installs it as `tool_registry`'s lazy
seed. It sits in the engine package because that is the lowest layer that may
name every tool it lists — `tool/`, `lsp/` and `agent/types.py` are all at or
below it — while its callers are exactly the layers above: a host building an
agent, and the agent hook resolving a hook's `tools:`.

The seed stays lazy. The built-ins import `pydantic_ai`, so nothing here
resolves until a host builds an agent; `import zrb` must not pay for that.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.contracts.shared.ambient_state import get_interactive_mode
from zrb.llm.contracts.shared.tool_registry import ToolLike, ToolSeed, tool_registry
from zrb.llm.contracts.util.git import is_inside_git_dir
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext


def seed_default_tools() -> ToolSeed:
    """The built-in tool content: (tools, tool_factories, toolset_factories).

    A new tool under `llm/capabilities/tool/` tags itself where it is defined — `tag(...)`
    with its `Capability` — and is exported and appended here. A tool also
    reaches an agent by reference (`LLMTask(tools=[read_file])`), and that path
    never resolves this registry: only the tag on the tool itself says what it
    may touch. Without one the sandbox write-checks every path it names.
    """
    # Imported from source modules, not the ``zrb.llm.capabilities.tool`` re-export: that
    # loads ``delegate.py`` -> ``SubAgentManager``, which re-enters this function.
    # lazy: zrb internal (heavy via transitive)
    # lazy: zrb internal (heavy via transitive) — the LSP client stack
    from zrb.llm.capabilities.lsp.configs import detect_available_lsp_servers
    from zrb.llm.capabilities.lsp.tools import create_lsp_tools

    # lazy: zrb.llm.capabilities.tool.* transitively load pydantic_ai
    from zrb.llm.capabilities.tool.code import analyze_code
    from zrb.llm.capabilities.tool.delegate.worktree import (
        enter_worktree,
        exit_worktree,
        list_worktrees,
    )
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
    from zrb.llm.capabilities.tool.plan import get_todos, write_todos
    from zrb.llm.capabilities.tool.shell import run_shell_command
    from zrb.llm.capabilities.tool.web import open_web_page, search_internet
    from zrb.llm.engine.agent.types import Tool

    # Only when a language server is on $PATH (no server is started).
    lsp_tools = create_lsp_tools() if detect_available_lsp_servers() else []
    # Only inside a git repo (judged from the startup cwd).
    worktree_tools: list[Callable] = (
        [enter_worktree, exit_worktree, list_worktrees] if is_inside_git_dir() else []
    )
    # Visible, not deferred: a deferred tool is invisible until the model thinks
    # to search for it, and the set of tools nobody thought of is the set nobody
    # used (EnterWorktree: 1 call in a week, ExitWorktree and ListWorktrees: 0).
    # All three sit inside the git gate, so a non-repo session still pays nothing.
    plan_tools: list[Callable] = [write_todos, get_todos]

    tools: list[ToolLike] = [
        run_shell_command,
        list_files,
        glob_files,
        read_file,
        write_file,
        replace_in_file,
        search_files,
        remove_file,
        move_file,
        search_internet,
        open_web_page,
        # Rarely needed: the schema loads only through native tool search.
        Tool(analyze_code, defer_loading=True),
        Tool(analyze_file, defer_loading=True),
        *worktree_tools,
        *(Tool(_fn, defer_loading=True) for _fn in lsp_tools),
        *plan_tools,
    ]
    factories, toolset_factories = seed_tool_factories()
    return tools, factories, toolset_factories


def seed_tool_factories() -> tuple[list, list]:
    """The per-run tool factories + toolset factories of the built-in seed."""
    # lazy: zrb internal (heavy via transitive)
    # lazy: zrb.llm.capabilities.tool.* transitively load pydantic_ai
    from zrb.llm.capabilities.tool.ask import ask_user_question
    from zrb.llm.capabilities.tool.mcp import load_mcp_config
    from zrb.llm.capabilities.tool.memory import forget, remember, search_memory
    from zrb.llm.capabilities.tool.plan.mode import enter_plan_mode, exit_plan_mode
    from zrb.llm.capabilities.tool.shell.background import create_monitor_process_tool
    from zrb.llm.capabilities.tool.skill import (
        create_activate_skill_tool,
        create_search_skill_tool,
    )
    from zrb.llm.capabilities.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )
    from zrb.llm.engine.agent.spill import read_tool_result
    from zrb.llm.engine.agent.types import Tool

    factories: list["Callable[[AnyContext], Any]"] = [
        # Plan-mode and AskUserQuestion need a human: interactive sessions only.
        lambda ctx: (
            [
                Tool(enter_plan_mode, defer_loading=True),
                Tool(exit_plan_mode, defer_loading=True),
            ]
            if _resolve_interactive(ctx)
            else []
        ),
        lambda ctx: [ask_user_question] if _resolve_interactive(ctx) else [],
        # A factory so toggling LLM_TOOL_SPILL_ENABLED via /config applies next run.
        lambda ctx: [read_tool_result] if CFG.LLM_TOOL_SPILL_ENABLED else [],
        # Memory: three tools, none deferred. A schema behind `search_tools` asks
        # the model to think of a search before it can search — the step that
        # gets skipped — and a write verb nobody can see is a memory nobody
        # records. `LLM_MEMORY_ENABLED=false` is enforced by these tools'
        # absence: no other store stands behind them now.
        lambda ctx: (
            [search_memory, remember, forget] if CFG.LLM_MEMORY_ENABLED else []
        ),
        lambda ctx: Tool(create_list_zrb_task_tool(), defer_loading=True),
        lambda ctx: Tool(create_run_zrb_task_tool(), defer_loading=True),
        lambda ctx: create_activate_skill_tool(),
        # SearchSkill reaches the part of the catalogue the prompt truncates.
        lambda ctx: create_search_skill_tool(),
        lambda ctx: Tool(create_monitor_process_tool(), defer_loading=True),
    ]
    toolset_factories: list["Callable[[AnyContext], Any]"] = [
        lambda ctx: [toolset.defer_loading() for toolset in load_mcp_config()]
    ]
    return factories, toolset_factories


def _resolve_interactive(ctx: "AnyContext") -> bool:
    """Interactivity from ``ctx.input.interactive``, else the ``interactive_mode`` ContextVar."""
    val = getattr(getattr(ctx, "input", None), "interactive", None)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return to_boolean(val)
    return get_interactive_mode()


# Importing this module is what installs the built-ins, so a reader anywhere may
# read `tool_registry` and see the surface zrb ships — including an agent hook,
# which runs outside any task run and cannot reach the host glue above it.
tool_registry.set_seed(seed_default_tools)
