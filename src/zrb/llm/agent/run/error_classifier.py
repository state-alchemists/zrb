from __future__ import annotations


def is_prompt_too_long_error(e: Exception) -> bool:
    """Returns True if the exception is a context length / token limit error."""
    err_str = str(e).lower()
    context_keywords = [
        "prompt too long",
        "context length",
        "context window",
        "max tokens",
        "token limit",
        "input too long",
        "maximum context",
    ]
    return any(keyword in err_str for keyword in context_keywords)


def is_invalid_tool_call_error(e: Exception) -> bool:
    """Returns True if the exception is an HTTP 400 caused by an invalid/unknown tool name.

    Some model APIs (e.g. Ollama) reject responses where the model referenced a tool
    that was not in the registered tool list, returning HTTP 400 instead of handling
    the unknown call gracefully.
    """
    status_code = getattr(e, "status_code", None)
    if status_code != 400:
        return False
    err_str = str(e).lower()
    tool_keywords = [
        "tool",
        "function",
        "unknown",
        "invalid",
        "not defined",
        "not found",
    ]
    return any(keyword in err_str for keyword in tool_keywords)


def is_retryable_error(e: Exception) -> bool:
    """Returns True for transient provider errors (429, 5xx) worth retrying."""
    status_code = getattr(e, "status_code", None)
    if status_code is not None:
        return status_code == 429 or status_code >= 500
    response = getattr(e, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if code is not None:
            return code == 429 or code >= 500
    msg = str(e).lower()
    return any(
        k in msg
        for k in ("rate limit", "rate_limit", "529", "503", "502", "overloaded")
    )


def get_retry_wait(e: Exception, attempt: int, max_wait: float) -> float:
    """Exponential backoff, honoring Retry-After header when present."""
    response = getattr(e, "response", None)
    if response is not None:
        headers = getattr(response, "headers", {})
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(float(retry_after), max_wait)
            except ValueError:
                pass
    return min(2**attempt, max_wait)
