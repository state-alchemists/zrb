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


def _get_body_message(e: Exception) -> str:
    """Extract the provider's error message from the body, falling back to str(e)."""
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        msg = body.get("message") or ""
        return msg
    return str(e)


def is_invalid_tool_call_error(e: Exception) -> bool:
    """Returns True if the exception is an HTTP 400 caused by an invalid/unknown tool name.

    Some model APIs (e.g. Ollama) reject responses where the model referenced a tool
    that was not in the registered tool list, returning HTTP 400 instead of handling
    the unknown call gracefully.

    Checks the body's *message* field (not the outer str(e)) to avoid false-positives
    from wrapper metadata such as ``'type': 'invalid_request_error'``.
    """
    status_code = getattr(e, "status_code", None)
    if status_code != 400:
        return False
    err_str = _get_body_message(e).lower()
    entity_keywords = ["tool", "function"]
    problem_keywords = ["unknown", "invalid", "not defined", "not found"]
    return any(e in err_str for e in entity_keywords) and any(
        p in err_str for p in problem_keywords
    )


def is_missing_reasoning_content_error(e: Exception) -> bool:
    """Returns True if the provider requires reasoning_content in a history message.

    DeepSeek V3.2/V4 with tool calls requires the assistant's reasoning_content
    to be echoed back in multi-turn conversations.

    GLM-5 on Bedrock also rejects thinking parts in history, but returns a
    ValidationException with an empty Message field — detected by matching
    the error code pattern with no descriptive message.
    """
    status_code = getattr(e, "status_code", None)
    if status_code != 400:
        return False
    err_str = str(e).lower()
    if "missing reasoning_content" in err_str or "reasoning_content field" in err_str:
        return True
    # Bedrock ValidationException with empty message (GLM-5 pattern)
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        error = body.get("Error", {})
        if isinstance(error, dict):
            code = error.get("Code", "")
            message = error.get("Message", "")
            if code == "ValidationException" and not message:
                return True
    return False


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
