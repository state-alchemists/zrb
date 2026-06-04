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
import re
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
    deferred_mismatch_retry_done: bool = False
    empty_completion_retry_count: int = 0
    max_context_retries: int = field(
        default_factory=lambda: CFG.LLM_MAX_CONTEXT_RETRIES
    )
    max_transient_retries: int = field(
        default_factory=lambda: max(0, CFG.LLM_API_MAX_RETRIES - 1)
    )
    # An empty/placeholder completion is usually a transient provider hiccup, so
    # retry a couple of times; if it persists (e.g. context exceeds the model's
    # window) the loop raises a clear error rather than surfacing the placeholder.
    max_empty_completion_retries: int = 2


@dataclass
class RetryOutcome:
    """Decision returned by `handle_stream_error`."""

    should_retry: bool
    new_history: list[Any] | None = None
    new_message: Any = None
    clear_results: bool = False


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
        # transient_retry_count is intentionally NOT reset here: the transient
        # (429/5xx) budget derived from LLM_API_MAX_RETRIES is a global cap for
        # the whole run. A context-length prune is a different failure class and
        # must not refresh that budget, or a session alternating between the two
        # error types could retry transiently far more than configured.
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
        bad_name = _extract_invalid_tool_name(exc, current_history)
        if bad_name:
            lead = (
                "[SYSTEM] ⛔ STOP. Your last response is BROKEN.\n\n"
                f"You called: `{bad_name}` — this is NOT a real tool. "
                "It does not exist in the tool registry.\n"
            )
        else:
            lead = (
                "[SYSTEM] ⛔ STOP. Your last response is BROKEN — "
                "you called a tool name that does NOT exist.\n"
            )
        corrective = lead + (
            "\nYou likely glued multiple tool names together (e.g., "
            "`ReadRead`, `ReadReadRead`, `ActivateSkillRead`, `EditEdit`) "
            "or invented/abbreviated a name. BOTH are INVALID. Concatenated "
            "names will ALWAYS be rejected. There is no `ReadRead` in any "
            "tool registry, anywhere.\n\n"
            "RULES — non-negotiable:\n"
            "- ONE tool call per response. ONE name. ONE JSON arguments object.\n"
            "- To do N actions, send N separate responses. Wait for each result.\n"
            "- Example: reading 3 files = 3 separate responses, ONE `Read` "
            "each, NEVER one response with `ReadReadRead`.\n"
            "- Tool names come from the available list — verbatim, "
            "case-sensitive. Do NOT invent, abbreviate, modify, or combine.\n\n"
            "Now: emit exactly ONE valid tool call. Pick the single most "
            "useful next action."
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
    # An explainer ``UserPromptPart`` is always appended after the strip so
    # the model knows the ``(sanitized-history)`` markers are a record, not
    # a tool-calling format to imitate — and that tool use is still expected
    # on the next turn.
    if not state.opaque_retry_done:
        status_code = getattr(exc, "status_code", None)
        if status_code == 400:
            state.opaque_retry_done = True
            sanitized = strip_to_text_only(current_history)
            explainer = (
                "[SYSTEM] The conversation history above has been sanitized "
                "because your previous response could not round-trip through "
                "the current provider. Lines tagged `(sanitized-history)` are "
                "a TEXTUAL RECORD of past tool calls and results — they are "
                "NOT a tool-calling format and you must not imitate them. "
                "Continue the task using the normal tool-calling protocol: "
                "emit a real tool call when you need one, not a textual "
                "imitation."
            )
            sanitized = list(sanitized) + [
                ModelRequest(parts=[UserPromptPart(content=explainer)])
            ]
            fallback_message = current_message
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

    # Deferred-tool-results mismatch after history compression.
    # The history summarizer ran between deferred tool iterations and removed
    # the ModelResponse whose tool_calls matched current_results.  pydantic-ai's
    # _handle_deferred_tool_results raises UserError because the last ModelResponse
    # no longer has any ToolCallParts.  Clearing current_results lets the model
    # generate fresh tool calls on the next iteration.  We must hand back the
    # intact ``run_history`` (not ``None``) — the runner assigns ``new_history``
    # to ``current_history`` unconditionally, and the next loop iteration feeds
    # it straight into ``sanitize_history``, which raises on ``None``.
    if not state.deferred_mismatch_retry_done:
        # lazy: heavy third-party — pydantic_ai pulls in OpenAI/Anthropic SDKs.
        from pydantic_ai.exceptions import UserError as PydanticUserError

        if isinstance(exc, PydanticUserError) and (
            "does not contain any unprocessed tool calls" in str(exc)
            or "does not contain a `ModelResponse`" in str(exc)
        ):
            state.deferred_mismatch_retry_done = True
            print_fn(
                "\n[SYSTEM] Deferred tool results reference stale history — "
                "clearing pending results and retrying..."
            )
            return RetryOutcome(
                should_retry=True,
                new_history=run_history,
                clear_results=True,
            )

    return RetryOutcome(should_retry=False)


_INVALID_TOOL_NAME_PATTERNS = (
    re.compile(
        r"unknown\s+(?:tool|function)(?:\s+name)?[:\s]+['\"`]?([A-Za-z_][A-Za-z0-9_]*)['\"`]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:tool|function)\s+['\"`]?([A-Za-z_][A-Za-z0-9_]*)['\"`]?\s+(?:not\s+(?:found|defined)|is\s+(?:not\s+)?invalid)",
        re.IGNORECASE,
    ),
)


def _extract_invalid_tool_name(
    exc: Exception, current_history: list[Any]
) -> str | None:
    """Return the bad tool name when discoverable, else ``None``.

    Looks at two sources in order:

    1. The exception body (some providers include "Unknown tool: X").
    2. The recent history — zrb's ``SafeToolsetWrapper`` writes
       ``Unknown tool name: 'X'`` into a tool-return part when it
       rejects a malformed call, which is the most reliable signal
       for Ollama-cloud (whose body is the generic
       ``invalid tool call arguments``).
    """
    body = getattr(exc, "body", None)
    body_text = body.get("message") if isinstance(body, dict) else str(exc)
    if body_text:
        name = _match_invalid_tool_name(body_text)
        if name:
            return name
    for msg in reversed(current_history or []):
        for part in reversed(list(getattr(msg, "parts", None) or [])):
            content = getattr(part, "content", None)
            if not isinstance(content, str):
                continue
            name = _match_invalid_tool_name(content)
            if name:
                return name
    return None


def _match_invalid_tool_name(text: str) -> str | None:
    for pattern in _INVALID_TOOL_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None
