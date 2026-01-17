from pydantic_ai.toolsets import FunctionToolset

from zrb.llm.app.confirmation.replace_confirmation import replace_confirmation
from zrb.util.ascii_art.banner import create_banner
from zrb.llm.prompt.claude_compatibility import (
    create_claude_compatibility_prompt,
)
from zrb.llm.prompt.compose import PromptManager, new_prompt
from zrb.llm.prompt.default import get_default_prompt
from zrb.llm.prompt.system_context import system_context
from zrb.llm.prompt.zrb import create_zrb_prompt
from zrb.llm.skill.manager import SkillManager
from zrb.llm.task.chat_task import LLMChatTask
from zrb.llm.tool.bash import run_shell_command
from zrb.llm.tool.file import (
    list_files,
    read_file,
    replace_in_file,
    write_file,
)
from zrb.llm.tool.skill import create_activate_skill_tool
from zrb.llm.tool.sub_agent import create_sub_agent_tool
from zrb.llm.tool.web import open_web_page, search_internet
from zrb.llm.tool.zrb_task import (
    create_list_zrb_task_tool,
    create_run_zrb_task_tool,
)
from zrb.config.config import CFG
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.runner.cli import cli


def _get_ui_greeting(ctx: AnySharedContext) -> str | None:
    assistant_name = _get_ui_assistant_name(ctx)
    jargon = _get_ui_jargon(ctx)
    return create_banner(text=f"{assistant_name}\n{jargon}")


def _get_ui_assistant_name(ctx: AnySharedContext) -> str:
    return CFG.ROOT_GROUP_NAME.capitalize()


def _get_ui_jargon(ctx: AnySharedContext) -> str | None:
    return CFG.ROOT_GROUP_DESCRIPTION


skill_manager = SkillManager()
chat_task = LLMChatTask(
    name="chat",
    description="AI Assistant",
    input=[
        StrInput("message", "Message", allow_empty=True, always_prompt=False),
        StrInput("session", "Conversation Session", allow_empty=True, always_prompt=False),
        BoolInput("yolo", "YOLO Mode", default=False, allow_empty=True, always_prompt=False),
        StrInput("attach", "Attachments", allow_empty=True, always_prompt=False),
    ],
    yolo="{ctx.input.yolo}",
    message="{ctx.input.message}",
    conversation_name="{ctx.input.session}",
    prompt_manager=PromptManager(),
    summarize_command=["/compact", "/compress"],
    ui_assistant_name=_get_ui_assistant_name,
    ui_greeting=_get_ui_greeting,
    ui_jargon=_get_ui_jargon,
)
cli.add_task(chat_task)


async def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    import asyncio
    import random

    await asyncio.sleep(3)
    return str(random.randint(1, 6))


async def get_current_time() -> str:
    """Get the current time."""
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


joke_agent = create_sub_agent_tool(
    name="joke_agent",
    description="Generates jokes about the current directory content.",
    system_prompt=(
        "You are a comedian. Use the 'run_shell_command' tool to list files "
        "(ls -la) and make a funny joke about the project structure."
    ),
    tools=[run_shell_command],
)

chat_task.prompt_manager.add_middleware(
    new_prompt(get_default_prompt("assistant")),
    system_context,
    create_claude_compatibility_prompt(skill_manager),
    create_zrb_prompt(),
)
chat_task.add_confirmation_middleware(replace_confirmation)
chat_task.add_tool(
    roll_dice,
    joke_agent,
    run_shell_command,
    list_files,
    read_file,
    write_file,
    replace_in_file,
    search_internet,
    open_web_page,
    create_list_zrb_task_tool(),
    create_run_zrb_task_tool(),
    create_activate_skill_tool(skill_manager),
)
chat_task.add_toolset(FunctionToolset(tools=[get_current_time]))
