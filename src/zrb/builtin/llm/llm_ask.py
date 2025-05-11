from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_session import get_llm_ask_input_mapping, read_user_prompt
from zrb.builtin.llm.history import read_chat_conversation, write_chat_conversation
from zrb.builtin.llm.input import PreviousSessionInput
from zrb.builtin.llm.tool.api import get_current_location, get_current_weather
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.file import (
    apply_diff,
    list_files,
    read_from_file,
    search_files,
    write_to_file,
)
from zrb.builtin.llm.tool.web import (
    create_search_internet_tool,
    open_web_page,
    search_arxiv,
    search_wikipedia,
)
from zrb.callback.callback import Callback
from zrb.config import CFG
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.base_trigger import BaseTrigger
from zrb.task.llm_task import LLMTask

_llm_ask_inputs = [
    StrInput(
        "model",
        description="LLM Model",
        prompt="LLM Model",
        default="",
        allow_positional_parsing=False,
        always_prompt=False,
        allow_empty=True,
    ),
    StrInput(
        "base-url",
        description="LLM API Base URL",
        prompt="LLM API Base URL",
        default="",
        allow_positional_parsing=False,
        always_prompt=False,
        allow_empty=True,
    ),
    StrInput(
        "api-key",
        description="LLM API Key",
        prompt="LLM API Key",
        default="",
        allow_positional_parsing=False,
        always_prompt=False,
        allow_empty=True,
    ),
    TextInput(
        "system-prompt",
        description="System prompt",
        prompt="System prompt",
        default="",
        allow_positional_parsing=False,
        always_prompt=False,
    ),
    BoolInput(
        "start-new",
        description="Start new conversation (LLM will forget everything)",
        prompt="Start new conversation (LLM will forget everything)",
        default=False,
        allow_positional_parsing=False,
        always_prompt=False,
    ),
    TextInput("message", description="User message", prompt="Your message"),
    PreviousSessionInput(
        "previous-session",
        description="Previous conversation session",
        prompt="Previous conversation session (can be empty)",
        allow_positional_parsing=False,
        allow_empty=True,
        always_prompt=False,
    ),
]

llm_ask: LLMTask = llm_group.add_task(
    LLMTask(
        name="llm-ask",
        input=_llm_ask_inputs,
        description="❓ Ask LLM",
        model=lambda ctx: None if ctx.input.model.strip() == "" else ctx.input.model,
        model_base_url=lambda ctx: (
            None if ctx.input.base_url.strip() == "" else ctx.input.base_url
        ),
        model_api_key=lambda ctx: (
            None if ctx.input.api_key.strip() == "" else ctx.input.api_key
        ),
        conversation_history_reader=read_chat_conversation,
        conversation_history_writer=write_chat_conversation,
        system_prompt=lambda ctx: (
            None if ctx.input.system_prompt.strip() == "" else ctx.input.system_prompt
        ),
        message="{ctx.input.message}",
        retries=0,
    ),
    alias="ask",
)

llm_group.add_task(
    BaseTrigger(
        name="llm-chat",
        input=_llm_ask_inputs,
        description="💬 Chat with LLM",
        queue_name="ask_trigger",
        action=read_user_prompt,
        callback=Callback(
            task=llm_ask,
            input_mapping=get_llm_ask_input_mapping,
            result_queue="ask_result",
            session_name_queue="ask_session_name",
        ),
        retries=0,
        cli_only=True,
    ),
    alias="chat",
)

if CFG.LLM_ALLOW_ACCESS_LOCAL_FILE:
    llm_ask.add_tool(list_files)
    llm_ask.add_tool(read_from_file)
    llm_ask.add_tool(write_to_file)
    llm_ask.add_tool(search_files)
    llm_ask.add_tool(apply_diff)

if CFG.LLM_ALLOW_ACCESS_SHELL:
    llm_ask.add_tool(run_shell_command)

if CFG.LLM_ALLOW_ACCESS_INTERNET:
    llm_ask.add_tool(open_web_page)
    llm_ask.add_tool(search_wikipedia)
    llm_ask.add_tool(search_arxiv)
    if CFG.SERP_API_KEY != "":
        llm_ask.add_tool(create_search_internet_tool(CFG.SERP_API_KEY))
    llm_ask.add_tool(get_current_location)
    llm_ask.add_tool(get_current_weather)
