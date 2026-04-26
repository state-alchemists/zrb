import pytest

from zrb.llm.agent.run.error_classifier import (
    get_retry_wait,
    is_invalid_tool_call_error,
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
