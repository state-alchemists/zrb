"""
Tool wrapper utilities for consistent LLM tool behavior.

Tools registered via create_agent() are already wrapped by _create_safe_wrapper
in zrb.llm.agent.common. Use tool_safe_async only when you want a custom
error_hint appended to the error message.
"""

import functools
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def _get_hint(
    error_hint: str | Callable[..., str] | None,
    args: Any,
    kwargs: Any,
    exc: Exception,
) -> str:
    if error_hint is None:
        return ""
    if callable(error_hint):
        try:
            hint = error_hint(*args, **kwargs)
        except Exception:  # noqa: BLE001
            hint = ""
        return hint
    return error_hint


def _format_error(
    func_name: str,
    args: Any,
    kwargs: Any,
    exc: Exception,
    hint: str,
) -> str:
    error_msg = str(exc).strip()
    if not error_msg:
        error_msg = f"{type(exc).__name__}"

    formatted = f"Error in {func_name}: {error_msg}"
    if hint:
        formatted += f" [SYSTEM SUGGESTION]: {hint}"
    return formatted


def tool_safe_async(
    func: Callable[P, T] | None = None,
    *,
    error_hint: str | Callable[..., str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Wrap an async tool so exceptions become an error string for the LLM."""

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            try:
                return await fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                hint = _get_hint(error_hint, args, kwargs, e)
                return _format_error(fn.__name__, args, kwargs, e, hint)

        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
