from zrb.attr.type import StrAttr
from zrb.context.any_context import AnyContext
from zrb.llm_config import llm_config as default_llm_config
from zrb.util.attr import get_attr, get_str_attr


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
    return default_llm_config.get_default_persona() or ""


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
    return default_llm_config.get_default_system_prompt() or ""


def get_special_instruction_prompt(
    ctx: AnyContext,
    special_instruction_prompt_attr: StrAttr | None,
    render_special_instruction_prompt: bool,
) -> str:
    """Gets the special instruction prompt, prioritizing task-specific, then default."""
    special_instruction = get_attr(
        ctx,
        special_instruction_prompt_attr,
        None,
        auto_render=render_special_instruction_prompt,
    )
    if special_instruction is not None:
        return special_instruction
    return default_llm_config.get_default_special_instruction_prompt() or ""


def get_combined_system_prompt(
    ctx: AnyContext,
    persona_attr: StrAttr | None,
    render_persona: bool,
    system_prompt_attr: StrAttr | None,
    render_system_prompt: bool,
    special_instruction_prompt_attr: StrAttr | None,
    render_special_instruction_prompt: bool,
) -> str:
    """Combines persona, base system prompt, and special instructions."""
    persona = get_persona(ctx, persona_attr, render_persona)
    base_system_prompt = get_base_system_prompt(
        ctx, system_prompt_attr, render_system_prompt
    )
    special_instruction = get_special_instruction_prompt(
        ctx, special_instruction_prompt_attr, render_special_instruction_prompt
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
