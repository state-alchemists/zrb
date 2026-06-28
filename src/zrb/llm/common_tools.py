"""Shared default-tool registration for zrb-shipped agents.

`apply_common_tools(host)` registers the standard zrb-shipped tools,
toolset factories, static tool guidance, dynamic guidance factories, and
the model-aware Tool Usage Guide section factory on any host that
conforms to ``CommonToolHost`` — used by both ``LLMChatTask`` (main
agent), ``LLMTask`` (programmatic agents), and ``SubAgentManager``
(sub-agents) so they share the same tool surface and guidance.

Delegate tools (``DelegateToAgent`` — which also fans out via its ``tasks``
arg — and ``DelegateToAgentBackground``) are intentionally NOT registered here
— they're main-agent-only and sub-agents filter them out via
``zrb_is_delegate_tool``. Tool policies, argument
formatters, and response handlers are also out of scope: those live on
``LLMChatTask`` and propagate to sub-agents at runtime via the
``current_tool_confirmation`` ContextVar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

from zrb.config.config import CFG
from zrb.llm.prompt.tool_guidance import (
    ToolGuidance,
    get_parallel_tool_call_section,
)
from zrb.llm.util.git import is_inside_git_dir
from zrb.util.string.conversion import to_boolean

# NOTE: `zrb.llm.tool` and `zrb.llm.lsp.tools` are imported lazily inside
# ``apply_common_tools``. Reason: ``zrb.llm.tool/__init__.py`` loads
# ``delegate.py``, which imports ``SubAgentManager`` from
# ``zrb.llm.agent.subagent.manager.manager``. If this module is loaded
# before ``manager.py`` (e.g. via ``builtin/llm/chat.py``), the
# ``manager.py`` bottom-imports ``default_tools.py`` which re-enters
# ``apply_common_tools`` while this module is still mid-load — causing an
# ImportError on ``apply_common_tools``. Keeping the heavy imports inside
# the function defers them until ``apply_common_tools`` is actually
# called, by which point all the cycle's modules are fully loaded.

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext


@runtime_checkable
class CommonToolHost(Protocol):
    """Minimal interface needed by ``apply_common_tools``.

    Satisfied by ``LLMChatTask``, ``LLMTask``, and ``SubAgentManager``.
    """

    def add_tool(self, *tool: Callable) -> None: ...
    def add_tool_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...
    def add_toolset_factory(self, *factory: "Callable[[AnyContext], Any]") -> None: ...
    def add_tool_guidance(self, *guidance: ToolGuidance) -> None: ...
    def add_tool_guidance_factory(
        self, *factory: "Callable[[AnyContext], ToolGuidance]"
    ) -> None: ...
    def add_tool_guidance_section_factory(
        self, *factory: "Callable[[AnyContext, Any], str | None]"
    ) -> None: ...


# ── Static guidance ──────────────────────────────────────────────────────────
# Cross-tool decisions only. Per-tool intrinsics (argument behavior, output
# format, default values, irreversibility warnings) live in the tool docstrings,
# co-located with the schema the model fills in — which aids adherence and keeps
# this guide from restating them. Note that both are always-on: pydantic-ai
# serializes every registered tool's docstring + parameter schema into the
# request on every turn, so a docstring is NOT "lazy" context paid only when the
# model considers the tool — moving detail into a docstring relocates the token
# cost, it does not remove it. The real lever on tool-definition weight is the
# number of registered tools (hence the conditional registration of LSP and
# worktree tools in apply_common_tools below), not where the prose lives.
# Tool Usage Guide entries answer "when do I reach for THIS tool instead of
# THAT one?" — anything that doesn't reduce to a cross-tool choice belongs in
# the docstring.

_STATIC_TOOL_GUIDANCE: "list[ToolGuidance]" = [
    # File Operations
    ToolGuidance(
        group_name="File Operations",
        tool_name="LS",
        when_to_use="Exploring a directory without a known filename pattern",
        key_rule="For pattern-based discovery (e.g. `**/*.py`), use Glob. For content search, use Grep.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Glob",
        when_to_use="Finding files by name pattern",
        key_rule="For content search, use Grep. For an unfiltered directory listing, use LS.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Read",
        key_rule="Grep to locate the relevant section first; then Read to load it.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Write",
        key_rule="For surgical changes to an existing file, use Edit.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Edit",
        key_rule="Before editing a public symbol, Grep or LspFindReferences for call sites and update them in the same turn.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Grep",
        key_rule="For content search across files; to load a specific section, use Read.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="RM",
        when_to_use="Use instead of Bash rm",
        key_rule="Before removing, Grep for imports or references and update them in the same turn.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="MV",
        when_to_use="Use instead of Bash mv",
        key_rule="Before moving, Grep for imports or references that name the old path and update them.",
    ),
    # Execution
    ToolGuidance(
        group_name="Execution",
        tool_name="Shell",
        when_to_use="Running any shell command (Bash runs the same under bash)",
        key_rule="For file I/O, use Read/Write/Edit/Grep/RM/MV — not Shell. "
        "System Context already lists time, OS, CWD, and available tools — read from there before running commands to discover them. "
        "For long-running processes (dev servers, watchers, builds), pass background=True and poll with MonitorProcess instead of blocking.",
    ),
    ToolGuidance(
        group_name="Execution",
        tool_name="MonitorProcess",
        when_to_use="Check status of, wait on, or kill a background process "
        "started with Shell/Bash (background=True)",
        key_rule="Pass wait=N to block up to N seconds (returns early when the "
        "process exits) instead of busy-polling; kill=True terminates it.",
    ),
    # Analysis
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeCode",
        key_rule="Slow. Use Read + Grep first; AnalyzeFile for a single file; "
        "Glob or LS for a simple listing.",
    ),
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeFile",
        key_rule="Slow. Use Read for content; for directory-level analysis use AnalyzeCode.",
    ),
    # Research & Web
    ToolGuidance(
        group_name="Research & Web",
        tool_name="WebSearch",
        when_to_use="Current information, recent docs, or events",
        key_rule="Start broad with WebSearch, then WebFetch on the most promising URL.",
    ),
    ToolGuidance(
        group_name="Research & Web",
        tool_name="WebFetch",
        when_to_use="Fetching a known URL",
        key_rule="When the URL is not known, WebSearch first.",
    ),
    # User Interaction
    ToolGuidance(
        group_name="User Interaction",
        tool_name="AskUserQuestion",
        when_to_use="The choice is non-obvious AND the wrong pick would waste significant work — "
        "ambiguous library/strategy/file selection, or scope splits the user hasn't called.",
        key_rule="Do not ask for permission to do obvious things. Skip in non-interactive mode "
        "(System Context flags `Interactive: no`) — the tool short-circuits there anyway.",
    ),
    # Planning
    ToolGuidance(
        group_name="Planning",
        tool_name="TodoWrite",
        when_to_use="Starting work with ≥3 distinct steps, spanning multiple files, "
        "or expected to run across multiple turns — seed the full list before the "
        "first edit. Skip for single-step or one-line changes.",
        key_rule="Seed the full list up front; advance items by calling TodoWrite again with the updated list.",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="TodoRead",
        when_to_use="Resuming work, or after summarization may have dropped the "
        "plan — check the current list before proceeding",
    ),
    # Git Worktrees
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="ListWorktrees",
        when_to_use="Check before EnterWorktree to avoid duplicates",
    ),
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="EnterWorktree",
        when_to_use="Isolated branch for risky experiments, parallel "
        "approaches, or staging changes before merging",
        key_rule="ListWorktrees first. Pass the returned path as the `cwd` argument to Shell/Bash.",
    ),
    # Plan Mode
    ToolGuidance(
        group_name="Plan Mode",
        tool_name="EnterPlanMode",
        when_to_use=(
            "Before a risky or multi-file change, to investigate read-only "
            "first (edits/shell/delegation are blocked until you exit)"
        ),
        key_rule=(
            "Do discovery, then ExitPlanMode with a concrete plan. Skip plan "
            "mode when non-interactive (no user to approve): present the plan "
            "inline in your reply and proceed directly to the edits."
        ),
    ),
    ToolGuidance(
        group_name="Plan Mode",
        tool_name="ExitPlanMode",
        when_to_use="When discovery is done and you have a concrete change plan",
    ),
    # LSP
    ToolGuidance(
        group_name="LSP",
        tool_name="LspListServers",
        when_to_use="Verify an LSP server is running before reaching for other Lsp* tools",
        key_rule="If no servers are listed, fall back to Read + Grep.",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspFindReferences",
        when_to_use="Find all call sites before renaming, moving, or deleting a symbol",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspRenameSymbol",
        key_rule="Apply (`dry_run=False`) only after user approval; preview first (the default).",
    ),
]

# ── Dynamic guidance ─────────────────────────────────────────────────────────
# Factories so ``CFG.ROOT_GROUP_NAME`` is re-read at exec time (e.g. tool
# names change if the user customizes the root group). The delegate-tool
# guidance below is registered on every host, but only the main agent can
# actually call the delegate tools; sub-agents lack them, so the runtime
# ``tool_names`` filter drops the guidance for them.

_DYNAMIC_TOOL_GUIDANCE_FACTORIES: "list[Callable[[AnyContext], ToolGuidance]]" = [
    lambda ctx: ToolGuidance(
        group_name="Zrb Tasks",
        tool_name=f"List{CFG.ROOT_GROUP_NAME.capitalize()}Tasks",
        when_to_use=f"Before running a {CFG.ROOT_GROUP_NAME} task — confirm the task name exists",
    ),
    lambda ctx: ToolGuidance(
        group_name="Zrb Tasks",
        tool_name=f"Run{CFG.ROOT_GROUP_NAME.capitalize()}Task",
        when_to_use=f"Executing a registered {CFG.ROOT_GROUP_NAME} task",
        key_rule=f"Task names are case-sensitive. Verify with List{CFG.ROOT_GROUP_NAME.capitalize()}Tasks first.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="ActivateSkill",
        when_to_use="Loading domain-specific protocols for specialized work (see Skill Activation table)",
        key_rule="Re-activate after summarization if skill context was lost.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="DelegateToAgent",
        when_to_use="Delegate only when ALL apply: (a) the work needs >5 tool calls, "
        "(b) it spans >3 files OR requires speculative exploration, "
        "(c) you cannot already write the exact edits. "
        "Do the work yourself for ≤2 files, one-line changes, or any edit whose content you already know. "
        "To fan out, pass tasks=[{...}, ...] to run several concurrently in one call.",
        key_rule="deliverable and non_goals are the scope clamp — make them concrete; "
        "sub-agents over-produce against fuzzy specs. For fan-out, each task dict "
        "carries its own clamp and runs blind to the others.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="DelegateToAgentBackground",
        when_to_use="Long, independent work you do NOT need before continuing "
        "(e.g. speculative research, generating a file). To fan out, start "
        "several and collect the handles later.",
        key_rule="Same scope clamp as DelegateToAgent. Need the result now? "
        "Use DelegateToAgent (pass tasks=[...] to run several at once).",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="GetDelegationResult",
        when_to_use="Collect the result of a DelegateToAgentBackground handle",
        key_rule="Pass wait=N to block up to N seconds (returns early on finish) "
        "instead of busy-polling; kill=True stops the agent. The handle is "
        "consumed once a completed result is collected.",
    ),
]


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
        analyze_code,
        list_files,
        glob_files,
        read_file,
        write_file,
        replace_in_file,
        search_files,
        analyze_file,
        remove_file,
        move_file,
        search_journal,
        search_internet,
        open_web_page,
        *worktree_tools,
        *lsp_tools,
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
            [enter_plan_mode, exit_plan_mode] if _resolve_interactive(ctx) else []
        ),
        lambda ctx: [ask_user_question] if _resolve_interactive(ctx) else [],
    )
    host.add_tool_factory(
        lambda ctx: tag(create_list_zrb_task_tool(), Capability.READ),
        lambda ctx: tag(create_run_zrb_task_tool(), Capability.EXECUTE),
        lambda ctx: tag(create_activate_skill_tool(), Capability.META),
        lambda ctx: tag(create_monitor_process_tool(), Capability.EXECUTE),
    )
    host.add_toolset_factory(lambda ctx: load_mcp_config())
    host.add_tool_guidance(*_STATIC_TOOL_GUIDANCE)
    host.add_tool_guidance_factory(*_DYNAMIC_TOOL_GUIDANCE_FACTORIES)
    host.add_tool_guidance_section_factory(_parallel_tool_call_section_factory)


def _parallel_tool_call_section_factory(ctx: "AnyContext", model: Any) -> "str | None":
    """Emit the parallel-tool-call policy block, tone tuned to the model."""
    return get_parallel_tool_call_section(model)


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
