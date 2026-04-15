"""
Tool wrapper utilities for consistent LLM tool behavior.

All LLM tools should:
- Return strings (never raise exceptions to the LLM layer)
- Format errors as "Error: <what went wrong>. [SYSTEM SUGGESTION]: <how to fix>"
- Be synchronous (sync) when registered with pydantic-ai (async is handled by the agent)
"""

import functools
from typing import Any, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def tool_safe(
    func: Callable[P, T] | None = None,
    *,
    error_hint: str | Callable[..., str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, str]] | Callable[P, T]:
    """
    Decorator that wraps a tool function so all exceptions become
    error strings the LLM can understand and act on.

    Usage:
        @tool_safe
        def my_tool(path: str) -> str:
            ...

        @tool_safe(error_hint="Use Glob to find files first.")
        def read_file(path: str) -> str:
            ...

    Args:
        func: The function to wrap.
        error_hint: A string or callable returning a hint for recovery.
                    If callable, it receives the same args as the wrapped function.
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, str]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            try:
                result = fn(*args, **kwargs)
                # If the tool already returns a string (presumably error already formatted),
                # pass it through. This lets tools do their own error formatting.
                return result
            except Exception as e:  # noqa: BLE001
                hint = _get_hint(error_hint, args, kwargs, e)
                return _format_error(fn.__name__, args, kwargs, e, hint)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


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
    """
    Async version of @tool_safe. Preserves async behavior but
    wraps the await chain so exceptions become error strings.

    Note: Since this wraps the coroutine, errors during the await
    (not during the call) will still propagate as exceptions.
    Use this for tools that do async I/O internally.
    """

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
