import pytest

from zrb.llm.agent.run.error_classifier import (
    classify_error_type,
    get_retry_wait,
    is_invalid_tool_call_error,
    is_missing_reasoning_content_error,
    is_prompt_too_long_error,
    is_retryable_error,
)


def test_is_prompt_too_long_error():
    assert is_prompt_too_long_error(Exception("Prompt too long")) is True
    assert is_prompt_too_long_error(Exception("Context length exceeded")) is True
    assert is_prompt_too_long_error(Exception("Some other error")) is False


def test_is_invalid_tool_call_error():
    e = Exception("Unknown tool 'foo'")
    e.status_code = 400
    assert is_invalid_tool_call_error(e) is True

    e2 = Exception("Bad request")
    e2.status_code = 400
    assert is_invalid_tool_call_error(e2) is False

    e3 = Exception("Unknown tool 'foo'")
    e3.status_code = 500
    assert is_invalid_tool_call_error(e3) is False


def test_is_retryable_error():
    e = Exception("Rate limit exceeded")
    e.status_code = 429
    assert is_retryable_error(e) is True

    e2 = Exception("Server error")
    e2.status_code = 500
    assert is_retryable_error(e2) is True

    e3 = Exception("Not found")
    e3.status_code = 404
    assert is_retryable_error(e3) is False

    # Test via response object
    e4 = Exception("Response error")
    mock_response = type("obj", (object,), {"status_code": 429})
    e4.response = mock_response
    assert is_retryable_error(e4) is True

    # Test via message keywords
    assert is_retryable_error(Exception("overloaded")) is True
    assert is_retryable_error(Exception("rate_limit")) is True


def test_get_retry_wait():
    # Test with Retry-After header
    e = Exception("Retry")
    mock_response = type("obj", (object,), {"headers": {"retry-after": "10"}})
    e.response = mock_response
    assert get_retry_wait(e, 1, 60) == 10.0

    # Test with uppercase Retry-After header
    mock_response.headers = {"Retry-After": "5"}
    assert get_retry_wait(e, 1, 60) == 5.0

    # Test with invalid Retry-After header
    mock_response.headers = {"retry-after": "invalid"}
    assert get_retry_wait(e, 2, 60) == 4.0

    # Test with no header
    e2 = Exception("Retry")
    assert get_retry_wait(e2, 3, 60) == 8.0

    # Test max wait
    assert get_retry_wait(e2, 10, 30) == 30.0


def test_get_retry_wait_reads_a_wrapped_model_http_error():
    """pydantic-ai hands back `ModelHTTPError`, not the provider SDK's exception.

    That wrapper has no `.response`, so its `retry_after` is the only place the
    provider's requested wait survives.
    """
    from pydantic_ai.exceptions import ModelHTTPError

    e = ModelHTTPError(
        status_code=429, model_name="m", body=None, headers={"retry-after": "12"}
    )
    assert get_retry_wait(e, 1, 60) == 12.0
    # Still capped by max_wait.
    assert get_retry_wait(e, 1, 5) == 5.0

    # A wrapper carrying no usable header falls back to exponential backoff.
    bare = ModelHTTPError(status_code=429, model_name="m", body=None)
    assert get_retry_wait(bare, 3, 60) == 8.0


def test_is_missing_reasoning_content_error():
    e = Exception("Missing reasoning_content in history message")
    e.status_code = 400
    assert is_missing_reasoning_content_error(e) is True

    e2 = Exception("The reasoning_content field is required")
    e2.status_code = 400
    assert is_missing_reasoning_content_error(e2) is True

    # Bedrock GLM-5 pattern: ValidationException code with an empty Message.
    e3 = Exception("ValidationException on bedrock")
    e3.status_code = 400
    e3.body = {"Error": {"Code": "ValidationException", "Message": ""}}
    assert is_missing_reasoning_content_error(e3) is True

    # A ValidationException *with* a message is something else entirely.
    e4 = Exception("ValidationException with detail")
    e4.status_code = 400
    e4.body = {"Error": {"Code": "ValidationException", "Message": "bad input"}}
    assert is_missing_reasoning_content_error(e4) is False


def test_is_missing_reasoning_content_requires_status_400():
    e = Exception("missing reasoning_content")
    e.status_code = 500
    assert is_missing_reasoning_content_error(e) is False


def test_classify_error_type_by_status_code():
    def err(status):
        e = Exception(f"error {status}")
        e.status_code = status
        return e

    assert classify_error_type(err(429)) == "rate_limit"
    assert classify_error_type(err(401)) == "authentication_failed"
    assert classify_error_type(err(403)) == "authentication_failed"
    assert classify_error_type(err(404)) == "model_not_found"
    assert classify_error_type(err(400)) == "invalid_request"
    assert classify_error_type(err(500)) == "server_error"
    assert classify_error_type(err(503)) == "server_error"


def test_classify_error_type_overloaded():
    e = Exception("server busy")
    e.status_code = 529
    assert classify_error_type(e) == "overloaded"

    # Via message when the status code carries a plain 5xx.
    e2 = Exception("The model is overloaded right now")
    e2.status_code = 500
    assert classify_error_type(e2) == "overloaded"

    # Via message alone when there is no status code at all.
    assert classify_error_type(Exception("HTTP 529 overloaded")) == "overloaded"
    assert classify_error_type(Exception("rate limit exceeded")) == "rate_limit"


def test_classify_error_type_reads_response_when_no_status_code():
    e = Exception("gateway error")
    e.response = type("obj", (object,), {"status_code": 502})
    assert classify_error_type(e) == "server_error"


def test_classify_error_type_context_length_wins():
    e = Exception("prompt too long: context length exceeded")
    e.status_code = 400
    assert classify_error_type(e) == "context_length"


def test_classify_error_type_unknown_fallback():
    assert classify_error_type(Exception("something odd happened")) == "unknown"
