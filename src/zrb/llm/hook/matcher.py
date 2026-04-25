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


# Mapping from HookEvent to the field that Claude Code matchers apply to
CLAUDE_EVENT_MATCHER_FIELDS: dict[HookEvent, str] = {
    HookEvent.PRE_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE: "tool_name",
    HookEvent.POST_TOOL_USE_FAILURE: "tool_name",
    HookEvent.USER_PROMPT_SUBMIT: "prompt",
    HookEvent.SESSION_START: "source",
    HookEvent.NOTIFICATION: "message",
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

        if not matcher.case_sensitive and isinstance(value, str):
            value = value.lower()
            matcher_value = (
                matcher.value.lower()
                if isinstance(matcher.value, str)
                else matcher.value
            )
        else:
            matcher_value = matcher.value

        evaluator = MATCHER_OPERATORS.get(matcher.operator)
        if evaluator is None:
            logger.warning(f"Unknown matcher operator: {matcher.operator}")
            return False

        if not evaluator(value, matcher_value):
            return False

    return True


__all__ = [
    "MATCHER_OPERATORS",
    "CLAUDE_EVENT_MATCHER_FIELDS",
    "evaluate_matchers",
    "get_field_value",
]
