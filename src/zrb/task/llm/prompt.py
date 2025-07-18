import os
import platform
import re
from datetime import datetime, timezone

from zrb.attr.type import StrAttr
from zrb.config.llm_config import llm_config as llm_config
from zrb.context.any_context import AnyContext
from zrb.task.llm.conversation_history_model import ConversationHistory
from zrb.util.attr import get_attr, get_str_attr
from zrb.util.file import read_dir, read_file_with_line_numbers
from zrb.util.llm.prompt import make_prompt_section


def get_persona(
    ctx: AnyContext,
    persona_attr: StrAttr | None,
) -> str:
    """Gets the persona, prioritizing task-specific, then default."""
    persona = get_attr(
        ctx,
        persona_attr,
        None,
        auto_render=False,
    )
    if persona is not None:
        return persona
    return llm_config.default_persona or ""


def get_base_system_prompt(
    ctx: AnyContext,
    system_prompt_attr: StrAttr | None,
) -> str:
    """Gets the base system prompt, prioritizing task-specific, then default."""
    system_prompt = get_attr(
        ctx,
        system_prompt_attr,
        None,
        auto_render=False,
    )
    if system_prompt is not None:
        return system_prompt
    return llm_config.default_system_prompt or ""


def get_special_instruction_prompt(
    ctx: AnyContext,
    special_instruction_prompt_attr: StrAttr | None,
) -> str:
    """Gets the special instruction prompt, prioritizing task-specific, then default."""
    special_instruction = get_attr(
        ctx,
        special_instruction_prompt_attr,
        None,
        auto_render=False,
    )
    if special_instruction is not None:
        return special_instruction
    return llm_config.default_special_instruction_prompt


def get_system_and_user_prompt(
    ctx: AnyContext,
    user_message: str,
    persona_attr: StrAttr | None = None,
    system_prompt_attr: StrAttr | None = None,
    special_instruction_prompt_attr: StrAttr | None = None,
    conversation_history: ConversationHistory | None = None,
) -> tuple[str, str]:
    """Combines persona, base system prompt, and special instructions."""
    persona = get_persona(ctx, persona_attr)
    base_system_prompt = get_base_system_prompt(ctx, system_prompt_attr)
    special_instruction = get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr
    )
    if conversation_history is None:
        conversation_history = ConversationHistory()
    conversation_context, new_user_message = extract_conversation_context(user_message)
    new_system_prompt = "\n".join(
        [
            make_prompt_section("Persona", persona),
            make_prompt_section("System Prompt", base_system_prompt),
            make_prompt_section("Special Instruction", special_instruction),
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
            make_prompt_section("Conversation Context", conversation_context),
        ]
    )
    return new_system_prompt, new_user_message


def extract_conversation_context(user_message: str) -> tuple[str, str]:
    modified_user_message = user_message
    # Match “@” + any non-space/comma sequence that contains at least one “/”
    pattern = r"(?<!\w)@(?=[^,\s]*/)([^,\s]+)"
    potential_resource_path = re.findall(pattern, user_message)
    apendixes = []
    for ref in potential_resource_path:
        resource_path = os.path.abspath(os.path.expanduser(ref))
        print("RESOURCE PATH", resource_path)
        if os.path.isfile(resource_path):
            content = read_file_with_line_numbers(resource_path)
            apendixes.append(
                make_prompt_section(
                    f"`{ref}` (file path: `{resource_path}`)", content, as_code=True
                )
            )
            # Remove the '@' from the modified user message for valid file paths
            modified_user_message = modified_user_message.replace(f"@{ref}", ref, 1)
        elif os.path.isdir(resource_path):
            content = read_dir(resource_path)
            apendixes.append(
                make_prompt_section(
                    f"`{ref}` (directory path: `{resource_path}`)",
                    content,
                    as_code=True,
                )
            )
            # Remove the '@' from the modified user message for valid directory paths
            modified_user_message = modified_user_message.replace(f"@{ref}", ref, 1)
    conversation_context = "\n".join(
        [
            make_prompt_section("Current OS", platform.system()),
            make_prompt_section("OS Version", platform.version()),
            make_prompt_section("Python Version", platform.python_version()),
            make_prompt_section("Apendixes", "\n".join(apendixes)),
        ]
    )
    iso_date = datetime.now(timezone.utc).astimezone().isoformat()
    current_directory = os.getcwd()
    modified_user_message = "\n".join(
        [
            make_prompt_section("User Message", modified_user_message),
            make_prompt_section(
                "Context",
                "\n".join(
                    [
                        make_prompt_section("Current working directory", current_directory),
                        make_prompt_section("Current time", iso_date),
                    ]
                )
            )
        ]
    )
    return conversation_context, modified_user_message


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
) -> str:
    """Gets the summarization prompt, rendering if configured and handling defaults."""
    summarization_prompt = get_attr(
        ctx,
        summarization_prompt_attr,
        None,
        auto_render=False,
    )
    if summarization_prompt is not None:
        return summarization_prompt
    return llm_config.default_summarization_prompt


def get_context_enrichment_prompt(
    ctx: AnyContext,
    context_enrichment_prompt_attr: StrAttr | None,
) -> str:
    """Gets the context enrichment prompt, rendering if configured and handling defaults."""
    context_enrichment_prompt = get_attr(
        ctx,
        context_enrichment_prompt_attr,
        None,
        auto_render=False,
    )
    if context_enrichment_prompt is not None:
        return context_enrichment_prompt
    return llm_config.default_context_enrichment_prompt
