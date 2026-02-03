import os
from typing import Any

from zrb.builtin.group import llm_group
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.agent.manager import SubAgentManager
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.history_processor.summarizer import create_summarizer_history_processor
from zrb.llm.note.manager import NoteManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.skill.manager import SkillManager
from zrb.llm.task.llm_chat_task import LLMChatTask
from zrb.llm.tool.bash import run_shell_command
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.delegate import create_delegate_to_agent_tool
from zrb.llm.tool.file import (
    analyze_file,
    glob_files,
    list_files,
    read_file,
    read_files,
    replace_in_file,
    search_files,
    write_file,
    write_files,
)
from zrb.llm.tool.mcp import load_mcp_config
from zrb.llm.tool.note import create_note_tools
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.web import open_web_page, search_internet
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool
from zrb.llm.tool_call import (
    auto_approve,
    replace_in_file_formatter,
    replace_in_file_response_handler,
    write_file_formatter,
    write_files_formatter,
)
from zrb.runner.cli import cli

skill_manager = SkillManager()
note_manager = NoteManager()

# Define Tool Registry for Sub-Agents
TOOL_REGISTRY = {
    "run_shell_command": run_shell_command,
    "list_files": list_files,
    "glob_files": glob_files,
    "read_file": read_file,
    "read_files": read_files,
    "write_file": write_file,
    "write_files": write_files,
    "replace_in_file": replace_in_file,
    "search_files": search_files,
    "analyze_file": analyze_file,
    "analyze_code": analyze_code,
    "search_internet": search_internet,
    "open_web_page": open_web_page,
}

# Add Note tools to registry
note_tools_list = create_note_tools(note_manager)
for tool in note_tools_list:
    if hasattr(tool, "__name__"):
        TOOL_REGISTRY[tool.__name__] = tool

# Prevent subagent from calling other subagent
sub_agent_tool_registry = TOOL_REGISTRY.copy()
if "delegate_to_agent" in sub_agent_tool_registry:
    del sub_agent_tool_registry["delegate_to_agent"]

sub_agent_manager = SubAgentManager(tool_registry=sub_agent_tool_registry)

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
    history_processors=[
        create_summarizer_history_processor(
            token_threshold=CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD,
            summary_window=CFG.LLM_HISTORY_SUMMARIZATION_WINDOW,
        )
    ],
    prompt_manager=PromptManager(
        assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
        note_manager=note_manager,
        skill_manager=skill_manager,
    ),
    ui_ascii_art=lambda ctx: CFG.LLM_ASSISTANT_ASCII_ART,
    ui_assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ui_greeting=lambda ctx: f"{CFG.LLM_ASSISTANT_NAME}\n{CFG.LLM_ASSISTANT_JARGON}",
    ui_jargon=lambda ctx: CFG.LLM_ASSISTANT_JARGON,
)
llm_group.add_task(llm_chat)
cli.add_task(llm_chat)


llm_chat.add_response_handler(replace_in_file_response_handler)
llm_chat.add_toolset(*load_mcp_config())
llm_chat.add_tool(
    run_shell_command,
    list_files,
    glob_files,
    read_file,
    read_files,
    write_file,
    write_files,
    replace_in_file,
    search_files,
    analyze_file,
    analyze_code,
    search_internet,
    open_web_page,
    *create_note_tools(note_manager),
)
llm_chat.add_tool_factory(
    lambda ctx: create_list_zrb_task_tool(),
    lambda ctx: create_run_zrb_task_tool(),
    lambda ctx: create_activate_skill_tool(skill_manager),
    lambda ctx: create_delegate_to_agent_tool(sub_agent_manager),
)
llm_chat.add_argument_formatter(
    replace_in_file_formatter, write_file_formatter, write_files_formatter
)
llm_chat.add_custom_command(get_skill_custom_command(skill_manager))


def _is_path_inside_cwd(path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        cwd = os.getcwd()
        return abs_path == cwd or abs_path.startswith(cwd + os.sep)
    except Exception:
        return False


def _approve_if_path_inside_cwd(args: dict[str, Any]) -> bool:
    path = args.get("path")
    paths = args.get("paths")
    if path is not None:
        return _is_path_inside_cwd(str(path))
    if paths is not None:
        if isinstance(paths, list):
            return all(_is_path_inside_cwd(str(p)) for p in paths)
        return False
    return True


llm_chat.add_tool_policy(
    auto_approve("read_file", _approve_if_path_inside_cwd),
    auto_approve("read_files", _approve_if_path_inside_cwd),
    auto_approve("list_files", _approve_if_path_inside_cwd),
    auto_approve("glob_files", _approve_if_path_inside_cwd),
    auto_approve("search_files", _approve_if_path_inside_cwd),
    auto_approve("analyze_file", _approve_if_path_inside_cwd),
    auto_approve("search_internet"),
    auto_approve("open_web_page"),
    auto_approve("read_long_term_note"),
    auto_approve("read_contextual_note"),
    auto_approve("activate_skill"),
    auto_approve("delegate_to_agent"),
)
