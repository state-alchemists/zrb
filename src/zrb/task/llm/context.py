import datetime
import inspect
import os
import platform
import re
from collections.abc import Callable
from typing import Any

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.util.attr import get_attr
from zrb.util.file import read_dir, read_file_with_line_numbers


def get_default_context(user_message: str) -> dict[str, Any]:
    """Generates default context including time, OS, and file references."""
    references = re.findall(r"@(\S+)", user_message)
    current_references = []

    for ref in references:
        resource_path = os.path.abspath(os.path.expanduser(ref))
        if os.path.isfile(resource_path):
            content = read_file_with_line_numbers(resource_path)
            current_references.append(
                {
                    "reference": ref,
                    "name": resource_path,
                    "type": "file",
                    "note": "line numbers are included in the content",
                    "content": content,
                }
            )
        elif os.path.isdir(resource_path):
            content = read_dir(resource_path)
            current_references.append(
                {
                    "reference": ref,
                    "name": resource_path,
                    "type": "directory",
                    "content": content,
                }
            )

    return {
        "current_time": datetime.datetime.now().isoformat(),
        "current_working_directory": os.getcwd(),
        "current_os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "current_references": current_references,
    }


def get_conversation_context(
    ctx: AnyContext,
    conversation_context_attr: (
        dict[str, Any] | Callable[[AnySharedContext], dict[str, Any]] | None
    ),
) -> dict[str, Any]:
    """
    Retrieves the conversation context.
    If a value in the context dict is callable, it executes it with ctx.
    """
    raw_context = get_attr(
        ctx, conversation_context_attr, {}, auto_render=False
    )  # Context usually shouldn't be rendered
    if not isinstance(raw_context, dict):
        ctx.log_warning(
            f"Conversation context resolved to type {type(raw_context)}, "
            "expected dict. Returning empty context."
        )
        return {}
    # If conversation_context contains callable value, execute them.
    processed_context: dict[str, Any] = {}
    for key, value in raw_context.items():
        if callable(value):
            try:
                # Check if the callable expects 'ctx'
                sig = inspect.signature(value)
                if "ctx" in sig.parameters:
                    processed_context[key] = value(ctx)
                else:
                    processed_context[key] = value()
            except Exception as e:
                ctx.log_warning(
                    f"Error executing callable for context key '{key}': {e}. "
                    "Skipping."
                )
                processed_context[key] = None
        else:
            processed_context[key] = value
    return processed_context


# Context enrichment functions moved to context_enrichment.py
