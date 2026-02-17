import pytest

from zrb.llm.config.limiter import LLMLimiter


def test_limiter_to_str_dict_explosion():
    limiter = LLMLimiter()
    # A dictionary with 1000 keys, each having a 1000-char string
    large_dict = {f"key{i}": "a" * 1000 for i in range(1000)}
    # Total chars: keys (~6000) + values (1,000,000) = ~1,006,000
    # Expected tokens: ~335,333

    tokens = limiter.count_tokens(large_dict)
    print(f"Tokens for large dict: {tokens}")
    assert tokens > 300000


def test_limiter_to_str_nested_list():
    limiter = LLMLimiter()
    # Nested lists
    nested = [[["content"] * 10] * 10] * 10
    # This shouldn't explode, but let's see what it produces
    tokens = limiter.count_tokens(nested)
    # "content" is 7 chars. 7 * 10 * 10 * 10 = 7000 chars.
    # Using len(text) // 3 as an approximation without tiktoken
    assert tokens > 2300
    assert tokens < 2500
