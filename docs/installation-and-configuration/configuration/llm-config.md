🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Config

## Overview

The `LLMConfig` class in [`src/zrb/llm_config.py`](../../../src/zrb/llm_config.py) provides configuration settings for the Language Model (LLM) functionality. It includes default prompts, model settings, and other parameters required for LLM operations.

The configurations will be used as default values for `LLMTask` and other LLM utilities.


Zrb has a `llm_config` singleton that you can access and manipulate by importing `zrb.llm_config` in your `zrb_init.py`

```python
from zrb import llm_config

# Setup default LLM persona:
llm_config.set_persona(
    "You are Zoey, an AI assistant excel in coding, software engineering, and philosophy."

)
```

## Properties

### `default_model_name`
- **Description**: The default model name to be used for LLM operations.
- **Type**: `str | None`
- **Environment Variable**: `ZRB_LLM_MODEL`

### `default_model_base_url`
- **Description**: The base URL for the LLM API.
- **Type**: `str | None`
- **Environment Variable**: `ZRB_LLM_BASE_URL`

### `default_model_api_key`
- **Description**: The API key for the LLM service.
- **Type**: `str | None`
- **Environment Variable**: `ZRB_LLM_API_KEY`

### `default_persona`
- **Description**: The default persona for the assistant.
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_PERSONA`

### `default_system_prompt`
- **Description**: The default system prompt for the assistant, used for direct, one-shot commands. This prompt instructs the LLM to analyze the request, execute it, and provide a clear answer.
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_SYSTEM_PROMPT`

### `default_interactive_system_prompt`
- **Description**: The system prompt used for interactive sessions. This prompt outlines a core workflow: clarify, plan, execute, and confirm.
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_INTERACTIVE_SYSTEM_PROMPT`

### `default_special_instruction_prompt`
- **Description**: A prompt that provides specialized protocols, such as for software engineering tasks. It mandates safety, adherence to conventions, and a clear workflow (Understand, Plan, Implement, Verify).
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_SPECIAL_INSTRUCTION_PROMPT`

### `default_summarization_prompt`
- **Description**: The prompt used to instruct the "Conversation Historian" agent. It defines a protocol for integrating recent conversation history into a narrative summary and a list of recent turns.
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_SUMMARIZATION_PROMPT`

### `default_context_enrichment_prompt`
- **Description**: The prompt for the "Memory Curator" agent. It defines a protocol for extracting long-term, stable facts from a conversation and updating a Markdown-formatted `Long-Term Context` block.
- **Type**: `str`
- **Environment Variable**: `ZRB_LLM_CONTEXT_ENRICHMENT_PROMPT`

### `default_summarize_history`
- **Description**: Whether to summarize conversation history.
- **Type**: `bool`
- **Environment Variable**: `ZRB_LLM_SUMMARIZE_HISTORY`

### `default_history_summarization_token_threshold`
- **Description**: The token count threshold for history summarization.
- **Type**: `int`
- **Environment Variable**: `ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD`

### `default_model_settings`
- **Description**: The default model settings.
- **Type**: `ModelSettings | None`

### `default_model_provider`
- **Description**: The default model provider.
- **Type**: `Provider | str`

### `default_model`
- **Description**: The default model instance.
- **Type**: `Model | str | None`

## Methods

### `set_default_persona(persona: str)`
- **Description**: Sets the default persona.

### `set_default_system_prompt(system_prompt: str)`
- **Description**: Sets the default system prompt for one-shot commands.

### `set_default_interactive_system_prompt(interactive_system_prompt: str)`
- **Description**: Sets the default system prompt for interactive chat sessions.

### `set_default_special_instruction_prompt(special_instruction_prompt: str)`
- **Description**: Sets the default special instruction prompt.

### `set_default_summarization_prompt(summarization_prompt: str)`
- **Description**: Sets the default summarization prompt.

### `set_default_model_name(model_name: str)`
- **Description**: Sets the default model name.

### `set_default_model_api_key(model_api_key: str)`
- **Description**: Sets the default model API key.

### `set_default_model_base_url(model_base_url: str)`
- **Description**: Sets the default model base URL.

### `set_default_model_provider(provider: Provider | str)`
- **Description**: Sets the default model provider.

### `set_default_model(model: Model | str)`
- **Description**: Sets the default model.

### `set_default_summarize_history(summarize_history: bool)`
- **Description**: Sets whether to summarize history.

### `set_default_history_summarization_token_threshold(history_summarization_token_threshold: int)`
- **Description**: Sets the history summarization token threshold.

### `set_default_context_enrichment_token_threshold(context_enrichment_token_threshold: int)`
- **Description**: Sets the context enrichment token threshold.

### `set_default_model_settings(model_settings: ModelSettings)`
- **Description**: Sets the default model settings.

---
🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)