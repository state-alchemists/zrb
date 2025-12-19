🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Rate Limiter Config

## Overview

The `LLMRateLimitter` class in [`src/zrb/llm_rate_limitter.py`](../../../src/zrb/llm_rate_limitter.py) helps enforce API rate limits and throttling for LLM requests. It tracks requests and tokens in a rolling 60-second window, ensuring that the application stays within the defined limits.

To configure the rate limiter, you can access and manipulate the `llm_rate_limitter` singleton by importing `zrb.llm_config` in your `zrb_init.py`:

```python
from zrb import llm_config

# Set the maximum number of requests per minute
llm_config.llm_rate_limitter.set_max_requests_per_minute(15)

# Set the maximum number of tokens per minute
llm_config.llm_rate_limitter.set_max_tokens_per_minute(100000)

# Set the maximum number of tokens per request
llm_config.llm_rate_limitter.set_max_tokens_per_request(120000)

# Set the maximum number of tokens per tool call result
llm_config.llm_rate_limitter.set_max_tokens_per_tool_call_result(48000)  # 40% of min(100000, 120000)

# Set the throttle sleep duration
llm_config.llm_rate_limitter.set_throttle_sleep(5.0)

# Set the token counter function
llm_config.llm_rate_limitter.set_token_counter_fn(lambda x: len(x.split()))
```

## Properties

### `max_requests_per_minute`
- **Description**: The maximum number of requests allowed per minute.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` or `ZRB_LLM_MAX_REQUEST_PER_MINUTE`

### `max_tokens_per_minute`
- **Description**: The maximum number of tokens allowed per minute.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_TOKENS_PER_MINUTE` or `ZRB_LLM_MAX_TOKEN_PER_MINUTE`

### `max_tokens_per_request`
- **Description**: The maximum number of tokens allowed per individual request.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_TOKENS_PER_REQUEST` or `ZRB_LLM_MAX_TOKEN_PER_REQUEST`

### `max_tokens_per_tool_call_result`
- **Description**: The maximum number of tokens allowed per tool call result.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT` or `ZRB_LLM_MAX_TOKEN_PER_TOOL_CALL_RESULT`

### `throttle_sleep`
- **Description**: The number of seconds to sleep when throttling is required.
- **Type**: `float`
- **Environment Variable**: `ZRB_LLM_THROTTLE_SLEEP`

### `history_summarization_token_threshold`
- **Description**: The token count threshold for history summarization.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD`

### `repo_analysis_extraction_token_threshold`
- **Description**: The token count threshold for repo analysis extraction.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD`

### `repo_analysis_summarization_token_threshold`
- **Description**: The token count threshold for repo analysis summarization.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD`

### `file_analysis_token_threshold`
- **Description**: The token count threshold for file analysis.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD` (previously `ZRB_LLM_FILE_ANALYSIS_TOKEN_LIMIT`)

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

### `set_max_tokens_per_tool_call_result(value: int)`
- **Description**: Sets the maximum number of tokens allowed per tool call result.

### `set_throttle_sleep(value: float)`
- **Description**: Sets the number of seconds to sleep when throttling is required.

### `set_token_counter_fn(fn: Callable[[str], int])`
- **Description**: Sets the function that counts the number of tokens in a given prompt.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)