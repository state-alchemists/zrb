import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from zrb.attr.type import StrAttr
from zrb.config.llm_config import llm_config
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_attr, get_str_attr
from zrb.util.file import read_dir, read_file_with_line_numbers
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


def construct_user_prompt(user_message: str) -> str:
    current_directory = os.getcwd()
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
            rel_path = os.path.relpath(resource_path, current_directory)
            placeholder = f"`{rel_path}`"
            processed_user_message = processed_user_message.replace(
                f"@{ref}", placeholder, 1
            )
            apendix_list.append(
                make_markdown_section(
                    f"{placeholder} {ref_type}",
                    "\n".join(content) if isinstance(content, list) else content,
                    as_code=True,
                )
            )
    apendixes = "\n".join(apendix_list)
    iso_date = datetime.now(timezone.utc).astimezone().isoformat()
    modified_user_message = make_markdown_section(
        "User Request",
        "\n".join(
            [
                f"- Current Directory: {current_directory}",
                f"- Current Time: {iso_date}",
                "---",
                processed_user_message,
                make_markdown_section(
                    "📄 Apendixes",
                    apendixes,
                ),
            ]
        ),
    )
    return modified_user_message


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
