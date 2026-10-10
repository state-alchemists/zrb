"""Naming a conversation from its first message (ADR-0109)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.util.subagent_session_naming import parse_delegated_session
from zrb.util.string.name import is_random_name

if TYPE_CHECKING:
    from pydantic_ai.models import Model

_MAX_SLUG_LENGTH = 40
_MAX_MESSAGE_CHARS = 2000


def should_auto_name(conversation_name: str) -> bool:
    """Whether *conversation_name* is still the generated default and
    auto-naming is on."""
    return CFG.LLM_AUTO_NAME_ENABLED and is_random_name(conversation_name)


def sanitize_slug(text: str) -> str:
    """*text* as a `[a-z0-9-]` slug of at most 40 characters; "" when nothing is left."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:_MAX_SLUG_LENGTH].strip("-")


def with_slug(conversation_name: str, slug: str) -> str:
    """`trim-coil-1234` + `greetings` -> `trim-coil-1234-greetings`. Raises
    `ConversationNamingError` when the result would look like a delegated
    sub-agent transcript (`…-sub-<agent>-<id>`), which is stored elsewhere."""
    name = f"{conversation_name}-{slug}"
    if parse_delegated_session(name) is not None:
        raise ConversationNamingError(
            f"'{name}' looks like a sub-agent transcript name; the conversation "
            "keeps its generated name."
        )
    return name


class ConversationNamingError(Exception):
    """The small model could not name the conversation."""


async def suggest_slug(message: str, model: "str | Model | None" = None) -> str:
    """A short topic slug for *message* from the small model. Raises
    `ConversationNamingError` when the model fails or gives nothing usable."""
    # lazy: heavy third-party — building an agent pulls in pydantic_ai.
    from zrb.llm.agent.common import create_agent

    try:
        agent = create_agent(
            model=resolve_configured_small_model(model or CFG.LLM_AUTO_NAME_MODEL),
            system_prompt=get_prompt("conversation_namer"),
            resolve_model=False,
        )
        result = await agent.run(message[:_MAX_MESSAGE_CHARS])
        slug = sanitize_slug(str(result.output or ""))
    except Exception as e:
        raise ConversationNamingError(str(e) or type(e).__name__) from e
    if not slug:
        raise ConversationNamingError(
            "the model returned no usable topic; the conversation keeps its generated name"
        )
    return slug
