"""Matcher operator helpers and evaluator for hook config.

The functions here are intentionally state-free so they can be unit-tested in
isolation and reused outside `HookManager`. The dispatcher dict
`MATCHER_OPERATORS` maps a `MatcherOperator` enum value to the predicate that
implements it.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from typing import Any, Callable

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import MatcherConfig
from zrb.llm.hook.types import HookEvent, MatcherOperator

logger = logging.getLogger(__name__)


# --- Matcher operator predicates -----------------------------------------


def _match_equals(value: Any, matcher_value: Any) -> bool:
    """Check if value equals matcher value."""
    return value == matcher_value


def _match_not_equals(value: Any, matcher_value: Any) -> bool:
    """Check if value does not equal matcher value."""
    return value != matcher_value


def _match_contains(value: Any, matcher_value: Any) -> bool:
    """Check if value contains matcher value (string operation)."""
    if not isinstance(value, str) or not isinstance(matcher_value, str):
        return False
    return matcher_value in value


def _match_starts_with(value: Any, matcher_value: Any) -> bool:
    """Check if value starts with matcher value (string operation)."""
    if not isinstance(value, str) or not isinstance(matcher_value, str):
        return False
    return value.startswith(matcher_value)


def _match_ends_with(value: Any, matcher_value: Any) -> bool:
    """Check if value ends with matcher value (string operation)."""
    if not isinstance(value, str) or not isinstance(matcher_value, str):
        return False
    return value.endswith(matcher_value)


def _match_regex(value: Any, matcher_value: Any) -> bool:
    """Check if value matches regex pattern."""
    if not isinstance(value, str) or not isinstance(matcher_value, str):
        return False
    try:
        return bool(re.search(matcher_value, value))
    except re.error:
        logger.warning(f"Invalid regex pattern in matcher: {matcher_value}")
        return False


def _match_glob(value: Any, matcher_value: Any) -> bool:
    """Check if value matches glob pattern."""
    if not isinstance(value, str) or not isinstance(matcher_value, str):
        return False
    return fnmatch.fnmatch(value, matcher_value)


# Dispatcher dictionary for matcher operators
MATCHER_OPERATORS: dict[MatcherOperator, Callable[[Any, Any], bool]] = {
    MatcherOperator.EQUALS: _match_equals,
    MatcherOperator.NOT_EQUALS: _match_not_equals,
    MatcherOperator.CONTAINS: _match_contains,
    MatcherOperator.STARTS_WITH: _match_starts_with,
    MatcherOperator.ENDS_WITH: _match_ends_with,
    MatcherOperator.REGEX: _match_regex,
    MatcherOperator.GLOB: _match_glob,
}


# zrb names its built-in tools with Claude-compatible names via ``func.__name__``
# (e.g. ``read_file`` -> "Read", ``write_file`` -> "Write"), so most Claude hook
# matchers keyed on a tool name already match. A few zrb tools keep a name that
# differs from Claude's, so a matcher written for the Claude name would miss
# them. This maps the zrb tool name to the extra Claude name(s) a tool-name
# matcher should also accept, e.g. ``{"matcher": "Bash"}`` fires on zrb's "Shell"
# tool, and ``{"matcher": "Task"}`` fires on the delegation tools.
CLAUDE_TOOL_ALIASES: dict[str, list[str]] = {
    "Shell": ["Bash"],
    "DelegateToAgent": ["Task"],
    "DelegateToAgentBackground": ["Task"],
}


# Mapping from HookEvent to the field that Claude Code matchers apply to
CLAUDE_EVENT_MATCHER_FIELDS: dict[HookEvent, str] = {
    HookEvent.PRE_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE_FAILURE: "tool_name",
    HookEvent.PERMISSION_REQUEST: "tool_name",
    HookEvent.USER_PROMPT_SUBMIT: "prompt",
    HookEvent.SESSION_START: "source",
    HookEvent.SESSION_END: "source",
    HookEvent.NOTIFICATION: "notification_type",
    HookEvent.SUBAGENT_START: "agent_type",
    HookEvent.SUBAGENT_STOP: "agent_type",
    HookEvent.STOP_FAILURE: "error_type",
    HookEvent.PRE_COMPACT: "trigger",
    HookEvent.POST_COMPACT: "trigger",
}


def get_field_value(context: HookContext, field_path: str) -> Any:
    """Get a value from context using dot notation.

    Supports nested access like "metadata.project.name".
    """
    parts = field_path.split(".")
    current: Any = context

    for part in parts:
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            try:
                current = getattr(current, part)
            except AttributeError:
                return None

    return current


def evaluate_matchers(matchers: list[MatcherConfig], context: HookContext) -> bool:
    """Evaluate all matchers against the given context.

    Returns True if ALL matchers pass, False otherwise. Matchers can access
    fields in the context using dot notation (e.g. "metadata.project").
    """
    if not matchers:
        return True  # No matchers means always match

    for matcher in matchers:
        value = get_field_value(context, matcher.field)

        evaluator = MATCHER_OPERATORS.get(matcher.operator)
        if evaluator is None:
            logger.warning(f"Unknown matcher operator: {matcher.operator}")
            return False

        # A tool may answer to a Claude-compatible alias (e.g. "Shell" also
        # matches "Bash"); test the value and any aliases, passing if any match.
        # NOT_EQUALS is an exclusion — expanding it would let an alias slip past
        # the filter — so it stays 1:1 on the raw value.
        if matcher.operator is MatcherOperator.NOT_EQUALS:
            candidates: list[Any] = [value]
        else:
            candidates = _tool_name_candidates(matcher.field, value)

        matcher_value = matcher.value
        if not matcher.case_sensitive:
            candidates = [c.lower() if isinstance(c, str) else c for c in candidates]
            if isinstance(matcher_value, str):
                matcher_value = matcher_value.lower()

        if not any(evaluator(candidate, matcher_value) for candidate in candidates):
            return False

    return True


def _tool_name_candidates(field: str, value: Any) -> list[Any]:
    """The matched value plus any Claude-compatible tool-name aliases for it.

    Only the tool-name field is expanded; every other field yields just its own
    value, so non-tool matchers are unaffected.
    """
    candidates: list[Any] = [value]
    if field == "tool_name" and isinstance(value, str):
        candidates.extend(CLAUDE_TOOL_ALIASES.get(value, []))
    return candidates


__all__ = [
    "MATCHER_OPERATORS",
    "CLAUDE_EVENT_MATCHER_FIELDS",
    "CLAUDE_TOOL_ALIASES",
    "evaluate_matchers",
    "get_field_value",
]
