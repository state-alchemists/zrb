from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_tool_policy import (
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
)
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
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
    open_web_page,
    read_file,
    read_files,
    replace_in_file,
    run_shell_command,
    search_files,
    search_internet,
    update_todo,
    write_file,
    write_files,
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
    read_files_validation_policy,
    replace_in_file_formatter,
    replace_in_file_response_handler,
    replace_in_file_validation_policy,
    write_file_formatter,
    write_files_formatter,
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
    read_files,
    write_file,
    write_files,
    replace_in_file,
    search_files,
    analyze_file,
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
        when_to_use="Loading domain-specific protocols for specialized work",
        key_rule="Re-activate after long conversations if context feels lost. "
        "Activate core-coding for all coding tasks. "
        "Skills may include companion resources (scripts, docs, data) in their directory — "
        "use Glob to discover them or check the listing shown when activated.",
    ),
    lambda ctx: ToolGuidance(
        group_name="Delegation",
        tool_name="DelegateToAgent",
        when_to_use="A sub-task needs isolated context, produces heavy output, or requires independent verification. "
        "Do it yourself for single lookups, one-file edits, quick commands, or when the needed context is already loaded. "
        "Use DelegateToAgentsParallel instead when two or more such sub-tasks are independent of each other.",
        key_rule="Always give the sub-agent full context — it cannot see your conversation history.",
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
llm_chat.add_argument_formatter(
    replace_in_file_formatter, write_file_formatter, write_files_formatter
)

# Add response handler (update tool)
llm_chat.add_response_handler(replace_in_file_response_handler)

# Add tool policies (automatically approve/disprove tool calling)
llm_chat.add_tool_policy(
    bash_safe_command_policy(),
    replace_in_file_validation_policy,
    read_file_validation_policy,
    read_files_validation_policy,
    auto_approve("Read", approve_if_path_inside_cwd),
    auto_approve("Read", approve_if_path_inside_journal_dir),
    auto_approve("ReadMany", approve_if_path_inside_cwd),
    auto_approve("ReadMany", approve_if_path_inside_journal_dir),
    auto_approve("LS", approve_if_path_inside_cwd),
    auto_approve("LS", approve_if_path_inside_journal_dir),
    auto_approve("Glob", approve_if_path_inside_cwd),
    auto_approve("Glob", approve_if_path_inside_journal_dir),
    auto_approve("Grep", approve_if_path_inside_cwd),
    auto_approve("Grep", approve_if_path_inside_journal_dir),
    auto_approve("AnalyzeFile", approve_if_path_inside_cwd),
    auto_approve("AnalyzeFile", approve_if_path_inside_journal_dir),
    auto_approve("Write", approve_if_path_inside_journal_dir),
    auto_approve("WriteMany", approve_if_path_inside_journal_dir),
    auto_approve("Edit", approve_if_path_inside_journal_dir),
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

# File Operations
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="File Operations",
        tool_name="LS",
        when_to_use="Exploring a directory's structure without a specific filename pattern",
        key_rule="For pattern-based discovery (e.g., **/*.py), use Glob instead.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Glob",
        when_to_use="Finding files by name pattern (e.g., **/*.py, src/**/*.ts)",
        key_rule="For content search, use Grep. For unfiltered listing, use LS.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Read",
        key_rule="Content starts after ---CONTENT---. Everything above is metadata — NOT part of the file. "
        "Copy old_text for Edit from below ---CONTENT---. "
        "Use Grep first to locate the relevant section. For multiple files, use ReadMany.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Write",
        when_to_use="Creating new files or fully overwriting existing ones",
        key_rule="For surgical edits to an existing file, use Edit instead. "
        "For multiple files at once, use WriteMany. "
        "Large content: first chunk mode='w', subsequent chunks mode='a'.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Edit",
        key_rule="old_text must come from below ---CONTENT--- in Read output (not the header). "
        "Include 2-3 surrounding lines for uniqueness. "
        "If old_text matches multiple times, expand context or use count=1. "
        "For new files, use Write instead.",
    ),
    ToolGuidance(
        group_name="File Operations",
        tool_name="Grep",
        key_rule="Never use Grep output as Edit's old_text — lines truncate at 1000 chars; use Read first. "
        "Use files_only=True when you only need matching file paths (much smaller output). "
        "Use case_sensitive=False for case-insensitive search. "
        "Use context_lines=0 to suppress surrounding lines.",
    ),
)

