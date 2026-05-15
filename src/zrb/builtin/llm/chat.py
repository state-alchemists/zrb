from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_tool_policy import (
    approve_if_mv_inside_journal_dir,
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
    approve_if_path_inside_skill_or_plugin_dir,
)
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.agent.subagent.manager import sub_agent_manager
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.hook.journal import create_journaling_hook_factory
from zrb.llm.lsp.tools import create_lsp_tools
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.tool_guidance import ToolGuidance
from zrb.llm.skill.manager import skill_manager
from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.tool import (
    analyze_code,
    analyze_file,
    clear_todos,
    get_todos,
    glob_files,
    list_files,
    move_file,
    open_web_page,
    read_file,
    remove_file,
    replace_in_file,
    run_shell_command,
    search_files,
    search_internet,
    search_journal,
    update_todo,
    write_file,
    write_todos,
)
from zrb.llm.tool.delegate import (
    create_delegate_to_agent_tool,
    create_parallel_delegate_tool,
)
from zrb.llm.tool.mcp import load_mcp_config
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.worktree import enter_worktree, exit_worktree, list_worktrees
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool
from zrb.llm.tool_call import (
    auto_approve,
    bash_safe_command_policy,
    read_file_validation_policy,
    replace_in_file_formatter,
    replace_in_file_response_handler,
    replace_in_file_validation_policy,
    write_file_formatter,
)
from zrb.runner.cli import cli

llm_chat = LLMChatTask(
    name="chat",
    description="🤖 Chat with your AI Assistant",
    input=[
        StrInput("message", "Message", allow_empty=True, always_prompt=False),
        StrInput("model", "Model", allow_empty=True, always_prompt=False),
        StrInput(
            "session", "Conversation Session", allow_empty=True, always_prompt=False
        ),
        StrInput(
            "yolo",
            "YOLO Mode (true/false or comma-separated tool names, e.g. Write,Edit)",
            default="",
            allow_empty=True,
            always_prompt=False,
        ),
        StrInput("attach", "Attachments", allow_empty=True, always_prompt=False),
        BoolInput(
            "interactive",
            "Interactive Mode",
            default=True,
            allow_empty=True,
            always_prompt=False,
        ),
    ],
    model="{ctx.input.model}",
    yolo="{ctx.input.yolo}",
    message="{ctx.input.message}",
    conversation_name="{ctx.input.session}",
    interactive="{ctx.input.interactive}",
    history_processors=[],
    prompt_manager=PromptManager(
        assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ),
    ui_ascii_art=lambda ctx: CFG.LLM_ASSISTANT_ASCII_ART,
    ui_assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ui_greeting=lambda ctx: f"{CFG.LLM_ASSISTANT_NAME}\n{CFG.LLM_ASSISTANT_JARGON}",
    ui_jargon=lambda ctx: CFG.LLM_ASSISTANT_JARGON,
)

# Add toolsets
llm_chat.add_toolset(*load_mcp_config())

# Add tools
lsp_tools = create_lsp_tools()
plan_tools = [write_todos, get_todos, update_todo, clear_todos]
tools = [
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
]
llm_chat.add_tool(*tools)

# Add tool factories
llm_chat.add_tool_factory(
    lambda ctx: create_list_zrb_task_tool(),
    lambda ctx: create_run_zrb_task_tool(),
    lambda ctx: create_activate_skill_tool(),
    lambda ctx: create_delegate_to_agent_tool(),
    lambda ctx: create_parallel_delegate_tool(),
)

# Register guidance for dynamically-named factory tools
# Each guidance factory returns a single ToolGuidance object
llm_chat.add_tool_guidance_factory(
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
)

# Add argument formatter (show arguments when asking for user confirmation)
llm_chat.add_argument_formatter(replace_in_file_formatter, write_file_formatter)

# Add response handler (update tool)
llm_chat.add_response_handler(replace_in_file_response_handler)

