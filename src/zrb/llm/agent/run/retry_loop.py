"""Stream-error retry decisions for `run_agent`.

Encapsulates the retry policies that share the main agent loop:
- transient provider errors (429/5xx-style): exponential-ish wait, capped count
- prompt-too-long errors: drop one history turn, capped count
- invalid tool call: inject a single corrective system message, once
- opaque 400: collapse history to text-only and retry once

The opaque-400 handler is deliberately *not* provider-specific. When a model
response can't round-trip through its own provider (GLM-5 on Bedrock, DeepSeek
on third-party gateways, local models, …) the error is always a 400 with some
provider-specific body shape. Rather than catalog every variant, the fallback
collapses all messages to plain text — the least common denominator that every
provider accepts.

`handle_stream_error` mutates `RetryState` in place and sleeps internally
for the transient case, returning whether the caller should retry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.llm.agent.run.error_classifier import (
    get_retry_wait,
    is_invalid_tool_call_error,
    is_missing_reasoning_content_error,
    is_prompt_too_long_error,
    is_retryable_error,
)
from zrb.llm.agent.run.history_utils import (
    drop_oldest_turn,
    strip_thinking_parts,
    strip_to_text_only,
)


@dataclass
class RetryState:
    """Counters and one-shot flags carried across stream-error retries."""

    context_retry_count: int = 0
    transient_retry_count: int = 0
    invalid_tool_retry_done: bool = False
    missing_reasoning_retry_done: bool = False
    opaque_retry_done: bool = False
    max_context_retries: int = field(
        default_factory=lambda: CFG.LLM_MAX_CONTEXT_RETRIES
    )
    max_transient_retries: int = field(
        default_factory=lambda: max(0, CFG.LLM_API_MAX_RETRIES - 1)
    )


@dataclass
class RetryOutcome:
    """Decision returned by `handle_stream_error`."""

    should_retry: bool
    new_history: list[Any] | None = None
    new_message: Any = None


async def handle_stream_error(
    state: RetryState,
    exc: Exception,
    current_history: list[Any],
    current_message: Any,
    run_history: list[Any],
    print_fn: Callable[[str], Awaitable[Any] | Any],
    min_turns: int = 0,
) -> RetryOutcome:
    """Decide whether/how to retry after a stream error. Sleeps for transient errors."""
    # lazy: heavy third-party — pydantic_ai pulls in OpenAI/Anthropic SDKs.
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    if (
        is_retryable_error(exc)
        and state.transient_retry_count < state.max_transient_retries
    ):
        state.transient_retry_count += 1
        wait_secs = get_retry_wait(
            exc, state.transient_retry_count, CFG.LLM_API_MAX_WAIT
        )
        print_fn(
            f"\n[SYSTEM] Transient provider error, retrying in {wait_secs:.0f}s"
            f" (attempt {state.transient_retry_count}/{state.max_transient_retries})..."
        )
        CFG.LOGGER.debug(
            f"Retryable error (attempt {state.transient_retry_count}): {exc}"
        )
        await asyncio.sleep(wait_secs)
        return RetryOutcome(
            should_retry=True,
            new_history=current_history,
            new_message=current_message,
        )

    if (
        is_prompt_too_long_error(exc)
        and state.context_retry_count < state.max_context_retries
    ):
        state.context_retry_count += 1
        state.transient_retry_count = 0
        new_history = drop_oldest_turn(current_history, min_turns=min_turns)
        print_fn(
            f"\n[SYSTEM] Context too long, retrying with reduced history"
            f" (attempt {state.context_retry_count}/{state.max_context_retries})..."
        )
        CFG.LOGGER.debug(
            f"Prompt too long: retrying with {len(new_history)} history messages"
        )
        return RetryOutcome(
            should_retry=True,
            new_history=new_history,
            new_message=current_message,
        )

    if (
        is_missing_reasoning_content_error(exc)
        and not state.missing_reasoning_retry_done
    ):
        state.missing_reasoning_retry_done = True
        print_fn(
            "\n[SYSTEM] Provider requires reasoning_content in history — "
            "stripping thinking parts and retrying..."
        )
        CFG.LOGGER.debug(
            f"Missing reasoning_content error: {exc}. Stripping thinking parts from history."
        )
        sanitized = strip_thinking_parts(current_history)
        return RetryOutcome(
            should_retry=True,
            new_history=sanitized,
            new_message=current_message,
        )

    if is_invalid_tool_call_error(exc) and not state.invalid_tool_retry_done:
        state.invalid_tool_retry_done = True
        corrective = (
            "[SYSTEM] Your previous response was rejected because it referenced "
            "an invalid or non-existent tool name. Use only the exact tool names "
            "available to you — do not combine, modify, or invent tool names."
        )
        print_fn("\n[SYSTEM] Invalid tool call detected, asking model to retry...")
        CFG.LOGGER.debug(
            f"Invalid tool call error: {exc}. Injecting corrective message."
        )

        if current_message is not None and isinstance(current_message, str):
            return RetryOutcome(
                should_retry=True,
                new_history=current_history,
                new_message=current_message + "\n\n" + corrective,
            )
        return RetryOutcome(
            should_retry=True,
            new_history=list(run_history)
            + [ModelRequest(parts=[UserPromptPart(content=corrective)])],
            new_message=None,
        )

    # Generic opaque-400 retry: collapse history to text-only and retry once.
    # This catches any 400 that wasn't classified by the handlers above —
    # most commonly a model response that can't round-trip through its own
    # provider (GLM-5 on Bedrock, DeepSeek, local models, …).  Text is the
    # lowest common denominator every provider accepts.
    #
    # The guard used to require ``current_message is not None``, but that
    # skipped the handler when ``_merge_consecutive_messages`` had merged
    # the user message into a previous ``ModelRequest`` (common during tool-
    # call iterations and outer-retry resume).  Remove the guard so every
    # opaque 400 gets the text-only fallback regardless of message state.
    # When ``current_message`` is *None* we inject a resume prompt so the
    # model produces a plain-text continuation instead of re-entering the
    # tool-calling flow that triggered the rejection.
    if not state.opaque_retry_done:
        status_code = getattr(exc, "status_code", None)
        if status_code == 400:
            state.opaque_retry_done = True
            sanitized = strip_to_text_only(current_history)
            fallback_message = current_message
            if fallback_message is None:
                fallback_message = (
                    "[SYSTEM] The previous response was rejected by the provider. "
                    "Please continue with a plain-text response — do not use tools."
                )
                sanitized = list(sanitized) + [
                    ModelRequest(parts=[UserPromptPart(content=fallback_message)])
                ]
                fallback_message = None
            print_fn(
                "\n[SYSTEM] Model response rejected by provider — "
                "collapsing history to text-only and retrying..."
            )
            CFG.LOGGER.debug(
                f"Opaque 400 error: {exc}. Falling back to text-only history."
            )
            return RetryOutcome(
                should_retry=True,
                new_history=sanitized,
                new_message=fallback_message,
            )

    return RetryOutcome(should_retry=False)
