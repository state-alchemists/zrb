from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_tool_policy import (
    approve_if_path_inside_cwd,
    approve_if_path_inside_journal_dir,
)
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.lsp.tools import create_lsp_tools
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.skill.manager import skill_manager
from zrb.llm.task.llm_chat_task import LLMChatTask
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
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool
from zrb.llm.tool_call import (
    auto_approve,
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
        BoolInput(
            "yolo", "YOLO Mode", default=False, allow_empty=True, always_prompt=False
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
    *lsp_tools,
    *plan_tools,
]
llm_chat.add_tool(*tools)

# Add tool factories
tool_factories = [
    lambda ctx: create_list_zrb_task_tool(),
    lambda ctx: create_run_zrb_task_tool(),
    lambda ctx: create_activate_skill_tool(),
    lambda ctx: create_delegate_to_agent_tool(),
    lambda ctx: create_parallel_delegate_tool(),
]
llm_chat.add_tool_factory(*tool_factories)

# Add argument formatter (show arguments when asking for user confirmation)
llm_chat.add_argument_formatter(
    replace_in_file_formatter, write_file_formatter, write_files_formatter
)

# Add response handler (update tool)
llm_chat.add_response_handler(replace_in_file_response_handler)

# Add tool policies (automatically approve/disprove tool calling)
llm_chat.add_tool_policy(
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
    auto_approve("ReadLongTermNote"),
    auto_approve("ReadContextualNote"),
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
)

# Add custom command (slash commands)
llm_chat.add_custom_command(get_skill_custom_command(skill_manager))

llm_group.add_task(llm_chat)
cli.add_task(llm_chat)
