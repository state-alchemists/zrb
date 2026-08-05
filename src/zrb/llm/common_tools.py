"""Shared default-tool registration for zrb-shipped agents.

`apply_common_tools(host)` registers the standard zrb-shipped tools, toolset
factories, and the shell-safety policy on any host that conforms to
``CommonToolHost`` — used by ``LLMChatTask`` (main agent), ``LLMTask``
(programmatic agents), and ``SubAgentManager`` (sub-agents) so they share the
same tool surface.

There is no prompt-side tool catalogue. What a tool does, what its arguments
mean, and which tool to reach for instead all live in the tool's own docstring,
next to the schema the model fills in. pydantic-ai serializes every registered
tool's docstring + parameter schema into every request either way, so the
docstring is not deferred context — the only lever on tool-definition weight is
the *number* of registered tools, which is why LSP, worktree, plan-mode, and
journal tools are registered conditionally and rarely-used ones use
``defer_loading``.

Delegate tools (``DelegateToAgent`` — which also fans out via its ``tasks``
arg — and ``DelegateToAgentBackground``) are intentionally NOT registered here
— they're main-agent-only and sub-agents filter them out via
``zrb_is_delegate_tool``. Argument formatters and response handlers are out of
scope: those live on ``LLMChatTask`` and propagate to sub-agents at runtime via
the ``current_tool_confirmation`` ContextVar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

from zrb.config.config import CFG
from zrb.llm.util.git import is_inside_git_dir
from zrb.util.string.conversion import to_boolean

# NOTE: `zrb.llm.tool` and `zrb.llm.lsp.tools` are imported lazily inside
# ``apply_common_tools``. Reason: ``zrb.llm.tool/__init__.py`` loads
# ``delegate.py``, which imports ``SubAgentManager`` from
# ``zrb.llm.agent.subagent.manager``. If this module is loaded
# before ``manager.py`` (e.g. via ``builtin/llm/chat.py``), the
# ``manager.py`` bottom-imports ``default_tools.py`` which re-enters
# ``apply_common_tools`` while this module is still mid-load — causing an
# ImportError on ``apply_common_tools``. Keeping the heavy imports inside
# the function defers them until ``apply_common_tools`` is actually
# called, by which point all the cycle's modules are fully loaded.

if TYPE_CHECKING:
    from pydantic_ai.tools import Tool

    from zrb.context.any_context import AnyContext


@runtime_checkable
class CommonToolHost(Protocol):
    """Minimal interface needed by ``apply_common_tools``.

    Satisfied by ``LLMChatTask``, ``LLMTask``, and ``SubAgentManager``.
    """

    def add_tool(self, *tool: "Callable | Tool") -> None: ...
    def add_tool_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...
    def add_toolset_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...


def apply_common_tools(host: CommonToolHost) -> None:
    """Register zrb-shipped default tools, factories, and guidance on ``host``.

    Idempotent only if called once per host — calling twice will register
    everything twice.
    """
    # lazy + import from source modules directly. Going through the
    # ``zrb.llm.tool`` re-export would deadlock: that package's __init__
    # loads ``delegate.py`` which triggers ``SubAgentManager`` load which
    # ultimately re-enters this function. By that time the re-export
    # names (``analyze_file``, etc.) aren't yet bound on ``zrb.llm.tool``.
    # lazy: zrb internal (heavy via transitive / circular)
    # Register the 8 LSP tools only when a language server is actually installed
    # — their own guidance already says to fall back to Read + Grep when none is
    # available, so advertising them in a server-less repo is pure prompt weight.
    # detect_available_lsp_servers() is a cheap shutil.which scan (no startup).
    # lazy: zrb internal (heavy via transitive / circular)
    # lazy: pydantic_ai (heavy third-party deferral)
    from pydantic_ai import Tool

    from zrb.llm.lsp.configs import detect_available_lsp_servers
    from zrb.llm.lsp.tools import create_lsp_tools

    # lazy: permission is a leaf module.
    from zrb.llm.permission import Capability, tag

    # lazy: zrb.llm.tool.* transitively load pydantic_ai; deferring keeps cold-start
    # latency off the import path for callers that never apply common tools.
    from zrb.llm.tool.ask import ask_user_question
    from zrb.llm.tool.bash import run_bash_command
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
    from zrb.llm.tool.journal import search_journal
    from zrb.llm.tool.journal_write import log_activity, write_journal_note
    from zrb.llm.tool.mcp import load_mcp_config
    from zrb.llm.tool.plan import get_todos, write_todos
    from zrb.llm.tool.plan_mode import enter_plan_mode, exit_plan_mode
    from zrb.llm.tool.shell import run_shell_command
    from zrb.llm.tool.shell_background import create_monitor_process_tool
    from zrb.llm.tool.skill import create_activate_skill_tool
    from zrb.llm.tool.web import open_web_page, search_internet
    from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees
    from zrb.llm.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )

    # lazy: circular — tool_policy → handler → ui → llm_task → here
    from zrb.llm.tool_call.tool_policy.bash_validation import bash_safe_command_policy

    lsp_tools = create_lsp_tools() if detect_available_lsp_servers() else []
    # Worktree tools only make sense inside a git repo — registering them in a
    # non-git directory is pure prompt weight (their guidance is auto-suppressed
    # by the runtime tool_names filter, but the docstrings + schemas would still
    # ship on every request). Mirrors the LSP gate above. is_inside_git_dir() is
    # evaluated against the startup cwd; a user in a non-git dir trades away the
    # tools' `cwd`-points-elsewhere escape hatch, same as the LSP gate trades
    # away server-less repos — acceptable for the token saving.
    worktree_tools = (
        [enter_worktree, exit_worktree, list_worktrees] if is_inside_git_dir() else []
    )
    # TodoWrite replaces the whole list by default, so it subsumes the former
    # UpdateTodo (rewrite with one status changed) and ClearTodos (write []).
    plan_tools = [write_todos, get_todos]

    # Tag each tool with its capability so the permission policy / plan mode can
    # reason about it. Untagged tools resolve to UNKNOWN (denied in plan mode),
    # so tagging the read-only ones explicitly keeps discovery working.
    for _fn in (
        list_files,
        glob_files,
        read_file,
        search_files,
        analyze_file,
        analyze_code,
        search_journal,
    ):
        tag(_fn, Capability.READ)
    for _fn in (
        write_file,
        replace_in_file,
        remove_file,
        move_file,
        # The journal writers only ever touch CFG.LLM_JOURNAL_DIR, but they do
        # write, so plan mode must block them like any other edit.
        log_activity,
        write_journal_note,
    ):
        tag(_fn, Capability.EDIT)
    # Tag worktree tools only when registered (git dir): list is read-only,
    # enter/exit mutate the tree. Mirrors the lsp_tools tagging loop below.
    for _fn in worktree_tools:
        tag(_fn, Capability.READ if _fn is list_worktrees else Capability.EDIT)
    tag(run_shell_command, Capability.EXECUTE)
    tag(run_bash_command, Capability.EXECUTE)
    for _fn in (search_internet, open_web_page):
        tag(_fn, Capability.NETWORK)
    for _fn in plan_tools + [ask_user_question]:
        tag(_fn, Capability.META)
    for _tool in lsp_tools:
        _name = getattr(_tool, "__name__", "") or getattr(_tool, "name", "")
        tag(_tool, Capability.EDIT if "Rename" in _name else Capability.READ)

    host.add_tool(
        run_shell_command,
        run_bash_command,
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
        # Deferred loading: these are rarely needed (specific workflows or
        # server-gated), so hide their schemas from the model's initial
        # context. The model discovers them by keyword search only when it
        # needs one, instead of paying their token cost on every turn.
        # Tool Usage Guide entries stay visible regardless (tool_names is
        # populated from all registered tools, deferred or not) — the model
        # still learns these tools exist and when to reach for them, it just
        # pays their schema cost only once it searches for them by name.
        Tool(analyze_code, defer_loading=True),
        Tool(analyze_file, defer_loading=True),
        *(Tool(_fn, defer_loading=True) for _fn in worktree_tools),
        *(Tool(_fn, defer_loading=True) for _fn in lsp_tools),
        *plan_tools,
    )
    # Plan-mode and AskUserQuestion need a human in the loop, so register them
    # only in interactive sessions. In non-interactive runs (one-shot CLI,
    # sub-agents, programmatic LLMTask) they are dead weight — AskUserQuestion
    # short-circuits and the prompt already says to skip plan mode — yet their
    # docstrings + schemas (~350-450 tok) would still ship on every request.
    # Gating drops them; the runtime tool_names filter auto-suppresses their
    # Tool Usage Guide entries to match. Factories (not static add_tool) so the
    # gate is re-evaluated per run against the resolved context.
    host.add_tool_factory(
        lambda ctx: (
            [
                Tool(enter_plan_mode, defer_loading=True),
                Tool(exit_plan_mode, defer_loading=True),
            ]
            if _resolve_interactive(ctx)
            else []
        ),
        lambda ctx: [ask_user_question] if _resolve_interactive(ctx) else [],
        # The journal tools are the whole journal interface — there is no prompt
        # section describing the protocol any more, so LLM_JOURNAL_ENABLED=false
        # is enforced by these three simply not existing. Their docstrings carry
        # what earns an entry and when to write it, and disappear with them.
        lambda ctx: (
            [search_journal, log_activity, write_journal_note]
            if CFG.LLM_JOURNAL_ENABLED
            else []
        ),
    )
    host.add_tool_factory(
        lambda ctx: tag(create_list_zrb_task_tool(), Capability.READ),
        lambda ctx: tag(create_run_zrb_task_tool(), Capability.EXECUTE),
        lambda ctx: tag(create_activate_skill_tool(), Capability.META),
        # Deferred loading: only needed after monitoring a background process —
        # see the rationale on analyze_code/analyze_file above.
        lambda ctx: Tool(
            tag(create_monitor_process_tool(), Capability.EXECUTE),
            defer_loading=True,
        ),
    )
    # MCP servers vary widely in tool count; hide them behind search too —
    # same rationale as the deferred function tools above.
    host.add_toolset_factory(
        lambda ctx: [toolset.defer_loading() for toolset in load_mcp_config()]
    )
    # Shell safety travels with the shell tools rather than with one builtin
    # task: the allowlist in bash_safe_command_policy IS the git approval rule
    # (read-only subcommands auto-approve, `commit`/`push`/`reset` reach the
    # user), so registering it here is what lets that rule stay out of the
    # prompt. Hosts without an approval channel (programmatic LLMTask,
    # SubAgentManager — the latter inherits the caller's confirmation via the
    # current_tool_confirmation ContextVar) have no add_tool_policy; skip them.
    add_policy = getattr(host, "add_tool_policy", None)
    if callable(add_policy):
        add_policy(bash_safe_command_policy())


def defer_common_tools(host: CommonToolHost) -> None:
    """Register ``apply_common_tools(host)`` to run on first use instead of now.

    ``apply_common_tools`` transitively imports ``pydantic_ai`` (via the
    ``zrb.llm.tool.*`` functions and the ``Tool`` class). Calling it at module
    import — as the ``llm_chat`` and ``sub_agent_manager`` singletons used to —
    dragged that ~1.7s import onto every ``import zrb``. Deferring it to the
    first agent build (``ensure_common_tools`` at the top of the exec /
    ``create_agent`` entry points) keeps the heavy import off the cold path for
    callers that never run an agent. See ``ensure_common_tools``.
    """
    setattr(host, "_pending_common_tools", True)


def ensure_common_tools(host: CommonToolHost) -> None:
    """Run the deferred ``apply_common_tools`` once, if one is pending.

    No-op for hosts that never called ``defer_common_tools`` (e.g. bare
    ``LLMChatTask`` instances that are not the ``llm_chat`` singleton), so the
    deferral stays scoped to exactly the singletons that had the eager call.
    """
    if getattr(host, "_pending_common_tools", False):
        setattr(host, "_pending_common_tools", False)
        apply_common_tools(host)


def _resolve_interactive(ctx: "AnyContext") -> bool:
    """Interactivity as seen when tool factories resolve.

    The main chat task carries the flag on ``ctx.input.interactive`` (already
    resolved by the time factories run). Sub-agents and programmatic
    ``LLMTask`` don't expose it, so fall back to the ``interactive_mode``
    ContextVar (set by live_context once a session is running, hence reliable
    by the time a sub-agent's tools resolve). Absent both, default True so no
    host silently loses tools it had before.
    """
    # lazy: zrb.llm.tool.ask transitively loads pydantic_ai; deferring keeps
    # the heavy import off this module's load path.
    from zrb.llm.tool.ask import get_interactive_mode

    val = getattr(getattr(ctx, "input", None), "interactive", None)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return to_boolean(val)
    return get_interactive_mode()
