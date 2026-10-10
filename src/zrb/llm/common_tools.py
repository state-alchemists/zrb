"""Shared default-tool registration for zrb-shipped agents.

`apply_common_tools(host)` gives a ``CommonToolHost`` the shipped tools,
toolset factories and shell-safety policy, so ``LLMChatTask``, ``LLMTask`` and
``SubAgentManager`` share one tool surface. The canonical set lives in
``tool_registry`` (``registry.py``); this module owns its lazy seed
(``tool_registry.set_seed``) and the host glue.

Application only appends per-run providers; nothing resolves until the host's
first agent build, which keeps ``pydantic_ai`` off ``import zrb``. LSP,
worktree, plan-mode and journal tools register conditionally, rare ones use
``defer_loading``.

Not registered here: delegate tools (main-agent-only; sub-agents filter them
via ``zrb_is_delegate_tool``), argument formatters and response handlers
(owned by ``LLMChatTask``, reaching sub-agents through the
``current_tool_confirmation`` ContextVar).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from zrb.config.config import CFG
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.registry import tool_name, tool_registry
from zrb.llm.tool_call.tool_policy.bash_validation import bash_safe_command_policy
from zrb.llm.util.git import is_inside_git_dir
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import Tool


@runtime_checkable
class CommonToolHost(Protocol):
    """Minimal interface `apply_common_tools` needs from a host."""

    def append_tool(self, *tool: "Callable | Tool") -> None: ...
    def append_tool_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...

    def append_toolset_factory(
        self, *factory: "Callable[[AnyContext], Any]"
    ) -> None: ...


def apply_common_tools(host: CommonToolHost) -> None:
    """Give *host* the zrb-shipped tools, factories, and shell-safety policy.

    Storage only (safe at construction, no heavy import); call once per host.
    ``SubAgentManager`` filters the result by each sub-agent's ``tools:`` list.
    """
    host.append_tool_factory(_common_tools_provider)
    host.append_toolset_factory(_common_toolsets_provider)
    # Read-only git subcommands auto-approve. Hosts without an approval channel
    # (LLMTask, SubAgentManager) have no prepend_tool_policy.
    add_policy = getattr(host, "prepend_tool_policy", None)
    if callable(add_policy):
        add_policy(bash_safe_command_policy())


def _common_tools_provider(
    ctx: "AnyContext",
) -> "list[Callable | Tool]":
    """Per-run provider: the full common tool surface, re-evaluating env gates each build."""
    tools = list(tool_registry.get_tools())
    for factory in tool_registry.get_tool_factories():
        produced = factory(ctx)
        tools.extend(produced if isinstance(produced, list) else [produced])
    return tools


def _common_toolsets_provider(ctx: "AnyContext") -> list:
    """Per-run provider: the common toolset content (e.g. MCP servers)."""
    produced: list = []
    for factory in tool_registry.get_toolset_factories():
        items = factory(ctx)
        produced.extend(items if isinstance(items, list) else [items])
    return produced


def _seed_default_tool_registry() -> None:
    """Install ``_seed_default_tools`` as ``tool_registry``'s lazy seed."""
    tool_registry.set_seed(_seed_default_tools)


def _seed_default_tools() -> tuple[list, list, list]:
    """The built-in tool content: (tools, tool_factories, toolset_factories).

    A new tool under `llm/tool/` must be imported, `tag()`-ed with a
    `Capability`, and appended here, or it resolves to `Capability.UNKNOWN`.
    """
    # Imported from source modules, not the ``zrb.llm.tool`` re-export: that
    # loads ``delegate.py`` -> ``SubAgentManager``, which re-enters this function.
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import Tool

    # lazy: zrb internal (heavy via transitive) — the LSP client stack
    from zrb.llm.lsp.configs import detect_available_lsp_servers
    from zrb.llm.lsp.tools import create_lsp_tools

    # lazy: zrb.llm.tool.* transitively load pydantic_ai
    from zrb.llm.tool.code import analyze_code
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
    from zrb.llm.tool.plan import get_todos, write_todos
    from zrb.llm.tool.shell import run_shell_command
    from zrb.llm.tool.web import open_web_page, search_internet
    from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees

    # Only when a language server is on $PATH (no server is started).
    lsp_tools = create_lsp_tools() if detect_available_lsp_servers() else []
    # Only inside a git repo (judged from the startup cwd).
    worktree_tools = (
        [enter_worktree, exit_worktree, list_worktrees] if is_inside_git_dir() else []
    )
    plan_tools = [write_todos, get_todos]

    # Untagged tools resolve to UNKNOWN (denied in plan mode).
    for _fn in (
        list_files,
        glob_files,
        read_file,
        search_files,
        analyze_file,
        analyze_code,
    ):
        tag(_fn, Capability.READ)
    for _fn in (write_file, replace_in_file, remove_file, move_file):
        tag(_fn, Capability.EDIT)
    # list is read-only; enter/exit mutate the tree.
    for _fn in worktree_tools:
        tag(_fn, Capability.READ if _fn is list_worktrees else Capability.EDIT)
    tag(run_shell_command, Capability.EXECUTE)
    for _fn in (search_internet, open_web_page):
        tag(_fn, Capability.NETWORK)
    for _fn in plan_tools:
        tag(_fn, Capability.META)
    for _tool in lsp_tools:
        tag(_tool, Capability.EDIT if "Rename" in tool_name(_tool) else Capability.READ)

    tools: list["Callable | Tool"] = [
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
        *(Tool(_fn, defer_loading=True) for _fn in worktree_tools),
        *(Tool(_fn, defer_loading=True) for _fn in lsp_tools),
        *plan_tools,
    ]
    factories, toolset_factories = _seed_tool_factories()
    return tools, factories, toolset_factories


