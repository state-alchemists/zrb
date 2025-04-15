import datetime
import inspect
import json
import os
import platform
import re
import traceback
from collections.abc import Callable
from textwrap import dedent
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from zrb.attr.type import BoolAttr
from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.task.llm.agent import run_agent_iteration  # Updated import
from zrb.task.llm.typing import ListOfDict
from zrb.util.attr import get_attr, get_bool_attr
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


class EnrichmentConfig(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    model: Model | str | None = None
    settings: ModelSettings | None = None
    prompt: str
    retries: int = 1


class EnrichmentResult(BaseModel):
    response: dict[str, Any]  # or further decompose as needed


async def enrich_context(
    ctx: AnyContext,
    config: EnrichmentConfig,
    conversation_context: dict[str, Any],
    history_list: ListOfDict,
) -> dict[str, Any]:
    """Runs an LLM call to extract key info and merge it into the context."""
    ctx.log_info("Attempting to enrich conversation context...")
    # Prepare context and history for the enrichment prompt
    try:
        context_json = json.dumps(conversation_context)
        history_json = json.dumps(history_list)
        # The user prompt will now contain the dynamic data
        user_prompt_data = dedent(
            f"""
            Analyze the following
            # Current Context
            {context_json}
            # Conversation History
            {history_json}
        """
        ).strip()
    except Exception as e:
        ctx.log_warning(f"Error formatting context/history for enrichment: {e}")
        return conversation_context  # Return original context if formatting fails

    enrichment_agent = Agent(
        model=config.model,
        # System prompt is part of the user prompt for this specific call
        system_prompt=config.prompt,  # Use the main prompt as system prompt
        tools=[],
        mcp_servers=[],
        model_settings=config.settings,
        retries=config.retries,
        result_type=EnrichmentResult,
    )

    try:
        enrichment_run = await run_agent_iteration(
            ctx=ctx,
            agent=enrichment_agent,
            user_prompt=user_prompt_data,  # Pass the formatted data as user prompt
            history_list=[],  # Enrichment agent doesn't need prior history itself
        )
        if enrichment_run and enrichment_run.result.data:
            response = enrichment_run.result.data.response
            if response:
                conversation_context.update(response)
                ctx.log_info("Context enriched based on history.")
                ctx.log_info(
                    f"Updated conversation context: {json.dumps(conversation_context)}"
                )
        else:
            ctx.log_warning("Context enrichment returned no data")
    except Exception as e:
        ctx.log_warning(f"Error during context enrichment LLM call: {e}")
        traceback.print_exc()
    return conversation_context


def should_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    should_enrich_context_attr: BoolAttr,
    render_enrich_context: bool,
) -> bool:
    """Determines if context enrichment should occur based on history and config."""
    if len(history_list) == 0:
        return False
    return get_bool_attr(
        ctx,
        should_enrich_context_attr,
        True,  # Default to True if not specified
        auto_render=render_enrich_context,
    )


async def maybe_enrich_context(
    ctx: AnyContext,
    history_list: ListOfDict,
    conversation_context: dict[str, Any],
    should_enrich_context_attr: BoolAttr,
    render_enrich_context: bool,
    model: str | Model | None,
    model_settings: ModelSettings | None,
    context_enrichment_prompt: str,
) -> dict[str, Any]:
    """Enriches context based on history if enabled."""
    if should_enrich_context(
        ctx, history_list, should_enrich_context_attr, render_enrich_context
    ):
        # Use the enrich_context function now defined in this file
        return await enrich_context(
            ctx=ctx,
            config=EnrichmentConfig(
                model=model,
                settings=model_settings,
                prompt=context_enrichment_prompt,
            ),
            conversation_context=conversation_context,
            history_list=history_list,
        )
    return conversation_context