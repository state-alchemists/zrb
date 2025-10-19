import os
import platform
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from zrb.attr.type import StrAttr, StrListAttr
from zrb.config.llm_config import llm_config
from zrb.config.llm_context.config import llm_context_config
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.util.attr import get_attr, get_str_attr, get_str_list_attr
from zrb.util.file import read_dir, read_file_with_line_numbers
from zrb.util.llm.prompt import make_prompt_section

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


def get_modes(
    ctx: AnyContext,
    modes_attr: StrListAttr | None,
    render_modes: bool,
) -> list[str]:
    """Gets the modes, prioritizing task-specific, then default."""
    raw_modes = get_str_list_attr(
        ctx,
        [] if modes_attr is None else modes_attr,
        auto_render=render_modes,
    )
    if raw_modes is None:
        raw_modes = []
    modes = [mode.strip().lower() for mode in raw_modes if mode.strip() != ""]
    if len(modes) > 0:
        return modes
    return llm_config.default_modes or []


def get_project_context_prompt() -> str:
    context_dict = llm_context_config.get_contexts()
    context_prompts = []
    for context_path, context in context_dict.items():
        context_prompts.append(
            make_prompt_section(header=f"Context at `{context_path}`", content=context)
        )
    return "\n".join(context_prompts)


def get_workflow_prompt(
    ctx: AnyContext,
    modes_attr: StrListAttr | None,
    render_modes: bool,
) -> str:
    builtin_workflow_dir = os.path.join(os.path.dirname(__file__), "default_workflow")
    modes = set(get_modes(ctx, modes_attr, render_modes))

    # Get user-defined workflows
    workflows = {
        workflow_name.strip().lower(): content
        for workflow_name, content in llm_context_config.get_workflows().items()
        if workflow_name.strip().lower() in modes
    }

    # Get available builtin workflow names from the file system
    available_builtin_workflow_names = set()
    try:
        for filename in os.listdir(builtin_workflow_dir):
            if filename.endswith(".md"):
                available_builtin_workflow_names.add(filename[:-3].lower())
    except FileNotFoundError:
        # Handle case where the directory might not exist
        ctx.log_error(
            f"Warning: Default workflow directory not found at {builtin_workflow_dir}"
        )
    except Exception as e:
        # Catch other potential errors during directory listing
        ctx.log_error(f"Error listing default workflows: {e}")

    # Determine which builtin workflows are requested and not already loaded
    requested_builtin_workflow_names = [
        workflow_name
        for workflow_name in available_builtin_workflow_names
        if workflow_name in modes and workflow_name not in workflows
    ]

    # Add builtin-workflows if requested
    if len(requested_builtin_workflow_names) > 0:
        for workflow_name in requested_builtin_workflow_names:
            workflow_file_path = os.path.join(
                builtin_workflow_dir, f"{workflow_name}.md"
            )
            try:
                with open(workflow_file_path, "r") as f:
                    workflows[workflow_name] = f.read()
            except FileNotFoundError:
                ctx.log_error(
                    f"Warning: Builtin workflow file not found: {workflow_file_path}"
                )
            except Exception as e:
                ctx.log_error(f"Error reading builtin workflow {workflow_name}: {e}")

    return "\n".join(
        [
            make_prompt_section(header.capitalize(), content)
            for header, content in workflows.items()
            if header.lower() in modes
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
    modes_attr: StrListAttr | None = None,
    render_modes: bool = False,
    conversation_history: ConversationHistory | None = None,
) -> tuple[str, str]:
    if conversation_history is None:
        conversation_history = ConversationHistory()
    modified_user_message, user_message_context = _extract_user_prompt_components(
        user_message
    )
    new_system_prompt = _construct_system_prompt(
        ctx=ctx,
        persona_attr=persona_attr,
        render_persona=render_persona,
        system_prompt_attr=system_prompt_attr,
        render_system_prompt=render_system_prompt,
        special_instruction_prompt_attr=special_instruction_prompt_attr,
        render_special_instruction_prompt=render_special_instruction_prompt,
        modes_attr=modes_attr,
        render_modes=render_modes,
        conversation_history=conversation_history,
    )
    user_message_context["Token Counter"] = _get_token_usage_info(
        new_system_prompt, user_message, conversation_history
    )
    return new_system_prompt, _contruct_user_message_prompt(
        modified_user_message, user_message_context
    )


def _construct_system_prompt(
    ctx: AnyContext,
    persona_attr: StrAttr | None = None,
    render_persona: bool = False,
    system_prompt_attr: StrAttr | None = None,
    render_system_prompt: bool = False,
    special_instruction_prompt_attr: StrAttr | None = None,
    render_special_instruction_prompt: bool = False,
    modes_attr: StrListAttr | None = None,
    render_modes: bool = False,
    conversation_history: ConversationHistory | None = None,
) -> str:
    persona = get_persona(ctx, persona_attr, render_persona)
    base_system_prompt = get_base_system_prompt(
        ctx, system_prompt_attr, render_system_prompt
    )
    special_instruction_prompt = get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr, render_special_instruction_prompt
    )
    workflow_prompt = get_workflow_prompt(ctx, modes_attr, render_modes)
    project_context_prompt = get_project_context_prompt()
    if conversation_history is None:
        conversation_history = ConversationHistory()
    current_directory = os.getcwd()
    directory_tree = _generate_directory_tree(current_directory, max_depth=2)
    return "\n".join(
        [
            make_prompt_section("Persona", persona),
            make_prompt_section("System Prompt", base_system_prompt),
            make_prompt_section("Special Instruction", special_instruction_prompt),
            make_prompt_section("Special Workflows", workflow_prompt),
            make_prompt_section(
                "Past Conversation",
                "\n".join(
                    [
                        make_prompt_section(
                            "Summary",
                            conversation_history.past_conversation_summary,
                            as_code=True,
                        ),
                        make_prompt_section(
                            "Last Transcript",
                            conversation_history.past_conversation_transcript,
                            as_code=True,
                        ),
                    ]
                ),
            ),
            make_prompt_section(
                "Notes",
                "\n".join(
                    [
                        make_prompt_section(
                            "Long Term",
                            conversation_history.long_term_note,
                            as_code=True,
                        ),
                        make_prompt_section(
                            "Contextual",
                            conversation_history.contextual_note,
                            as_code=True,
                        ),
                    ]
                ),
            ),
            make_prompt_section("Project Context", project_context_prompt),
            make_prompt_section(
                "Conversation Environment",
                "\n".join(
                    [
                        make_prompt_section("Current OS", platform.system()),
                        make_prompt_section("OS Version", platform.version()),
                        make_prompt_section(
                            "Python Version", platform.python_version()
                        ),
                        make_prompt_section(
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
            make_prompt_section("User Message", modified_user_message),
            make_prompt_section(
                "Context",
                "\n".join(
                    [
                        make_prompt_section(key, val)
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

        for i, entry in enumerate(entries):
            if i >= max_children:
                tree_lines.append(f"{prefix}└─... (more)")
                break
            is_last = i == len(entries) - 1
            connector = "└─" if is_last else "├─"
            tree_lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                new_prefix = prefix + ("  " if is_last else "│ ")
                recurse(entry.path, depth + 1, new_prefix)

    tree_lines.append(os.path.basename(dir_path))
    recurse(dir_path, 1, "")
    return "\n".join(tree_lines)


def _get_token_usage_info(
    system_prompt: str, user_message: str, conversation_history: ConversationHistory
) -> str:
    system_prompt_token_count = llm_rate_limitter.count_token(system_prompt)
    user_message_token_count = llm_rate_limitter.count_token(user_message)
    conversation_history_token_count = llm_rate_limitter.count_token(
        conversation_history.history
    )
    total_token_count = (
        system_prompt_token_count
        + user_message_token_count
        + conversation_history_token_count
    )
    max_token = llm_rate_limitter.max_tokens_per_request
    return f"{total_token_count} tokens of {max_token} tokens"


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
            placeholder = f"[Reference {i+1}: {os.path.basename(ref)}]"
            modified_user_message = modified_user_message.replace(
                f"@{ref}", placeholder, 1
            )
            apendixes.append(
                make_prompt_section(
                    f"{placeholder} ({ref_type} path: `{resource_path}`)",
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
    attachment: "UserContent | list[UserContent] | Callable[[AnySharedContext], UserContent | list[UserContent]] | None" = None,  # noqa
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
