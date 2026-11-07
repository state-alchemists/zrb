"""Build the prompt content payload passed to pydantic-ai's `run_stream_events`.

Pure helper: it only normalizes the user-facing prompt + attachments. The
merge-into-history path in `run_agent` wraps the list in `UserPromptPart` as
needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.util.attachment import normalize_attachments

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.messages import UserContent

    from zrb.llm.agent.run.typing_aliases import PrintFn, PromptMessage


def get_prompt_content(
    message: str | None,
    attachments: Sequence[UserContent | None] | None,
    print_fn: PrintFn,
) -> PromptMessage:
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
        content: list[UserContent] = [message]
        content.extend(attachments)
        return content
    return list(attachments)
