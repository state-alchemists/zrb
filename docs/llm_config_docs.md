# LLM Configuration Documentation

## Overview
The `LLMConfig` class provides configuration settings for the Language Model (LLM) functionality. It includes default prompts, model settings, and other parameters required for LLM operations.

## Properties

### `default_model_name`
- **Description**: The default model name to be used for LLM operations.
- **Type**: `str | None`

### `default_model_base_url`
- **Description**: The base URL for the LLM API.
- **Type**: `str | None`

### `default_model_api_key`
- **Description**: The API key for the LLM service.
- **Type**: `str | None`

### `default_persona`
- **Description**: The default persona for the assistant.
- **Type**: `str`

### `default_system_prompt`
- **Description**: The default system prompt for the assistant.
- **Type**: `str`

### `default_special_instruction_prompt`
- **Description**: The default prompt for special instructions.
- **Type**: `str`

### `default_summarization_prompt`
- **Description**: The default prompt for summarization tasks.
- **Type**: `str`

### `default_context_enrichment_prompt`
- **Description**: The default prompt for context enrichment.
- **Type**: `str`

### `default_summarize_history`
- **Description**: Whether to summarize conversation history.
- **Type**: `bool`

### `default_history_summarization_threshold`
- **Description**: The threshold for history summarization.
- **Type**: `int`

### `default_enrich_context`
- **Description**: Whether to enrich context.
- **Type**: `bool`

### `default_context_enrichment_threshold`
- **Description**: The threshold for context enrichment.
- **Type**: `int`

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
- **Description**: Sets the default system prompt.

### `set_default_special_instruction_prompt(special_instruction_prompt: str)`
- **Description**: Sets the default special instruction prompt.

### `set_default_summarization_prompt(summarization_prompt: str)`
- **Description**: Sets the default summarization prompt.

### `set_default_context_enrichment_prompt(context_enrichment_prompt: str)`
- **Description**: Sets the default context enrichment prompt.

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

### `set_default_history_summarization_threshold(history_summarization_threshold: int)`
- **Description**: Sets the history summarization threshold.

### `set_default_enrich_context(enrich_context: bool)`
- **Description**: Sets whether to enrich context.

### `set_default_context_enrichment_threshold(context_enrichment_threshold: int)`
- **Description**: Sets the context enrichment threshold.

### `set_default_model_settings(model_settings: ModelSettings)`
- **Description**: Sets the default model settings.

## Example Usage
```python
from zrb.llm_config import llm_config

# Set a custom model name
llm_config.set_default_model_name("gpt-4")

# Get the default system prompt
print(llm_config.default_system_prompt)
```