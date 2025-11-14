import os
import platform
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from zrb.attr.type import StrAttr, StrListAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_context.config import llm_context_config
from zrb.context.any_context import AnyContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.task.llm.workflow import get_available_workflows
from zrb.util.attr import get_attr, get_str_attr, get_str_list_attr
from zrb.util.file import read_dir, read_file_with_line_numbers
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


def get_persona(
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


def get_base_system_prompt(
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


def get_special_instruction_prompt(
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


def get_workflow_names(
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


def get_project_context_prompt() -> str:
    context_dict = llm_context_config.get_contexts()
    context_prompts = []
    for context_path, context in context_dict.items():
        context_prompts.append(
            make_markdown_section(
                header=f"Context at `{context_path}`", content=context
            )
        )
    return "\n".join(context_prompts)


def get_workflow_prompt(
    ctx: AnyContext,
    workflows_attr: StrListAttr | None,
    render_workflows: bool,
    user_message: str,
) -> str:
    available_workflows = get_available_workflows()
    active_workflow_names = set(
        get_workflow_names(ctx, workflows_attr, render_workflows)
    )
    active_workflow_prompts = []
    available_workflow_prompts = []
    for workflow_name, workflow in available_workflows.items():
        if workflow_name in active_workflow_names:
            active_workflow_prompts.append(
                make_markdown_section(
                    workflow.name.capitalize(),
                    "\n".join(
                        [
                            f"> Workflow Name: `{workflow.name}`",
                            f"> Workflow Location: `{workflow.path}`",
                            workflow.content,
                        ]
                    ),
                )
            )
            continue
        available_workflow_prompts.append(
            make_markdown_section(
                workflow.name.capitalize(),
                "\n".join(
                    [
                        f"> Workflow Name: `{workflow.name}`",
                        f"> Description: {workflow.description}",
                    ]
                ),
            )
        )
    if len(active_workflow_prompts) > 0:
        active_workflow_prompts = [
            "> These workflows are automatically loaded.",
        ] + active_workflow_prompts
    if len(available_workflow_prompts) > 0:
        available_workflow_prompts = [
            "> You should load the following workflows using `load_workflow` tool.",
        ] + available_workflow_prompts
    return "\n".join(
        [
            make_markdown_section(
                "Active Workflows", "\n".join(active_workflow_prompts)
            ),
            make_markdown_section(
                "Available Workflows", "\n".join(available_workflow_prompts)
            ),
        ]
    )


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
    modified_user_message, user_message_context = _extract_user_prompt_components(
        user_message
    )
    new_system_prompt = _construct_system_prompt(
        ctx=ctx,
        user_message=user_message,
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
    return new_system_prompt, _contruct_user_message_prompt(
        modified_user_message, user_message_context
    )


def _construct_system_prompt(
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
) -> str:
    persona = get_persona(ctx, persona_attr, render_persona)
    base_system_prompt = get_base_system_prompt(
        ctx, system_prompt_attr, render_system_prompt
    )
    special_instruction_prompt = get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr, render_special_instruction_prompt
    )
    workflow_prompt = get_workflow_prompt(
        ctx, workflows_attr, render_workflows, user_message
    )
    project_context_prompt = get_project_context_prompt()
    if conversation_history is None:
        conversation_history = ConversationHistory()
    current_directory = os.getcwd()
    directory_tree = _generate_directory_tree(current_directory, max_depth=2)
    return "\n".join(
        [
            make_markdown_section("Persona", persona),
            make_markdown_section("System Prompt", base_system_prompt),
            make_markdown_section("Special Instruction", special_instruction_prompt),
            make_markdown_section(
                "Workflows",
                "\n".join(
                    [
                        "**CRITICAL:** You MUST load all relevant workflows before starting any task execution. Failure to do so will result in incomplete or incorrect implementations.",  # noqa
                        workflow_prompt,
                    ]
                ),
            ),
            make_markdown_section(
                "Past Conversation",
                "\n".join(
                    [
                        make_markdown_section(
                            "Summary",
                            conversation_history.past_conversation_summary,
                            as_code=True,
                        ),
                        make_markdown_section(
                            "Last Transcript",
                            conversation_history.past_conversation_transcript,
                            as_code=True,
                        ),
                    ]
                ),
            ),
            make_markdown_section(
                "Notes",
                "\n".join(
                    [
                        make_markdown_section(
                            "Long Term",
                            conversation_history.long_term_note,
                            as_code=True,
                        ),
                        make_markdown_section(
                            "Contextual",
                            conversation_history.contextual_note,
                            as_code=True,
                        ),
                    ]
                ),
            ),
            make_markdown_section("Project Context", project_context_prompt),
            make_markdown_section(
                "Conversation Environment",
                "\n".join(
                    [
                        make_markdown_section(
                            "Current OS/Version",
                            f"{platform.system()} - {platform.version()}",
                        ),
                        make_markdown_section(
                            "Python Version", platform.python_version()
                        ),
                        make_markdown_section(
                            "Directory Tree (depth=2)", directory_tree, as_code=True
                        ),
                    ]
                ),
            ),
        ]
    )


def _contruct_user_message_prompt(
    modified_user_message: str, user_message_context: dict[str, str]
) -> str:
    return "\n".join(
        [
            make_markdown_section("User Message", modified_user_message),
            make_markdown_section(
                "Context",
                "\n".join(
                    [
                        make_markdown_section(key, val)
                        for key, val in user_message_context.items()
                    ]
                ),
            ),
        ]
    )


def _generate_directory_tree(
    dir_path: str,
    max_depth: int = 2,
    max_children: int = 10,
    include_hidden: bool = False,
) -> str:
    """
    Generates a string representation of a directory tree, pure Python.
    """
    tree_lines = []

    def recurse(path: str, depth: int, prefix: str):
        if depth > max_depth:
            return
        try:
            entries = sorted(
                [e for e in os.scandir(path)],
                key=lambda e: e.name,
            )
        except FileNotFoundError:
            return
        child_count = 0
        entry_count = len(entries)
        for i, entry in enumerate(entries):
            if not include_hidden and entry.name.startswith("."):
                continue
            if child_count >= max_children:
                tree_lines.append(f"{prefix}└─... (more)")
                break
            is_last = i == entry_count - 1
            connector = "└─" if is_last else "├─"
            tree_lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                new_prefix = prefix + ("  " if is_last else "│ ")
                recurse(entry.path, depth + 1, new_prefix)
            child_count += 1

    tree_lines.append(os.path.basename(dir_path))
    recurse(dir_path, 1, "")
    return "\n".join(tree_lines)


def _extract_user_prompt_components(user_message: str) -> tuple[str, dict[str, Any]]:
    modified_user_message = user_message
    # Match “@” + any non-space/comma sequence that contains at least one “/”
    pattern = r"(?<!\w)@(?=[^,\s]*\/)([^,\?\!\s]+)"
    potential_resource_path = re.findall(pattern, user_message)
    apendixes = []
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
            modified_user_message = modified_user_message.replace(
                f"@{ref}", placeholder, 1
            )
            apendixes.append(
                make_markdown_section(
                    f"Content of {placeholder} ({ref_type} path: `{resource_path}`)",
                    "\n".join(content) if isinstance(content, list) else content,
                    as_code=True,
                )
            )
    current_directory = os.getcwd()
    iso_date = datetime.now(timezone.utc).astimezone().isoformat()
    user_message_context = {
        "Current Working Directory": current_directory,
        "Current Time": iso_date,
        "Apendixes": "\n".join(apendixes),
    }
    return modified_user_message, user_message_context


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
