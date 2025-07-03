🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Rate Limiter Config

## Overview

The `LLMRateLimiter` class in [`src/zrb/llm_rate_limitter.py`](../../../src/zrb/llm_rate_limitter.py) helps enforce API rate limits and throttling for LLM requests. It tracks requests and tokens in a rolling 60-second window, ensuring that the application stays within the defined limits.

To configure the rate limiter, you can access and manipulate the `llm_rate_limitter` singleton by importing `zrb.llm_config` in your `zrb_init.py`:

```python
from zrb import llm_config

# Set the maximum number of requests per minute
llm_config.llm_rate_limitter.set_max_requests_per_minute(15)

# Set the maximum number of tokens per minute
llm_config.llm_rate_limitter.set_max_tokens_per_minute(100000)

# Set the maximum number of tokens per request
llm_config.llm_rate_limitter.set_max_tokens_per_request(50000)

# Set the throttle sleep duration
llm_config.llm_rate_limitter.set_throttle_sleep(1.0)

# Set the token counter function
llm_config.llm_rate_limitter.set_token_counter_fn(lambda x: len(x.split()))
```

## Properties

### `max_requests_per_minute`
- **Description**: The maximum number of requests allowed per minute.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_REQUESTS_PER_MINUTE`

### `max_tokens_per_minute`
- **Description**: The maximum number of tokens allowed per minute.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_TOKENS_PER_MINUTE`

### `max_tokens_per_request`
- **Description**: The maximum number of tokens allowed per individual request.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_TOKENS_PER_REQUEST`

### `throttle_sleep`
- **Description**: The number of seconds to sleep when throttling is required.
- **Type**: `float`
- **Environment Variable**: `ZRB_LLM_THROTTLE_SLEEP`

### `token_counter_fn`
- **Description**: A function that counts the number of tokens in a given prompt.
- **Type**: `Callable[[str], int]`

## Methods

### `set_max_requests_per_minute(value: int)`
- **Description**: Sets the maximum number of requests per minute.

### `set_max_tokens_per_minute(value: int)`
- **Description**: Sets the maximum number of tokens per minute.

### `set_max_tokens_per_request(value: int)`
- **Description**: Sets the maximum number of tokens per request.

### `set_throttle_sleep(value: float)`
- **Description**: Sets the number of seconds to sleep when throttling is required.

### `set_token_counter_fn(fn: Callable[[str], int])`
- **Description**: Sets the function that counts the number of tokens in a given prompt.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)