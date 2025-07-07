from zrb.attr.type import StrAttr
from zrb.config.llm_config import llm_config as llm_config
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_attr, get_str_attr


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


def get_combined_system_prompt(
    ctx: AnyContext,
    persona_attr: StrAttr | None,
    system_prompt_attr: StrAttr | None,
    special_instruction_prompt_attr: StrAttr | None,
) -> str:
    """Combines persona, base system prompt, and special instructions."""
    persona = get_persona(ctx, persona_attr)
    base_system_prompt = get_base_system_prompt(ctx, system_prompt_attr)
    special_instruction = get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr
    )
    parts = []
    if persona:
        parts.append(persona)
    if base_system_prompt:
        parts.append(base_system_prompt)
    if special_instruction:
        parts.append(special_instruction)
    return "\n\n".join(parts).strip()


def get_user_message(
    ctx: AnyContext,
    message_attr: StrAttr | None,
    render_user_message: bool,
) -> str:
    """Gets the user message, rendering and providing a default."""
    return get_str_attr(
        ctx, message_attr, "How are you?", auto_render=render_user_message
    )


def get_summarization_prompt(
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
