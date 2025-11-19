import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.builtin.group import llm_group
from zrb.builtin.llm.attachment import get_media_type
from zrb.builtin.llm.chat_session import get_llm_ask_input_mapping, read_user_prompt
from zrb.builtin.llm.history import read_chat_conversation, write_chat_conversation
from zrb.builtin.llm.input import PreviousSessionInput
from zrb.builtin.llm.tool.api import (
    create_get_current_location,
    create_get_current_weather,
)
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.code import analyze_repo
from zrb.builtin.llm.tool.file import (
    analyze_file,
    list_files,
    read_from_file,
    replace_in_file,
    search_files,
    write_to_file,
)
from zrb.builtin.llm.tool.note import (
    read_contextual_note,
    read_long_term_note,
    write_contextual_note,
    write_long_term_note,
)
from zrb.builtin.llm.tool.web import (
    create_search_internet_tool,
    open_web_page,
)
from zrb.callback.callback import Callback
from zrb.config.config import CFG
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.input.any_input import AnyInput
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.base_trigger import BaseTrigger
from zrb.task.llm_task import LLMTask
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from pydantic_ai import AbstractToolset, Tool, UserContent

    ToolOrCallable = Tool | Callable


def _get_toolset(ctx: AnyContext) -> list["AbstractToolset[None] | str"]:
    cwd = os.getcwd()
    toolsets = []
    for config_path in [
        os.path.join(cwd, "mcp_config.json"),
        os.path.join(cwd, "mcp-config.json"),
    ]:
        if os.path.isfile(config_path):
            toolsets.append(config_path)
    return toolsets


def _get_tool(ctx: AnyContext) -> list["ToolOrCallable"]:
    tools = [
        read_long_term_note,
        write_long_term_note,
        read_contextual_note,
        write_contextual_note,
    ]
    if CFG.LLM_ALLOW_ANALYZE_REPO:
        tools.append(analyze_repo)
    if CFG.LLM_ALLOW_ANALYZE_FILE:
        tools.append(analyze_file)
    if CFG.LLM_ALLOW_ACCESS_LOCAL_FILE:
        tools.append(search_files)
        tools.append(list_files)
        tools.append(read_from_file)
        tools.append(replace_in_file)
        tools.append(write_to_file)
    if CFG.LLM_ALLOW_ACCESS_SHELL:
        tools.append(run_shell_command)
    if CFG.LLM_ALLOW_OPEN_WEB_PAGE:
        tools.append(open_web_page)
    if CFG.LLM_ALLOW_GET_CURRENT_LOCATION:
        tools.append(create_get_current_location())
    if CFG.LLM_ALLOW_GET_CURRENT_WEATHER:
        tools.append(create_get_current_weather())
    if CFG.SERPAPI_KEY != "" and CFG.LLM_ALLOW_SEARCH_INTERNET:
        tools.append(create_search_internet_tool())
    return tools


def _get_default_yolo_mode(ctx: AnyContext) -> str:
    default_value = llm_config.default_yolo_mode
    if isinstance(default_value, list):
        return ",".join(default_value)
    return f"{default_value}"


def _render_yolo_mode_input(ctx: AnyContext) -> list[str] | bool:
    if ctx.input.yolo.strip() == "":
        return []
    elements = [element.strip() for element in ctx.input.yolo.split(",")]
    if len(elements) == 1:
        try:
            return to_boolean(elements[0])
        except Exception:
            pass
    return elements


def _render_attach_input(ctx: AnyContext) -> "list[UserContent]":
    from pathlib import Path

    from pydantic_ai import BinaryContent

    attachment_paths: list[str] = [
        attachment_path.strip()
        for attachment_path in ctx.input.attach.split(",")
        if attachment_path.strip() != ""
    ]
    if len(attachment_paths) == 0:
        return []
    attachments = []
    for attachment_path in attachment_paths:
        attachment_path = os.path.abspath(os.path.expanduser(attachment_path))
        media_type = get_media_type(attachment_path)
        if media_type is None:
            ctx.log_error(f"Cannot get media type of {attachment_path}")
            continue
        data = Path(attachment_path).read_bytes()
        attachments.append(BinaryContent(data, media_type=media_type))
    return attachments


def _get_inputs(require_message: bool = True) -> list[AnyInput | None]:
    return [
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
            "workflows",
            description="Workflows",
            prompt="Workflows",
            default=lambda ctx: ",".join(llm_config.default_workflows),
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
        TextInput(
            "message",
            description="User message",
            prompt="Your message",
            always_prompt=require_message,
            allow_empty=not require_message,
        ),
        StrInput(
            name="attach",
            description="Comma separated attachments",
            default="",
            allow_positional_parsing=False,
            always_prompt=False,
        ),
        PreviousSessionInput(
            "previous-session",
            description="Previous conversation session",
            prompt="Previous conversation session (can be empty)",
            allow_positional_parsing=False,
            allow_empty=True,
            always_prompt=False,
        ),
    ]


llm_ask = LLMTask(
    name="llm-ask",
    input=_get_inputs(True),
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
    workflows=lambda ctx: (
        None if ctx.input.workflows.strip() == "" else ctx.input.workflows.split(",")
    ),
    attachment=_render_attach_input,
    message="{ctx.input.message}",
    tools=_get_tool,
    toolsets=_get_toolset,
    yolo_mode=_render_yolo_mode_input,
    retries=0,
)
llm_group.add_task(llm_ask, alias="ask")

llm_group.add_task(
    BaseTrigger(
        name="llm-chat",
        input=_get_inputs(False),
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
