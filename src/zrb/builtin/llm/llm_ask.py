from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.builtin.group import llm_group
from zrb.builtin.llm.chat_session import get_llm_ask_input_mapping, read_user_prompt
from zrb.builtin.llm.history import read_chat_conversation, write_chat_conversation
from zrb.builtin.llm.input import PreviousSessionInput
from zrb.builtin.llm.tool.api import get_current_location, get_current_weather
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.code import analyze_repo
from zrb.builtin.llm.tool.file import (
    analyze_file,
    list_files,
    read_from_file,
    read_many_files,
    replace_in_file,
    search_files,
    write_many_files,
    write_to_file,
)
from zrb.builtin.llm.tool.web import (
    create_search_internet_tool,
    open_web_page,
    search_arxiv,
    search_wikipedia,
)
from zrb.callback.callback import Callback
from zrb.config.config import CFG
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.base_trigger import BaseTrigger
from zrb.task.llm_task import LLMTask
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from pydantic_ai import Tool

    ToolOrCallable = Tool | Callable


def _get_tool(ctx: AnyContext) -> list["ToolOrCallable"]:
    tools = []
    if CFG.LLM_ALLOW_ANALYZE_REPO:
        tools.append(analyze_repo)
    if CFG.LLM_ALLOW_ANALYZE_FILE:
        tools.append(analyze_file)
    if CFG.LLM_ALLOW_ACCESS_LOCAL_FILE:
        tools.append(search_files)
        tools.append(list_files)
        tools.append(read_from_file)
        tools.append(read_many_files)
        tools.append(replace_in_file)
        tools.append(write_to_file)
        tools.append(write_many_files)
    if CFG.LLM_ALLOW_ACCESS_SHELL:
        tools.append(run_shell_command)
    if CFG.LLM_ALLOW_OPEN_WEB_PAGE:
        tools.append(open_web_page)
    if CFG.LLM_ALLOW_SEARCH_WIKIPEDIA:
        tools.append(search_wikipedia)
    if CFG.LLM_ALLOW_SEARCH_ARXIV:
        tools.append(search_arxiv)
    if CFG.LLM_ALLOW_GET_CURRENT_LOCATION:
        tools.append(get_current_location)
    if CFG.LLM_ALLOW_GET_CURRENT_WEATHER:
        tools.append(get_current_weather)
    if CFG.SERPAPI_KEY != "" and CFG.LLM_ALLOW_SEARCH_INTERNET:
        tools.append(create_search_internet_tool(CFG.SERPAPI_KEY))
    return tools


def _get_default_yolo_mode(ctx: AnyContext) -> str:
    default_value = llm_config.default_yolo_mode
    if isinstance(default_value, list):
        return ",".join(default_value)
    return f"{default_value}"


def _render_yolo_mode_input(ctx: AnyContext) -> list[str] | bool | None:
    if ctx.input.yolo.strip() == "":
        return None
    elements = ctx.input.yolo.split(",")
    if len(elements) == 0:
        try:
            return to_boolean(elements[0])
        except Exception:
            pass
    return elements


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
    TextInput(
        "modes",
        description="Modes",
        prompt="Modes",
        default=lambda ctx: ",".join(llm_config.default_modes),
        allow_positional_parsing=False,
        always_prompt=False,
    ),
    BoolInput(
        "start-new",
        description="Start new session (LLM Agent will forget past conversation)",
        prompt="Start new session (LLM Agent will forget past conversation)",
        default=False,
        allow_positional_parsing=False,
        always_prompt=False,
    ),
    StrInput(
        "yolo",
        description="YOLO mode (LLM Agent will start in YOLO Mode)",
        prompt="YOLO mode (LLM Agent will start in YOLO Mode)",
        default=_get_default_yolo_mode,
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
        modes=lambda ctx: (
            None if ctx.input.modes.strip() == "" else ctx.input.modes.split(",")
        ),
        message="{ctx.input.message}",
        tools=_get_tool,
        yolo_mode=_render_yolo_mode_input,
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
            error_queue="ask_error",
            session_name_queue="ask_session_name",
        ),
        retries=0,
        cli_only=True,
    ),
    alias="chat",
)
