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
from zrb.llm.common_tools import apply_common_tools
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.hook.journal import create_journaling_hook_factory
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.skill.manager import skill_manager
from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.tool.delegate import create_delegate_to_agent_tool
from zrb.llm.tool.delegate_background import (
    create_background_delegate_tool,
    create_get_delegation_result_tool,
)
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
        StrInput(
            "sandbox",
            "Sandbox Mode (true/false)",
            allow_empty=True,
            always_prompt=False,
        ),
    ],
    # fstring template (StrAttr); LLMChatTask.model omits bare str from its
    # annotation but renders it at run time via get_attr in _get_model.
    model="{ctx.input.model}",  # type: ignore[arg-type]
    yolo="{ctx.input.yolo}",
    message="{ctx.input.message}",
    conversation_name="{ctx.input.session}",
    interactive="{ctx.input.interactive}",
    sandbox=lambda ctx: ctx.input.get("sandbox") or None,
    history_processors=[],
    prompt_manager=PromptManager(
        assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ),
    ui_ascii_art=lambda ctx: CFG.LLM_ASSISTANT_ASCII_ART,
    ui_assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ui_greeting=lambda ctx: f"{CFG.LLM_ASSISTANT_NAME}\n{CFG.LLM_ASSISTANT_JARGON}",
    ui_jargon=lambda ctx: CFG.LLM_ASSISTANT_JARGON,
)

# Register zrb-shipped default tools, factories, and guidance. The same
# call is made on `sub_agent_manager` at the bottom of
# `zrb/llm/agent/subagent/manager/manager.py`, so the main agent and
# sub-agents share their tool surface and guidance.
apply_common_tools(llm_chat)

# Delegate tools — main agent only. Sub-agents filter these out via
# `zrb_is_delegate_tool` (see SubAgentManager.create_agent), but
# `apply_common_tools` already registered the matching tool guidance so
# the prompt mentions them in both places consistently.
llm_chat.add_tool_factory(
    lambda ctx: create_delegate_to_agent_tool(),
    lambda ctx: create_background_delegate_tool(),
    lambda ctx: create_get_delegation_result_tool(),
)

# Add argument formatter (show arguments when asking for user confirmation)
llm_chat.add_argument_formatter(replace_in_file_formatter, write_file_formatter)

# Add response handler (update tool)
llm_chat.add_response_handler(replace_in_file_response_handler)

# Add tool policies (automatically approve/disprove tool calling).
# These also propagate to sub-agent tool calls via the
# `current_tool_confirmation` ContextVar set by `run_agent` — see the
# `_confirm_tool_execution` chain in `zrb.llm.ui.base.ui`.
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
    auto_approve("WebSearch"),
    auto_approve("WebFetch"),
    auto_approve("ActivateSkill"),
    # AskUserQuestion is auto-approved intrinsically (it registers itself via
    # register_always_auto_approve in zrb.llm.tool.ask), so the cascade approves
    # it in every path — main agent, sub-agents, web — not just here. See
    # ADR-0062. No entry needed in this list.
    auto_approve("DelegateToAgent"),
    # Starting a background delegation and polling its result are harmless; the
    # sub-agent's own tool calls still route their approvals to the user.
    auto_approve("DelegateToAgentBackground"),
    auto_approve("GetDelegationResult"),
    # EnterPlanMode only restricts the model further, safe to auto-approve.
    auto_approve("EnterPlanMode"),
    # ExitPlanMode switches from PLAN to BUILD — requires user confirmation
    # via the permission policy (PLAN_MODE_POLICY sets it to ASK) so the user
    # must approve the plan before execution resumes.
    # MonitorProcess is read-only (poll/wait); kill still routes through the user.
    # Starting a background command goes through Shell/Bash (background=True), which
    # is gated by bash_safe_command_policy like any other shell call.
    auto_approve("MonitorProcess"),
    # LSP tools - read-only, safe to auto-approve
    auto_approve("LspFindDefinition"),
    auto_approve("LspFindReferences"),
    auto_approve("LspGetDiagnostics"),
    auto_approve("LspGetDocumentSymbols"),
    auto_approve("LspGetWorkspaceSymbols"),
    auto_approve("LspGetHoverInfo"),
    auto_approve("LspListServers"),
    # Planning tools - safe to auto-approve (just state management)
    auto_approve("TodoWrite"),
    auto_approve("TodoRead"),
    # Note: LspRenameSymbol uses dry_run by default, but requires user approval
    # when dry_run=False (actual file modifications)
    # Worktree tools - listing is safe; create/remove require approval
    auto_approve("ListWorktrees"),
)

# Add custom command (slash commands)
llm_chat.add_custom_command(get_skill_custom_command(skill_manager))

# Add hook factories
# Journaling hook will check CFG.LLM_INCLUDE_JOURNAL_REMINDER at execution time
llm_chat.add_hook_factory(create_journaling_hook_factory())

llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
