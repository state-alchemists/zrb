import pytest

from zrb.llm.config.limiter import LLMLimiter


def test_limiter_to_str_dict_explosion():
    'Test count_tokens handles large dictionaries efficiently.'
    limiter = LLMLimiter()

    large_dict = {f"key{i}": "a" * 1000 for i in range(1000)}

    tokens = limiter.count_tokens(large_dict)
    print(f"Tokens for large dict: {tokens}")



    assert tokens > 0

    assert tokens < 500000


def test_limiter_to_str_nested_list():
    'Test count_tokens handles nested lists correctly.'
    limiter = LLMLimiter()

    nested = [[["content"] * 10] * 10] * 10

    tokens = limiter.count_tokens(nested)


    assert tokens > 0

    assert tokens < 5000
