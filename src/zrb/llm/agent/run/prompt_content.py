"""Build the prompt content payload passed to pydantic-ai's `run_stream_events`.

Pure helper extracted from `run_agent.py`. The merge-into-history path
in `run_agent` wraps the list in `UserPromptPart` as needed; this helper
only normalizes the user-facing prompt + attachments.
"""

from __future__ import annotations

from typing import Any, Callable

from zrb.llm.util.attachment import normalize_attachments


def get_prompt_content(
    message: str | None,
    attachments: list[Any] | None,
    print_fn: Callable[[str], Any],
) -> list[Any] | str | None:
    """Build prompt content for pydantic-ai agent.

    Returns:
        - str: text-only prompt (passed directly to run_stream_events)
        - list[UserContent]: multimodal prompt (text + attachments)
        - None: empty prompt
    """
    if not attachments:
        return message

    attachments = normalize_attachments(attachments, print_fn)
    if not attachments:
        return message if message else None

    if message:
        content: list[Any] = [message]
        content.extend(attachments)
        return content
    return list(attachments)
