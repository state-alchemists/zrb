from pydantic_ai import Tool

from zrb.builtin.group import llm_group
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.agent.manager import sub_agent_manager
from zrb.llm.custom_command import get_skill_custom_command
from zrb.llm.history_processor.summarizer import create_summarizer_history_processor
from zrb.llm.note.manager import note_manager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.skill.manager import skill_manager
from zrb.llm.task.llm_chat_task import LLMChatTask
from zrb.llm.tool.delegate import create_delegate_to_agent_tool
from zrb.llm.tool.mcp import load_mcp_config
from zrb.llm.tool.registry import tool_registry
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool
from zrb.llm.tool_call import (
    auto_approve,
    replace_in_file_formatter,
    replace_in_file_response_handler,
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
    history_processors=[
        create_summarizer_history_processor(
            token_threshold=CFG.LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD,
            summary_window=CFG.LLM_HISTORY_SUMMARIZATION_WINDOW,
        )
    ],
    prompt_manager=PromptManager(
        assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
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
for name, func in tool_registry.get_all().items():
    if name == getattr(func, "__name__", None):
        llm_chat.add_tool(func)
    else:
        # It's an alias, wrap it in a Tool with the alias name
        llm_chat.add_tool(Tool(func, name=name))
llm_chat.add_tool_factory(
    lambda ctx: create_list_zrb_task_tool(),
    lambda ctx: create_run_zrb_task_tool(),
    lambda ctx: create_activate_skill_tool(),
    lambda ctx: create_delegate_to_agent_tool(),
)
llm_chat.add_argument_formatter(
    replace_in_file_formatter, write_file_formatter, write_files_formatter
)
import os

llm_chat.add_custom_command(get_skill_custom_command(skill_manager))


def _is_path_inside_cwd(path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        cwd = os.getcwd()
        return abs_path == cwd or abs_path.startswith(cwd + os.sep)
    except Exception:
        return False


def _approve_if_path_inside_cwd(args: dict[str, any]) -> bool:
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
