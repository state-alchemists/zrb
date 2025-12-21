import os
import platform
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from zrb.attr.type import StrAttr, StrListAttr
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.workflow import LLMWorkflow, get_available_workflows
from zrb.util.attr import get_attr, get_str_attr, get_str_list_attr
from zrb.util.file import read_dir, read_file_with_line_numbers
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


def get_system_and_user_prompt(
    ctx: AnyContext,
    user_message: str,
    persona_attr: StrAttr | None = None,
    render_persona: bool = False,
    system_prompt_attr: StrAttr | None = None,
    render_system_prompt: bool = False,
    special_instruction_prompt_attr: StrAttr | None = None,
    render_special_instruction_prompt: bool = False,
    workflows_attr: StrListAttr | None = None,
    render_workflows: bool = False,
    conversation_history: ConversationHistory | None = None,
) -> tuple[str, str]:
    if conversation_history is None:
        conversation_history = ConversationHistory()
    new_user_message_prompt, apendixes = _get_user_message_prompt(user_message)
    new_system_prompt = _construct_system_prompt(
        ctx=ctx,
        user_message=user_message,
        apendixes=apendixes,
        persona_attr=persona_attr,
        render_persona=render_persona,
        system_prompt_attr=system_prompt_attr,
        render_system_prompt=render_system_prompt,
        special_instruction_prompt_attr=special_instruction_prompt_attr,
        render_special_instruction_prompt=render_special_instruction_prompt,
        workflows_attr=workflows_attr,
        render_workflows=render_workflows,
        conversation_history=conversation_history,
    )
    return new_system_prompt, new_user_message_prompt


def _construct_system_prompt(
    ctx: AnyContext,
    user_message: str,
    apendixes: str,
    persona_attr: StrAttr | None = None,
    render_persona: bool = False,
    system_prompt_attr: StrAttr | None = None,
    render_system_prompt: bool = False,
    special_instruction_prompt_attr: StrAttr | None = None,
    render_special_instruction_prompt: bool = False,
    workflows_attr: StrListAttr | None = None,
    render_workflows: bool = False,
    conversation_history: ConversationHistory | None = None,
) -> str:
    persona = _get_persona(ctx, persona_attr, render_persona)
    base_system_prompt = _get_base_system_prompt(
        ctx, system_prompt_attr, render_system_prompt
    )
    special_instruction_prompt = _get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr, render_special_instruction_prompt
    )
    available_workflows = get_available_workflows()
    active_workflow_names = set(
        _get_active_workflow_names(ctx, workflows_attr, render_workflows)
    )
    active_workflow_prompt = _get_workflow_prompt(
        available_workflows, active_workflow_names, True
    )
    inactive_workflow_prompt = _get_workflow_prompt(
        available_workflows, active_workflow_names, False
    )
    if conversation_history is None:
        conversation_history = ConversationHistory()
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
                        make_markdown_section(
                            "📄 Apendixes",
                            apendixes,
                        ),
                    ]
                ),
            ),
        ]
    )


def _get_persona(
    ctx: AnyContext,
    persona_attr: StrAttr | None,
    render_persona: bool,
) -> str:
    """Gets the persona, prioritizing task-specific, then default."""
    persona = get_attr(
        ctx,
        persona_attr,
        None,
        auto_render=render_persona,
    )
    if persona is not None:
        return persona
    return llm_config.default_persona or ""


def _get_base_system_prompt(
    ctx: AnyContext,
    system_prompt_attr: StrAttr | None,
    render_system_prompt: bool,
) -> str:
    """Gets the base system prompt, prioritizing task-specific, then default."""
    system_prompt = get_attr(
        ctx,
        system_prompt_attr,
        None,
        auto_render=render_system_prompt,
    )
    if system_prompt is not None:
        return system_prompt
    return llm_config.default_system_prompt or ""


def _get_special_instruction_prompt(
    ctx: AnyContext,
    special_instruction_prompt_attr: StrAttr | None,
    render_spcecial_instruction_prompt: bool,
) -> str:
    """Gets the special instruction prompt, prioritizing task-specific, then default."""
    special_instruction = get_attr(
        ctx,
        special_instruction_prompt_attr,
        None,
        auto_render=render_spcecial_instruction_prompt,
    )
    if special_instruction is not None:
        return special_instruction
    return llm_config.default_special_instruction_prompt


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


def _get_user_message_prompt(user_message: str) -> tuple[str, str]:
    processed_user_message = user_message
    # Match “@” + any non-space/comma sequence that contains at least one “/”
    pattern = r"(?<!\w)@(?=[^,\s]*\/)([^,\?\!\s]+)"
    potential_resource_path = re.findall(pattern, user_message)
    apendix_list = []
    for i, ref in enumerate(potential_resource_path):
        resource_path = os.path.abspath(os.path.expanduser(ref))
        content = ""
        ref_type = ""
        if os.path.isfile(resource_path):
            content = read_file_with_line_numbers(resource_path)
            ref_type = "file"
        elif os.path.isdir(resource_path):
            content = read_dir(resource_path)
            ref_type = "directory"
        if content != "":
            # Replace the @-reference in the user message with the placeholder
            placeholder = f"[Reference {i+1}: `{os.path.basename(ref)}`]"
            processed_user_message = processed_user_message.replace(
                f"@{ref}", placeholder, 1
            )
            apendix_list.append(
                make_markdown_section(
                    f"Content of {placeholder} ({ref_type} path: `{resource_path}`)",
                    "\n".join(content) if isinstance(content, list) else content,
                    as_code=True,
                )
            )
    apendixes = "\n".join(apendix_list)
    current_directory = os.getcwd()
    iso_date = datetime.now(timezone.utc).astimezone().isoformat()
    modified_user_message = make_markdown_section(
        "User Request",
        "\n".join(
            [
                f"- Current Directory: {current_directory}",
                f"- Current Time: {iso_date}",
                "---",
                processed_user_message,
            ]
        ),
    )
    return modified_user_message, apendixes


def get_user_message(
    ctx: AnyContext,
    message_attr: StrAttr | None,
    render_user_message: bool,
) -> str:
    """Gets the user message, rendering and providing a default."""
    return get_str_attr(
        ctx, message_attr, "How are you?", auto_render=render_user_message
    )


def get_summarization_system_prompt(
    ctx: AnyContext,
    summarization_prompt_attr: StrAttr | None,
    render_summarization_prompt: bool,
) -> str:
    """Gets the summarization prompt, rendering if configured and handling defaults."""
    summarization_prompt = get_attr(
        ctx,
        summarization_prompt_attr,
        None,
        auto_render=render_summarization_prompt,
    )
    if summarization_prompt is not None:
        return summarization_prompt
    return llm_config.default_summarization_prompt


def get_attachments(
    ctx: AnyContext,
    attachment: "UserContent | list[UserContent] | Callable[[AnyContext], UserContent | list[UserContent]] | None" = None,  # noqa
) -> "list[UserContent]":
    if attachment is None:
        return []
    if callable(attachment):
        result = attachment(ctx)
        if result is None:
            return []
        if isinstance(result, list):
            return result
        return [result]
    if isinstance(attachment, list):
        return attachment
    return [attachment]
