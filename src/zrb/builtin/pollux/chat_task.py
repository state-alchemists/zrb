from pydantic_ai.toolsets import FunctionToolset

from zrb.builtin.pollux.prompt.claude_compatibility import (
    create_claude_compatibility_prompt,
)
from zrb.builtin.pollux.prompt.compose import PromptManager, new_prompt
from zrb.builtin.pollux.prompt.default import get_default_prompt
from zrb.builtin.pollux.prompt.system_context import system_context
from zrb.builtin.pollux.prompt.zrb import create_zrb_prompt
from zrb.builtin.pollux.skill.manager import SkillManager
from zrb.builtin.pollux.task.chat_task import LLMChatTask
from zrb.builtin.pollux.tool.bash import run_shell_command
from zrb.builtin.pollux.tool.file import (
    list_files,
    read_file,
    replace_in_file,
    write_file,
)
from zrb.builtin.pollux.tool.skill import create_activate_skill_tool
from zrb.builtin.pollux.tool.sub_agent import create_sub_agent_tool
from zrb.builtin.pollux.tool.web import open_web_page, search_internet
from zrb.builtin.pollux.tool.zrb_task import (
    create_list_zrb_task_tool,
    create_run_zrb_task_tool,
)
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.runner.cli import cli

ZARUBA_GREETING = """
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀
⠀⠀⠀⠀⢀⡴⣆⠀⠀⠀⠀⠀⣠⡀⠀⠀⠀⠀⠀⠀⣼⣿⡗⠀⠀⠀⠀
⠀⠀⠀⣠⠟⠀⠘⠷⠶⠶⠶⠾⠉⢳⡄⠀⠀⠀⠀⠀⣧⣿⠀⠀⠀⠀⠀
⠀⠀⣰⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣤⣤⣤⣤⣤⣿⢿⣄⠀⠀⠀⠀
⠀⠀⡇⠀⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣧⠀⠀⠀⠀⠀⠀⠙⣷⡴⠶⣦
⠀⠀⢱⡀⠀⠉⠉⠀⠀⠀⠀⠛⠃⠀⢠⡟⠂⠀⠀⢀⣀⣠⣤⠿⠞⠛⠋
⣠⠾⠋⠙⣶⣤⣤⣤⣤⣤⣀⣠⣤⣾⣿⠴⠶⠚⠋⠉⠁⠀⠀⠀⠀⠀⠀
⠛⠒⠛⠉⠉⠀⠀⠀⣴⠟⣣⡴⠛⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠛⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
"""

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
    ui_assistant_name="Zaruba",
    ui_greeting=ZARUBA_GREETING,
    ui_jargon="Nye nye nye",
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