# Add tool policies (automatically approve/disprove tool calling)
llm_chat.add_tool_policy(
    bash_safe_command_policy(),
    replace_in_file_validation_policy,
    read_file_validation_policy,
    auto_approve("Read", approve_if_path_inside_cwd),
    auto_approve("Read", approve_if_path_inside_journal_dir),
    auto_approve("Read", approve_if_path_inside_skill_or_plugin_dir),
    auto_approve("LS", approve_if_path_inside_cwd),
    auto_approve("LS", approve_if_path_inside_journal_dir),
    auto_approve("LS", approve_if_path_inside_skill_or_plugin_dir),
    auto_approve("Glob", approve_if_path_inside_cwd),
    auto_approve("Glob", approve_if_path_inside_journal_dir),
    auto_approve("Glob", approve_if_path_inside_skill_or_plugin_dir),
    auto_approve("Grep", approve_if_path_inside_cwd),
    auto_approve("Grep", approve_if_path_inside_journal_dir),
    auto_approve("Grep", approve_if_path_inside_skill_or_plugin_dir),
    auto_approve("AnalyzeFile", approve_if_path_inside_cwd),
    auto_approve("AnalyzeFile", approve_if_path_inside_journal_dir),
    auto_approve("Write", approve_if_path_inside_journal_dir),
    auto_approve("Edit", approve_if_path_inside_journal_dir),
    auto_approve("RM", approve_if_path_inside_journal_dir),
    auto_approve("MV", approve_if_mv_inside_journal_dir),
    auto_approve("SearchJournal"),
    auto_approve("SearchInternet"),
    auto_approve("OpenWebPage"),
    auto_approve("ActivateSkill"),
    auto_approve("DelegateToAgent"),
    auto_approve("DelegateToAgentsParallel"),
    # LSP tools - read-only, safe to auto-approve
    auto_approve("LspFindDefinition"),
    auto_approve("LspFindReferences"),
    auto_approve("LspGetDiagnostics"),
    auto_approve("LspGetDocumentSymbols"),
    auto_approve("LspGetWorkspaceSymbols"),
    auto_approve("LspGetHoverInfo"),
    auto_approve("LspListServers"),
    # Planning tools - safe to auto-approve (just state management)
    auto_approve("WriteTodos"),
    auto_approve("GetTodos"),
    auto_approve("UpdateTodo"),
    auto_approve("ClearTodos"),
    # Note: LspRenameSymbol uses dry_run by default, but requires user approval
    # when dry_run=False (actual file modifications)
    # Worktree tools - listing is safe; create/remove require approval
    auto_approve("ListWorktrees"),
)

# Add custom command (slash commands)
llm_chat.add_custom_command(get_skill_custom_command(skill_manager))

# ── Tool guidance ─────────────────────────────────────────────────────────────
# When to use a tool + non-obvious gotchas. Docstrings cover what tools do.
# Only include guidance that helps make better tool choices or prevents real mistakes.
# Registered on both llm_chat (main agent) and sub_agent_manager (sub-agents).

_static_tool_guidance = [
    # File Operations — only non-obvious gotchas. Tool names say what they do.
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
        "Grep first to locate the relevant section before reading. "
        "When you need several files at once, issue parallel Read calls in a single turn.",
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
        key_rule="Never for file I/O — use Read/Write/Edit/Grep/RM/MV. "
        "Never use to query state already in System Context (time, OS, CWD, tools). "
        "Always pass non-interactive flags (-y, --yes, CI=true). "
        "Default timeout is 120s; timed-out processes may linger. "
        "Batch independent commands with &&. Use cwd= for worktrees. "
        "Prefer rg over grep, gh for GitHub, rtk to prefix verbose commands.",
    ),
    # Analysis — LLM sub-agents, expensive
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
    # Planning — persistent across sessions
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
llm_chat.add_tool_guidance(*_static_tool_guidance)
sub_agent_manager.add_tool_guidance(*_static_tool_guidance)

# Add hook factories
# Journaling hook will check CFG.LLM_INCLUDE_JOURNAL_REMINDER at execution time
llm_chat.add_hook_factory(create_journaling_hook_factory())

llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
