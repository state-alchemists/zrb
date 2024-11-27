from zrb.builtin.group import llm_group
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.web import open_web_page, query_internet
from zrb.config import (
    LLM_ALLOW_ACCESS_SHELL,
    LLM_ALLOW_ACCESS_WEB,
    LLM_HISTORY_FILE,
    LLM_MODEL,
    LLM_SYSTEM_PROMPT,
)
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.llm_task import LLMTask

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
        history_file=LLM_HISTORY_FILE,
        description="Chat with LLM",
        model="{ctx.input.model}",
        system_prompt="{ctx.input['system-prompt']}",
        message="{ctx.input.message}",
    ),
    alias="chat",
)

if LLM_ALLOW_ACCESS_SHELL:
    llm_chat.add_tool(run_shell_command)

if LLM_ALLOW_ACCESS_WEB:
    llm_chat.add_tool(open_web_page)
    llm_chat.add_tool(query_internet)
