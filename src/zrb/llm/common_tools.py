"""Shared default-tool registration for zrb-shipped agents.

`apply_common_tools(host)` registers the standard zrb-shipped tools,
toolset factories, static tool guidance, dynamic guidance factories, and
the model-aware Tool Usage Guide section factory on any host that
conforms to ``CommonToolHost`` — used by both ``LLMChatTask`` (main
agent), ``LLMTask`` (programmatic agents), and ``SubAgentManager``
(sub-agents) so they share the same tool surface and guidance.

Delegate tools (``DelegateToAgent`` / ``DelegateToAgentsParallel``) are
intentionally NOT registered here — they're main-agent-only and sub-agents
filter them out via ``zrb_is_delegate_tool``. Tool policies, argument
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
# When to use a tool + non-obvious gotchas. Docstrings cover what tools do.
# Only include guidance that helps make better tool choices or prevents real
# mistakes.

_STATIC_TOOL_GUIDANCE: "list[ToolGuidance]" = [
    # File Operations
    ToolGuidance(
        group_name="File Operations",
        tool_name="LS",
        when_to_use="Exploring without a specific filename pattern",
        key_rule="For pattern-based discovery (e.g., **/*.py), use Glob instead.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Glob",
        when_to_use="Finding files by pattern",
        key_rule="For content search, use Grep. For unfiltered listing, use LS.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Read",
        key_rule="Content starts after ---CONTENT--- (metadata above is NOT the file). "
        "Copy old_text for Edit from below ---CONTENT---. "
        "Grep first to locate the relevant section before reading.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Write",
        key_rule="Prefer Edit for surgical changes to existing files. "
        "For existing files, read with Read first to confirm content before overwriting. "
        "Large content: first chunk mode='w', subsequent mode='a'.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Edit",
        key_rule="old_text from below ---CONTENT--- (not header). Include 2-3 surrounding lines for uniqueness. "
        "If multiple matches, expand context or use count=1. "
        "Before editing: Grep/LspFindReferences call sites and update them too.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Grep",
        key_rule="Never use Grep output as Edit old_text (1000-char truncation) — Read first. "
        "Use files_only=True for just file paths. "
        "Use case_sensitive=False, context_lines=0 as needed.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="RM",
        when_to_use="Prefer over Bash rm",
        key_rule="recursive=True is irreversible — confirm first. "
        "Check for imports/references with Grep before removing.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="MV",
        when_to_use="Prefer over Bash mv",
        key_rule="Creates missing parent dirs automatically. Check imports/references before moving.",
    ),
    # Execution
    ToolGuidance(
        group_name="Execution",
        tool_name="Bash",
        key_rule="NEVER use for file I/O - use Read/Write/Edit/Grep/RM/MV instead. "
        "Never use to query state already in System Context (time, OS, CWD, tools). "
        "Always pass non-interactive flags (-y, --yes, CI=true). "
        "Default timeout is 120s; timed-out processes may linger. "
        "Batch independent commands with &&. Use cwd= for worktrees. "
        "Prefer rg over grep, gh for GitHub, rtk to prefix verbose commands.",
    ),
    # Analysis
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeCode",
        key_rule="VERY SLOW. Use Read + Grep first. Only invoke when insufficient.",
    ),
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeFile",
        key_rule="SLOW. Use Read for content. For directory-level, use AnalyzeCode.",
    ),
    # Research & Web
    ToolGuidance(
        group_name="Research & Web",
        tool_name="SearchInternet",
        when_to_use="Current info, docs, recent events",
        key_rule="Start broad, then OpenWebPage for exact pages.",
    ),
    ToolGuidance(
        group_name="Research & Web",
        tool_name="OpenWebPage",
        when_to_use="Fetching a known URL",
        key_rule="Use SearchInternet first to find URLs.",
    ),
    # Planning
    ToolGuidance(
        group_name="Planning",
        tool_name="WriteTodos",
        when_to_use="Planning a multi-step task",
        key_rule="Mark 'in_progress' before starting, 'completed' immediately after — don't batch.",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="GetTodos",
        when_to_use="Resuming work — check current plan",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="UpdateTodo",
        key_rule="Update immediately on status change — don't batch.",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="ClearTodos",
        when_to_use="Discarding a completed/abandoned plan",
    ),
    # Git Worktrees
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="ListWorktrees",
        when_to_use="Check before creating/entering — avoid duplicates",
    ),
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="EnterWorktree",
        when_to_use="Isolated branch for experimental changes",
        key_rule="ListWorktrees first. Pass returned path as Bash cwd.",
    ),
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="ExitWorktree",
        when_to_use="Clean up after worktree work",
        key_rule="Use keep_branch=True if merging later.",
    ),
    # LSP
    ToolGuidance(
        group_name="LSP",
        tool_name="LspListServers",
        when_to_use="Verify LSP is available before using Lsp* tools",
        key_rule="If empty, fall back to Read/Grep.",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspFindReferences",
        when_to_use="Find all call sites before renaming, moving, or deleting",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspRenameSymbol",
        key_rule="Use dry_run=True first. Apply only after user approval.",
    ),
]

# ── Dynamic guidance ─────────────────────────────────────────────────────────
# Factories so ``CFG.ROOT_GROUP_NAME`` is re-read at exec time (e.g. tool
# names change if the user customizes the root group). DelegateToAgent
# guidance is registered on sub-agents too — even though they can't call
# the tool — so behavior matches pre-refactor.

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
        key_rule="Re-activate after long conversations or summarization if context feels lost. "
        "Skill directories may include companion resources (scripts, docs, data) — "
        "use Glob in the skill directory or check the listing shown when activated.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="DelegateToAgent",
        when_to_use="Batch repetitive tasks (>3 files), high-volume outputs (builds/verbose logs), or speculative 'trial and error' research. "
        "Do it yourself for single lookups, one-file edits, quick commands, or when the needed context is already loaded.",
        key_rule="Keep your main session history lean. Delegate heavy lifting. Always give the sub-agent full context — it cannot see your conversation history.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="DelegateToAgentsParallel",
        when_to_use="Two or more independent sub-tasks that do not depend on each other's output. "
        "Prefer this over sequential DelegateToAgent calls whenever tasks can run concurrently.",
        key_rule="Sub-tasks must share no state and must each receive full context — they cannot see your conversation history.",
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
    from zrb.llm.lsp.tools import create_lsp_tools
    from zrb.llm.tool.bash import run_shell_command
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
    from zrb.llm.tool.plan import clear_todos, get_todos, update_todo, write_todos
    from zrb.llm.tool.skill import create_activate_skill_tool
    from zrb.llm.tool.web import open_web_page, search_internet
    from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees
    from zrb.llm.tool.zrb_task import (
        create_list_zrb_task_tool,
        create_run_zrb_task_tool,
    )

    lsp_tools = create_lsp_tools()
    plan_tools = [write_todos, get_todos, update_todo, clear_todos]
    host.add_tool(
        run_shell_command,
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
        enter_worktree,
        exit_worktree,
        list_worktrees,
        *lsp_tools,
        *plan_tools,
    )
    host.add_tool_factory(
        lambda ctx: create_list_zrb_task_tool(),
        lambda ctx: create_run_zrb_task_tool(),
        lambda ctx: create_activate_skill_tool(),
    )
    host.add_toolset_factory(lambda ctx: load_mcp_config())
    host.add_tool_guidance(*_STATIC_TOOL_GUIDANCE)
    host.add_tool_guidance_factory(*_DYNAMIC_TOOL_GUIDANCE_FACTORIES)
    host.add_tool_guidance_section_factory(_parallel_tool_call_section_factory)


def _parallel_tool_call_section_factory(ctx: "AnyContext", model: Any) -> "str | None":
    """Emit the parallel-tool-call policy block, tone tuned to the model."""
    return get_parallel_tool_call_section(model)