# Execution
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="Execution",
        tool_name="Bash",
        when_to_use="System commands, package managers, test runners, and build tools",
        key_rule="Never use for file I/O — use Read/Write/Edit/Grep. "
        "Never use to query state already in System Context (Time, OS, CWD, available tools). "
        "Always pass non-interactive flags (-y, --yes, CI=true). "
        "Timeout 30s; timed-out processes may linger — check with ps aux | grep <name>. "
        "Batch independent commands with && to reduce round trips. "
        "Use cwd= when operating inside a worktree or a different project directory. "
        "Prefer CLI tools listed in System Context hints over their slower alternatives.",
    ),
)

# Analysis — LLM sub-agents, expensive
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeCode",
        when_to_use="Understanding an entire codebase's structure",
        key_rule="VERY SLOW. Use Read + Grep first. Only invoke when they are insufficient.",
    ),
    ToolGuidance(
        group_name="Analysis",
        tool_name="AnalyzeFile",
        when_to_use="Deep semantic understanding of a complex single file",
        key_rule="SLOW. Use Read for content retrieval. For directory-level analysis, use AnalyzeCode.",
    ),
)

# Research
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="Research & Web",
        tool_name="SearchInternet",
        when_to_use="Finding current information, documentation, or recent events",
        key_rule="Returns {query, results:[{title,url,snippet,source}], total, page, error}. "
        "Start broad, then OpenWebPage to fetch exact pages.",
    ),
    ToolGuidance(
        group_name="Research & Web",
        tool_name="OpenWebPage",
        when_to_use="Fetching content from a known URL",
        key_rule="For searching by query, use SearchInternet first to find URLs.",
    ),
)

# Planning — persistent across sessions
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="Planning",
        tool_name="WriteTodos",
        when_to_use="Creating a plan before starting a multi-step task",
        key_rule="Mark steps 'in_progress' before starting, 'completed' immediately after — don't batch updates.",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="GetTodos",
        when_to_use="Resuming work — check current plan at session start",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="UpdateTodo",
        key_rule="Update immediately on status change — don't batch at the end.",
    ),
    ToolGuidance(
        group_name="Planning",
        tool_name="ClearTodos",
        when_to_use="Discarding a completed or abandoned plan before starting a new one",
    ),
)

# Git Worktrees
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="ListWorktrees",
        when_to_use="Before creating or entering a worktree — avoid duplicates",
    ),
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="EnterWorktree",
        when_to_use="Creating an isolated branch for experimental or risky changes",
        key_rule="ListWorktrees first. Pass returned path as cwd to Bash commands.",
    ),
    ToolGuidance(
        group_name="Git Worktrees",
        tool_name="ExitWorktree",
        when_to_use="Finishing work in a worktree — always clean up",
        key_rule="Use keep_branch=True if you plan to merge later.",
    ),
)

# LSP
llm_chat.add_tool_guidance(
    ToolGuidance(
        group_name="LSP",
        tool_name="LspListServers",
        when_to_use="Before using any Lsp* tool — verify LSP is available",
        key_rule="If empty, fall back to Read/Grep.",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspFindDefinition",
        when_to_use="Jumping to the canonical definition of a symbol",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspFindReferences",
        when_to_use="Before renaming, moving, or deleting — find all call sites first",
    ),
    ToolGuidance(
        group_name="LSP",
        tool_name="LspRenameSymbol",
        when_to_use="Renaming a symbol safely across the codebase",
        key_rule="Use dry_run=True first. Apply only after user approval.",
    ),
)

# Add hook factories
# Journaling hook will check CFG.LLM_INCLUDE_JOURNAL at execution time
llm_chat.add_hook_factory(create_journaling_hook_factory())

llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
