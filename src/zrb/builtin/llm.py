import subprocess

from zrb.builtin.group import llm_group
from zrb.config import LLM_MODEL, LLM_SYSTEM_PROMPT
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.llm_task import LLMTask


def run_shell_command(command: str) -> str:
    """Running a shell command"""
    output = subprocess.check_output(
        command, shell=True, stderr=subprocess.STDOUT, text=True
    )
    return output


llm_chat: LLMTask = llm_group.add_task(
    LLMTask(
        name="llm-chat",
        input=[
            StrInput(
                "model",
                description="LLM Model",
                prompt="LLM Model",
                default_str=LLM_MODEL,
            ),
            StrInput(
                "system-prompt",
                description="System prompt",
                prompt="System prompt",
                default_str=LLM_SYSTEM_PROMPT,
            ),
            TextInput("message", description="User message", prompt="Your message"),
        ],
        description="Chat with LLM",
        model="{ctx.input.model}",
        system_prompt="{ctx.input['system-prompt']}",
        message="{ctx.input.message}",
    ),
    alias="chat",
)

llm_chat.add_tool(run_shell_command)
