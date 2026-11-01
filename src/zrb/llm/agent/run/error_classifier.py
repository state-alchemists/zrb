from __future__ import annotations

import re

from zrb.config.config import CFG

# pydantic-ai's missing-key wording (names the vendor variable).
_MISSING_KEY_MESSAGE = re.compile(r"Set the `\w+` environment variable")
# The OpenAI SDK's wording, raised when its client is built before pydantic-ai checks.
_OPENAI_SDK_MISSING_KEY_MESSAGE = re.compile(r"Missing credentials")


def _typed_model_errors() -> dict[str, type[Exception]]:
    """pydantic-ai's typed model errors, imported on first use.

    Lazy because this module is imported by the task layer on every path, while
    pydantic-ai is heavy and only reached once something has failed.
    """
    # lazy: heavy third-party -- pydantic_ai
    from pydantic_ai import exceptions as pai

    return {
        "rate_limit": pai.ModelRateLimitError,
        "quota": pai.ModelQuotaExceededError,
        "unavailable": pai.ModelUnavailableError,
        "overloaded": pai.ModelOverloadedError,
        "server": pai.ModelServerError,
        "connection": pai.ModelConnectionError,
        "timeout": pai.ModelTimeoutError,
        "context_window": pai.ModelContextWindowExceededError,
    }


def _is_typed_model_error(e: BaseException, *kinds: str) -> bool:
    """True when *e* is one of pydantic-ai's typed model errors.

    pydantic-ai classifies the provider answer where it is received, for the
    OpenAI-compatible path too (`_model_errors.openai_compatible_category`, which
    reads `context_length_exceeded` and the wording OpenRouter, vLLM and Groq
    use), and for Bedrock and Google by their own mappings. So the type is the
    precise answer and the status code is the approximation; these checks run
    first and the heuristics stay for errors that arrive untyped.
    """
    errors = _typed_model_errors()
    return isinstance(e, tuple(errors[kind] for kind in kinds))


