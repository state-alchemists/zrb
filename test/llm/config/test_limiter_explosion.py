import pytest

from zrb.llm.config.limiter import LLMLimiter


def test_limiter_to_str_dict_explosion():
    """Test count_tokens handles large dictionaries efficiently."""
    limiter = LLMLimiter()
    # A dictionary with 1000 keys, each having a 1000-char string
    large_dict = {f"key{i}": "a" * 1000 for i in range(1000)}

    tokens = limiter.count_tokens(large_dict)
    print(f"Tokens for large dict: {tokens}")
    # Token count should be positive and reasonable
    # With char/4 approximation: ~250,000 tokens
    # With tiktoken: varies based on encoding
    assert tokens > 0
    # Should complete without memory explosion
    assert tokens < 500000  # Reasonable upper bound


def test_limiter_to_str_nested_list():
    """Test count_tokens handles nested lists correctly."""
    limiter = LLMLimiter()
    # Nested lists
    nested = [[["content"] * 10] * 10] * 10
    # This shouldn't explode, but let's see what it produces
    tokens = limiter.count_tokens(nested)
    # "content" is 7 chars. 7 * 10 * 10 * 10 = 7000 chars.
    # Token count should be positive
    assert tokens > 0
    # Upper bound depends on encoding method
    assert tokens < 5000
