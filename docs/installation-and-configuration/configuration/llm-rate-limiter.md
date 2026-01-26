🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Rate Limiter Config

## Overview

The `LLMLimiter` class in [`src/zrb/llm/config/limiter.py`](../../../src/zrb/llm/config/limiter.py) manages LLM constraints: Context Window (Pruning) and Rate Limits (Throttling). It is designed as a singleton to share limits across tasks.

To configure the rate limiter, you can access and manipulate the `llm_limiter` singleton from `zrb.llm.config.limiter` in your `zrb_init.py`:

```python
from zrb.llm.config.limiter import llm_limiter

# Set the maximum number of requests per minute
llm_limiter.max_request_per_minute = 15

# Set the maximum number of tokens per minute
llm_limiter.max_token_per_minute = 100000

# Set the maximum number of tokens per request
llm_limiter.max_token_per_request = 120000

# Set the throttle check interval
llm_limiter.throttle_check_interval = 0.1
```

## Properties

### `max_request_per_minute`
- **Description**: The maximum number of requests allowed per minute.
- **Type**: `int`
- **Default**: `60`
- **Environment Variable**: `ZRB_LLM_MAX_REQUEST_PER_MINUTE` (also accepts `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` for backward compatibility)

### `max_token_per_minute`
- **Description**: The maximum number of tokens allowed per minute.
- **Type**: `int`
- **Default**: `100000`
- **Environment Variable**: `ZRB_LLM_MAX_TOKEN_PER_MINUTE` (also accepts `ZRB_LLM_MAX_TOKENS_PER_MINUTE` for backward compatibility)

### `max_token_per_request`
- **Description**: The maximum number of tokens allowed per individual LLM request.
- **Type**: `int`
- **Default**: `120000`
- **Environment Variable**: `ZRB_LLM_MAX_TOKEN_PER_REQUEST` (also accepts `ZRB_LLM_MAX_TOKENS_PER_REQUEST` for backward compatibility)

### `throttle_check_interval`
- **Description**: The interval (in seconds) to check for rate limit clearance.
- **Type**: `float`
- **Default**: `1.0`
- **Environment Variable**: `ZRB_LLM_THROTTLE_SLEEP`

### `use_tiktoken`
- **Description**: Whether to use Tiktoken for accurate token counting.
- **Type**: `bool`
- **Default**: `False`
- **Environment Variable**: `ZRB_USE_TIKTOKEN`

### `tiktoken_encoding`
- **Description**: The Tiktoken encoding scheme to use.
- **Type**: `str`
- **Default**: `cl100k_base`
- **Environment Variable**: `ZRB_TIKTOKEN_ENCODING_NAME`

## Methods

### `fit_context_window(history: list[Any], new_message: Any) -> list[Any]`
- **Description**: Prunes the conversation history to ensure the new message fits within the `max_token_per_request` limit (with a 95% buffer).

### `count_tokens(content: Any) -> int`
- **Description**: Counts the number of tokens in the given content. Uses Tiktoken if available, otherwise falls back to character-based approximation (characters ÷ 3).

### `acquire(content: Any, notifier: Callable[[str], Any] | None = None)`
- **Description**: Asynchronously acquires permission to proceed with the request, waiting if rate limits are exceeded.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)