def _seed_tool_factories() -> tuple[list, list]:
    """The per-run tool factories + toolset factories of the built-in seed."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.spill import read_tool_result
    from zrb.llm.agent.types import Tool

    # lazy: zrb.llm.tool.* transitively load pydantic_ai
    from zrb.llm.permission import Capability, tag
    from zrb.llm.tool.ask import ask_user_question
    from zrb.llm.tool.journal import search_journal
    from zrb.llm.tool.journal_write import (
        delete_journal_note,
        log_activity,
        write_journal_note,
    )
    from zrb.llm.tool.mcp import load_mcp_config
    from zrb.llm.tool.plan_mode import enter_plan_mode, exit_plan_mode
    from zrb.llm.tool.shell_background import create_monitor_process_tool
    from zrb.llm.tool.skill import create_activate_skill_tool, create_search_skill_tool
    from zrb.llm.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )

    tag(ask_user_question, Capability.META)
    tag(read_tool_result, Capability.META)
    tag(search_journal, Capability.READ)
    # Journal writers touch only CFG.LLM_JOURNAL_DIR, but plan mode still blocks them.
    for _fn in (log_activity, write_journal_note, delete_journal_note):
        tag(_fn, Capability.EDIT)

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
        # A factory so toggling LLM_ENABLE_TOOL_SPILL via /config applies next run.
        lambda ctx: [read_tool_result] if CFG.LLM_ENABLE_TOOL_SPILL else [],
        # LLM_JOURNAL_ENABLED=false is enforced by these tools' absence. The
        # journal-compliance hook names them, so `resolve_agent_hook_tools`
        # strips defer_loading there.
        lambda ctx: (
            [
                Tool(search_journal, defer_loading=True),
                Tool(log_activity, defer_loading=True),
                Tool(write_journal_note, defer_loading=True),
                Tool(delete_journal_note, defer_loading=True),
            ]
            if CFG.LLM_JOURNAL_ENABLED
            else []
        ),
        lambda ctx: Tool(
            tag(create_list_zrb_task_tool(), Capability.READ),
            defer_loading=True,
        ),
        lambda ctx: Tool(
            tag(create_run_zrb_task_tool(), Capability.EXECUTE),
            defer_loading=True,
        ),
        lambda ctx: tag(create_activate_skill_tool(), Capability.META),
        # SearchSkill reaches the part of the catalogue the prompt truncates.
        lambda ctx: tag(create_search_skill_tool(), Capability.META),
        lambda ctx: Tool(
            tag(create_monitor_process_tool(), Capability.EXECUTE),
            defer_loading=True,
        ),
    ]
    toolset_factories: list["Callable[[AnyContext], Any]"] = [
        lambda ctx: [toolset.defer_loading() for toolset in load_mcp_config()]
    ]
    return factories, toolset_factories


def _resolve_interactive(ctx: "AnyContext") -> bool:
    """Interactivity from ``ctx.input.interactive``, else the ``interactive_mode`` ContextVar."""
    from zrb.llm.tool.ambient_state import get_interactive_mode

    val = getattr(getattr(ctx, "input", None), "interactive", None)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return to_boolean(val)
    return get_interactive_mode()


_seed_default_tool_registry()
