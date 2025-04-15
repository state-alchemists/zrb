import json
from textwrap import dedent
from typing import Any

from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.llm_config import llm_config as default_llm_config
from zrb.task.llm.context import get_default_context  # Updated import
from zrb.util.attr import get_attr, get_str_attr


def get_system_prompt(
    ctx: AnyContext,
    system_prompt_attr: StrAttr | None,
    render_system_prompt: bool,
) -> str:
    """Gets the system prompt, rendering if configured and handling defaults."""
    system_prompt = get_attr(
        ctx,
        system_prompt_attr,
        None,
        auto_render=render_system_prompt,
    )
    if system_prompt is not None:
        return system_prompt
    return default_llm_config.get_default_system_prompt()


def get_user_message(
    ctx: AnyContext,
    message_attr: StrAttr | None,
) -> str:
    """Gets the user message, rendering and providing a default."""
    return get_str_attr(ctx, message_attr, "How are you?", auto_render=True)


def get_summarization_prompt(
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
    return default_llm_config.get_default_summarization_prompt()


def get_context_enrichment_prompt(
    ctx: AnyContext,
    context_enrichment_prompt_attr: StrAttr | None,
    render_context_enrichment_prompt: bool,
) -> str:
    """Gets the context enrichment prompt, rendering if configured and handling defaults."""
    context_enrichment_prompt = get_attr(
        ctx,
        context_enrichment_prompt_attr,
        None,
        auto_render=render_context_enrichment_prompt,
    )
    if context_enrichment_prompt is not None:
        return context_enrichment_prompt
    return default_llm_config.get_default_context_enrichment_prompt()


def build_user_prompt(
    ctx: AnyContext,
    message_attr: StrAttr | None,
    conversation_context: dict[str, Any],
) -> str:
    """Constructs the final user prompt including context."""
    user_message = get_user_message(ctx, message_attr)
    # Combine default context, conversation context (potentially enriched/summarized)
    enriched_context = {**get_default_context(user_message), **conversation_context}
    return dedent(
        f"""
        # Context
        {json.dumps(enriched_context)}
        # User Message
        {user_message}
        """
    ).strip()
