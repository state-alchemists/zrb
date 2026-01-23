from zrb.builtin.group import llm_group
from zrb.config.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.llm.tool_call.replace_confirmation import replace_confirmation
from zrb.llm.history_processor.summarizer import create_summarizer_history_processor
from zrb.llm.note.manager import NoteManager
from zrb.llm.prompt.claude_compatibility import (
    create_claude_compatibility_prompt,
)
from zrb.llm.prompt.compose import PromptManager, new_prompt
from zrb.llm.prompt.default import (
    get_mandate_prompt,
    get_persona_prompt,
)
from zrb.llm.prompt.note import create_note_prompt
from zrb.llm.prompt.system_context import system_context
from zrb.llm.prompt.zrb import create_zrb_prompt
from zrb.llm.skill.manager import SkillManager
from zrb.llm.task.llm_chat_task import LLMChatTask
from zrb.llm.tool.bash import run_shell_command
from zrb.llm.tool.code import analyze_code
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
from zrb.runner.cli import cli

skill_manager = SkillManager()
note_manager = NoteManager()

llm_chat = LLMChatTask(
    name="chat",
    description="🤖 Chat with your AI Assistant",
    input=[
        StrInput("message", "Message", allow_empty=True, always_prompt=False),
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
    prompt_manager=PromptManager(),
    ui_ascii_art=lambda ctx: CFG.LLM_ASSISTANT_ASCII_ART,
    ui_assistant_name=lambda ctx: CFG.LLM_ASSISTANT_NAME,
    ui_greeting=lambda ctx: f"{CFG.LLM_ASSISTANT_NAME}\n{CFG.LLM_ASSISTANT_JARGON}",
    ui_jargon=lambda ctx: CFG.LLM_ASSISTANT_JARGON,
)
llm_group.add_task(llm_chat)
cli.add_task(llm_chat)


llm_chat.prompt_manager.add_middleware(
    new_prompt(lambda: get_persona_prompt(CFG.LLM_ASSISTANT_NAME)),
    new_prompt(lambda: get_mandate_prompt()),
    system_context,
    create_note_prompt(note_manager),
    create_claude_compatibility_prompt(skill_manager),
    create_zrb_prompt(),
)
llm_chat.add_post_confirmation_middleware(replace_confirmation)
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
    create_list_zrb_task_tool(),
    create_run_zrb_task_tool(),
    create_activate_skill_tool(skill_manager),
    *create_note_tools(note_manager),
)
