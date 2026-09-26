import sys

from zrb.attr.tpl import Tpl
from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_tool_policy import (
    approve_if_mv_inside_journal_dir,
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
    approve_if_path_inside_skill_or_plugin_dir,
)
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.common_tools import apply_common_tools
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.profile import MINIMAL_PROFILE, active_profile
from zrb.llm.skill.manager import skill_manager
from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.tool.delegate import (
    create_delegate_to_agent_tool,
    create_search_agent_tool,
)
from zrb.llm.tool.delegate_background import (
    background_delegation_live_context,
    create_background_delegate_tool,
    create_get_delegation_result_tool,
)
from zrb.llm.tool_call import (
    auto_approve,
    read_file_validation_policy,
    replace_in_file_formatter,
    replace_in_file_response_handler,
    write_file_formatter,
)
from zrb.llm.tool_call.tool_policy.replace_in_file_validation import (
    replace_in_file_validation_policy,
)
from zrb.runner.cli import cli


def _get_message(ctx: AnyContext) -> str:
    """`--message`, else whatever was piped in (`echo "..." | zrb llm chat`)."""
    if ctx.input.message or ctx.is_tty or sys.stdin is None:
        return ctx.input.message
    return sys.stdin.read().strip()


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
            # Without a terminal there is nobody to answer the prompt.
            default=lambda ctx: ctx.is_tty,
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
    model=Tpl("{ctx.input.model}"),
    yolo=Tpl("{ctx.input.yolo}"),
    message=lambda ctx: _get_message(ctx),
    conversation_name=Tpl("{ctx.input.session}"),
    # Comma-separated file paths; normalized to BinaryContent in the agent
    # run path (prompt_content.normalize_attachments).
    attachment=lambda ctx: [
        path.strip() for path in ctx.input.attach.split(",") if path.strip()
    ],
    interactive=Tpl("{ctx.input.interactive}"),
    sandbox=lambda ctx: ctx.input.get("sandbox") or None,
    history_processors=[],
    prompt_manager=PromptManager(
        assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ),
)

# The zrb-shipped default tools. Storage-only: nothing resolves (and
# `pydantic_ai` does not load) until the first agent build.
# `sub_agent_manager` opts in the same way, so both share the tool surface.
apply_common_tools(llm_chat)


def _tool_factory(tool, defer_loading: bool = True):
    """Wrap a tool, optionally hiding its schema until searched for by name.

    Deferring removes the schema from every turn's token cost, not the model's
    knowledge that the tool exists — native tool search still surfaces the
    name on demand. ``DelegateToAgent`` is the exception that loads eagerly:
    its schema carries the sub-agent roster, and a model that has to search
    before it can see which agents exist mostly does not delegate at all.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import Tool

    return Tool(tool, defer_loading=defer_loading)


# Delegate tools, main agent only (sub-agents filter on
# `zrb_is_delegate_tool`). The `minimal` profile drops delegation (ADR-0049).
def _delegate_tool_factory(ctx):
    # Resolve from this run's model rather than CFG.LLM_MODEL: ``/model`` and
    # the task's ``model=`` override can select a small model while the global
    # default remains capable.
    if active_profile(llm_chat.get_model(ctx)) == MINIMAL_PROFILE:
        return []
    return [
        _tool_factory(create_delegate_to_agent_tool(), defer_loading=False),
        _tool_factory(create_search_agent_tool(), defer_loading=False),
        _tool_factory(create_background_delegate_tool()),
        _tool_factory(create_get_delegation_result_tool()),
    ]


llm_chat.append_tool_factory(_delegate_tool_factory)

# Notify the parent agent when one of its background delegations finishes,
# instead of leaving it to remember to poll GetDelegationResult.
llm_chat.prompt_manager.add_live_context(
    "background_delegations", background_delegation_live_context
)

# Add argument formatter (show arguments when asking for user confirmation)
llm_chat.prepend_argument_formatter(replace_in_file_formatter, write_file_formatter)

# Add response handler (update tool)
llm_chat.prepend_response_handler(replace_in_file_response_handler)

# Tool approval policies; sub-agents inherit them via the
# `current_tool_confirmation` ContextVar.
llm_chat.prepend_tool_policy(
    # bash_safe_command_policy is registered by apply_common_tools, alongside the
    # shell tools it guards.
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
    # Journal writers derive every path inside CFG.LLM_JOURNAL_DIR, so there
    # is nothing to adjudicate, and prompting would discourage recording.
    auto_approve("LogActivity"),
    auto_approve("WriteJournalNote"),
    auto_approve("WebSearch"),
    auto_approve("WebFetch"),
    auto_approve("ActivateSkill"),
    auto_approve("SearchSkill"),
    # AskUserQuestion auto-approves itself everywhere (ADR-0062).
    auto_approve("DelegateToAgent"),
    # Roster search is metadata — it finds delegation targets, it does not
    # delegate — so it prompts nothing; the sub-agent's own tool calls still
    # route their approvals to the user.
    auto_approve("SearchAgent"),
    # Starting a background delegation and polling its result are harmless; the
    # sub-agent's own tool calls still route their approvals to the user.
    auto_approve("DelegateToAgentBackground"),
    auto_approve("GetDelegationResult"),
    # EnterPlanMode only restricts the model further, safe to auto-approve.
    auto_approve("EnterPlanMode"),
    # ExitPlanMode is absent: PLAN_MODE_POLICY asks, so the user approves the
    # plan. MonitorProcess only polls/waits; kill still asks, and starting a
    # background command goes through Shell's policy.
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
    # LspRenameSymbol is deliberately absent: dry_run=False edits files.
    # Worktree tools - listing is safe; create/remove require approval
    auto_approve("ListWorktrees"),
)

# Add custom command (slash commands)
llm_chat.append_custom_command(get_skill_custom_command(skill_manager))

llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