def is_prompt_too_long_error(e: Exception) -> bool:
    """Returns True if the exception is a context length / token limit error."""
    if _is_typed_model_error(e, "context_window"):
        return True
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

    Reads the body's message, not str(e), to avoid matching wrapper metadata
    such as ``'type': 'invalid_request_error'``.
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
    """Returns True if the provider rejects history over reasoning_content.

    DeepSeek demands it be echoed back; GLM-5 on Bedrock rejects thinking parts
    with a message-less ValidationException.
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
    """Returns True for transient provider errors worth retrying.

    An exhausted quota arrives as a 429 like a rate limit does, but waiting does
    not refill it — pydantic-ai gives it its own class precisely so this can be
    told apart, and the status-code branch below cannot.
    """
    if _is_typed_model_error(e, "quota"):
        return False
    if _is_typed_model_error(
        e, "rate_limit", "unavailable", "overloaded", "server", "connection", "timeout"
    ):
        return True
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


# Categories `classify_error_type` returns that no amount of retrying can fix:
# the credentials, the model name, or the request itself is wrong.
_PERMANENT_ERROR_TYPES = frozenset(
    {"authentication_failed", "model_not_found", "invalid_request", "context_length"}
)


def is_permanent_error(e: BaseException) -> bool:
    """Returns True for failures a retry cannot fix.

    Not the inverse of `is_retryable_error`: an unrecognized error is neither
    known-transient nor known-permanent, and keeps its retry.
    """
    # lazy: heavy third-party -- pydantic_ai
    from pydantic_ai.exceptions import UserError

    # pydantic-ai's misconfiguration class (missing key, bad model string).
    if isinstance(e, UserError):
        return True
    # An exhausted quota or spend limit: the next attempt fails the same way.
    if _is_typed_model_error(e, "quota"):
        return True
    if not isinstance(e, Exception):
        return False
    return classify_error_type(e) in _PERMANENT_ERROR_TYPES


def retry_unless_permanent(e: BaseException) -> bool:
    """Default `retry_if` for the LLM tasks: retry blips, not misconfiguration."""
    return not is_permanent_error(e)


def _classify_typed_model_error(e: Exception) -> str | None:
    """The StopFailure token for a pydantic-ai typed error, or None for an untyped one."""
    if _is_typed_model_error(e, "context_window"):
        return "context_length"
    if _is_typed_model_error(e, "overloaded"):
        return "overloaded"
    if _is_typed_model_error(e, "server"):
        return "server_error"
    if _is_typed_model_error(e, "rate_limit", "quota"):
        return "rate_limit"
    return None


def classify_error_type(e: Exception) -> str:
    """Classify an exception into Claude Code's StopFailure error-type tokens, else "unknown".

    pydantic-ai's typed errors are consulted first, because they are decided from
    the provider's own code or message where the answer is received, and a status
    code is not enough to tell these apart: an exhausted quota and a rate limit
    are both 429, and OpenRouter and vLLM report a context overflow as a 400 with
    no distinguishing code. The status and keyword branches below stay for errors
    that arrive untyped — a raw SDK exception, or a provider path that has not
    been classified yet.
    """
    typed = _classify_typed_model_error(e)
    if typed is not None:
        return typed
    return _classify_untyped_error(e)


def _classify_untyped_error(e: Exception) -> str:
    """The status-code and keyword branches, for an error pydantic-ai did not classify."""
    status_code = getattr(e, "status_code", None)
    if status_code is None:
        response = getattr(e, "response", None)
        status_code = getattr(response, "status_code", None)
    msg = str(e).lower()
    token = _token_for_status(e, status_code, msg)
    if token is not None:
        return token
    return _token_for_keywords(msg) or "unknown"


def _token_for_status(e: Exception, status_code: int | None, msg: str) -> str | None:
    """The token an HTTP status implies, or None when it decides nothing.

    Transient statuses win over keywords (Ollama's 500 "Maximum context length
    exceeded" is transient), matching `handle_stream_error`'s order.
    """
    if status_code == 429:
        return "rate_limit"
    if status_code is not None and status_code >= 500:
        if status_code == 529 or "overloaded" in msg:
            return "overloaded"
        return "server_error"
    if is_prompt_too_long_error(e):
        return "context_length"
    if status_code in (401, 403):
        return "authentication_failed"
    if status_code == 404:
        return "model_not_found"
    if status_code == 400:
        return "invalid_request"
    return None


def _token_for_keywords(msg: str) -> str | None:
    """The token the error text implies, for an error with no decisive status."""
    if "overloaded" in msg or "529" in msg:
        return "overloaded"
    if "rate limit" in msg or "rate_limit" in msg:
        return "rate_limit"
    return None


def get_retry_wait(e: Exception, attempt: int, max_wait: float) -> float:
    """Exponential backoff, honoring ``Retry-After`` when the provider sent one.

    Read from ``ModelHTTPError.retry_after`` (parses the HTTP-date form too) or
    a raw SDK exception's httpx ``response`` headers.
    """
    retry_after = getattr(e, "retry_after", None)
    if isinstance(retry_after, (int, float)):
        return min(float(retry_after), max_wait)
    response = getattr(e, "response", None)
    if response is not None:
        headers = getattr(response, "headers", {})
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw is not None:
            try:
                return min(float(raw), max_wait)
            except ValueError:
                pass
    return min(2**attempt, max_wait)


def add_credential_hint(e: Exception) -> Exception:
    """Return *e* with a hint about zrb's own API key when it is a missing-key error."""
    # lazy: heavy third-party -- pydantic_ai, openai
    from openai import OpenAIError
    from pydantic_ai.exceptions import UserError

    hinted_type: type[Exception]
    if isinstance(e, UserError) and _MISSING_KEY_MESSAGE.search(str(e)):
        hinted_type = UserError
    elif isinstance(e, OpenAIError) and _OPENAI_SDK_MISSING_KEY_MESSAGE.search(str(e)):
        hinted_type = OpenAIError
    else:
        return e
    prefix = CFG.ENV_PREFIX
    hint = (
        f"Alternatively, set {prefix}_LLM_API_KEY: zrb sends it only to the "
        f"provider named by {prefix}_LLM_PROVIDER, else by the prefix of "
        f"{prefix}_LLM_MODEL. See docs/configuration/llm-config.md, "
        '"Which API Key Gets Used".'
    )
    hinted = hinted_type(f"{e}\n{hint}")
    hinted.__cause__ = e
    return hinted
