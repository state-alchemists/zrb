import os
import platform
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from zrb.attr.type import StrAttr, StrListAttr
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
from zrb.builtin.llm.xcom_names import (
    LLM_ASK_ERROR_XCOM_NAME,
    LLM_ASK_RESULT_XCOM_NAME,
    LLM_ASK_SESSION_XCOM_NAME,
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
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.prompt import (
    get_attachments,
)
from zrb.task.llm.subagent_conversation_history import (
    extract_subagent_conversation_history_from_ctx,
    inject_subagent_conversation_history_into_ctx,
)
from zrb.task.llm.workflow import (
    LLM_LOADED_WORKFLOW_XCOM_NAME,
    LLMWorkflow,
    get_available_workflows,
    load_workflow,
)
from zrb.task.llm_task import LLMTask
from zrb.util.attr import get_attr, get_str_list_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.file import read_file
from zrb.util.markdown import make_markdown_section
from zrb.util.string.conversion import to_boolean
from zrb.xcom.xcom import Xcom

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
    if isinstance(ctx.input.yolo, bool):
        return ctx.input.yolo
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
            "workflow",
            description="Workflows (comma separated)",
            prompt="Workflows (comma separated)",
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


def _get_llm_ask_system_prompt(ctx: AnyContext) -> str:
    system_prompt_attr = (
        None if ctx.input.system_prompt.strip() == "" else ctx.input.system_prompt
    )
    workflows_attr = (
        None if ctx.input.workflow.strip() == "" else ctx.input.workflow.split(",")
    )
    conversation_history = getattr(ctx, "conversation_history", ConversationHistory())

    persona = _get_persona(ctx)
    base_system_prompt = _get_base_system_prompt(ctx, system_prompt_attr)
    special_instruction_prompt = _get_special_instruction_prompt(ctx)
    project_instructions = _get_project_instructions()
    available_workflows = get_available_workflows()
    active_workflow_names = set(_get_active_workflow_names(ctx, workflows_attr, True))
    active_workflow_prompt = _get_workflow_prompt(
        available_workflows, active_workflow_names, True
    )
    inactive_workflow_prompt = _get_workflow_prompt(
        available_workflows, active_workflow_names, False
    )

    current_directory = os.getcwd()
    iso_date = datetime.now(timezone.utc).astimezone().isoformat()
    return "\n".join(
        [
            persona,
            base_system_prompt,
            make_markdown_section(
                "📝 SPECIAL INSTRUCTION",
                "\n".join(
                    [
                        special_instruction_prompt,
                        active_workflow_prompt,
                    ]
                ),
            ),
            make_markdown_section("📜 PROJECT INSTRUCTIONS", project_instructions),
            make_markdown_section("🛠️ AVAILABLE WORKFLOWS", inactive_workflow_prompt),
            make_markdown_section(
                "📚 CONTEXT",
                "\n".join(
                    [
                        make_markdown_section(
                            "ℹ️ System Information",
                            "\n".join(
                                [
                                    f"- OS: {platform.system()} {platform.version()}",
                                    f"- Python Version: {platform.python_version()}",
                                    f"- Current Directory: {current_directory}",
                                    f"- Current Time: {iso_date}",
                                ]
                            ),
                        ),
                        make_markdown_section(
                            "🧠 Long Term Note Content",
                            conversation_history.long_term_note,
                        ),
                        make_markdown_section(
                            "📝 Contextual Note Content",
                            conversation_history.contextual_note,
                        ),
                    ]
                ),
            ),
        ]
    )


def _get_project_instructions() -> str:
    instructions = []
    cwd = os.path.abspath(os.getcwd())
    home = os.path.abspath(os.path.expanduser("~"))
    search_dirs = []
    if cwd == home or cwd.startswith(os.path.join(home, "")):
        current_dir = cwd
        while True:
            search_dirs.append(current_dir)
            if current_dir == home:
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir
    else:
        search_dirs.append(cwd)
    for file_name in ["AGENTS.md", "CLAUDE.md"]:
        for dir_path in search_dirs:
            abs_file_name = os.path.join(dir_path, file_name)
            if os.path.isfile(abs_file_name):
                content = read_file(abs_file_name)
                instructions.append(
                    make_markdown_section(
                        f"Instruction from `{abs_file_name}`", content
                    )
                )
                break
    return "\n".join(instructions)


def _get_prompt_attr(
    ctx: AnyContext,
    attr: StrAttr | None,
    render: bool,
    default: str | None,
) -> str:
    """Generic helper to get a prompt attribute, prioritizing task-specific then default."""
    value = get_attr(
        ctx,
        attr,
        None,
        auto_render=render,
    )
    if value is not None:
        return value
    return default or ""


def _get_persona(
    ctx: AnyContext,
) -> str:
    return _get_prompt_attr(ctx, None, False, llm_config.default_persona)


def _get_base_system_prompt(
    ctx: AnyContext,
    system_prompt_attr: StrAttr | None,
) -> str:
    return _get_prompt_attr(
        ctx, system_prompt_attr, False, llm_config.default_system_prompt
    )


def _get_special_instruction_prompt(
    ctx: AnyContext,
) -> str:
    return _get_prompt_attr(
        ctx,
        None,
        False,
        llm_config.default_special_instruction_prompt,
    )


def _get_active_workflow_names(
    ctx: AnyContext,
    workflows_attr: StrListAttr | None,
    render_workflows: bool,
) -> list[str]:
    """Gets the workflows, prioritizing task-specific, then default."""
    raw_workflows = get_str_list_attr(
        ctx,
        [] if workflows_attr is None else workflows_attr,
        auto_render=render_workflows,
    )
    if raw_workflows is not None and len(raw_workflows) > 0:
        return [w.strip().lower() for w in raw_workflows if w.strip() != ""]
    return []


def _get_workflow_prompt(
    available_workflows: dict[str, LLMWorkflow],
    active_workflow_names: list[str] | set[str],
    select_active_workflow: bool,
) -> str:
    selected_workflows = {
        workflow_name: available_workflows[workflow_name]
        for workflow_name in available_workflows
        if (workflow_name in active_workflow_names) == select_active_workflow
    }
    return "\n".join(
        [
            make_markdown_section(
                workflow_name.capitalize(),
                (
                    (
                        "> Workflow status: Automatically Loaded/Activated.\n"
                        f"> Workflow location: `{workflow.path}`\n"
                        "{workflow.content}"
                    )
                    if select_active_workflow
                    else f"Workflow name: {workflow_name}\n{workflow.description}"
                ),
            )
            for workflow_name, workflow in selected_workflows.items()
        ]
    )


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
    system_prompt=_get_llm_ask_system_prompt,
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
            xcom_mapping={LLM_LOADED_WORKFLOW_XCOM_NAME: LLM_LOADED_WORKFLOW_XCOM_NAME},
            result_queue=LLM_ASK_RESULT_XCOM_NAME,
            error_queue=LLM_ASK_ERROR_XCOM_NAME,
            session_name_queue=LLM_ASK_SESSION_XCOM_NAME,
        ),
        retries=0,
        cli_only=True,
    ),
    alias="chat",
)
