🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Configuration for `zrb`

`zrb` uses `pydantic-ai` under the hood to manage Large Language Model (LLM) configurations. This document outlines how to configure the LLM for `zrb` using environment variables, with suggested values for common providers like OpenAI, Gemini, OpenRouter, and DeepSeek.

---

## Core Environment Variables

The following environment variables are used to configure the LLM in `zrb`:

- **`ZRB_LLM_MODEL`**: Specifies the LLM model to use (e.g., `gpt-4`, `gemini-pro`).
- **`ZRB_LLM_API_KEY`**: The API key for the LLM provider.
- **`ZRB_LLM_BASE_URL`**: The base URL for the LLM API (required for some providers or custom endpoints).
- **`ZRB_LLM_SYSTEM_PROMPT`**: Optional system prompt for the LLM.
- **`ZRB_LLM_INTERACTIVE_SYSTEM_PROMPT`**: Optional interactive system prompt.
- **`ZRB_LLM_PERSONA`**: Optional persona for the LLM.

---

## Advanced Configuration

### Access Control

These variables control the LLM's access to local files and the internet:

- **`ZRB_LLM_ACCESS_LOCAL_FILE`**: Set to `true` to allow the LLM to read local files (default: `false`).
- **`ZRB_LLM_ACCESS_INTERNET`**: Set to `true` to allow the LLM to access the internet (default: `false`).

### Rate Limiting

- **`ZRB_LLM_MAX_REQUESTS_PER_MINUTE`**: Limits the number of LLM API requests per minute (default: no limit).

### RAG Configuration

For Retrieval-Augmented Generation (RAG), use the following:

- **`ZRB_RAG_EMBEDDING_API_KEY`**: API key for the embedding service used in RAG.

### Summarization

`zrb` provides built-in support for summarization to manage large conversation histories efficiently. This feature is enabled by default with the following configurations:

#### Summarization
- **Trigger**: When the conversation history exceeds the token threshold (`ZRB_LLM_SUMMARIZATION_TOKEN_THRESHOLD`, default: 3000), the system automatically summarizes the history.
- **Default Prompt**: The summarization prompt is designed to condense the conversation while retaining key details.
- **Configuration**:
  - **`ZRB_LLM_SUMMARIZATION_TOKEN_THRESHOLD`**: Sets the token threshold for triggering summarization (default: 3000).
  - **`ZRB_LLM_SUMMARIZATION_PROMPT`**: Overrides the default summarization prompt if provided.

#### Workflow
1. **Summarization**: If the conversation history exceeds the token threshold, the system summarizes it.
2. **Continuation**: The enriched history is used for subsequent interactions.


---

## Provider-Specific Configurations

### OpenAI
```env
ZRB_LLM_MODEL=gpt-4
ZRB_LLM_API_KEY=your_openai_api_key
ZRB_LLM_BASE_URL=https://api.openai.com/v1
```

### Gemini
```env
ZRB_LLM_MODEL=gemini-2.5-flash
ZRB_LLM_API_KEY=your_gemini_api_key
ZRB_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
```

### OpenRouter
```env
ZRB_LLM_MODEL=openai/gpt-4
ZRB_LLM_API_KEY=your_openrouter_api_key
ZRB_LLM_BASE_URL=https://openrouter.ai/api/v1
```

### DeepSeek
```env
ZRB_LLM_MODEL=deepseek-chat
ZRB_LLM_API_KEY=your_deepseek_api_key
ZRB_LLM_BASE_URL=https://api.deepseek.com/v1
```

### Ollama
```env
ZRB_LLM_MODEL=llama2  # or any other model available in Ollama
ZRB_LLM_API_KEY=  # Typically not required for local Ollama instances
ZRB_LLM_BASE_URL=http://localhost:11434  # Default Ollama API endpoint
```

---

## Example `.env` File

Here’s an example `.env` file for OpenAI:
```env
# OpenAI Configuration
ZRB_LLM_MODEL=gpt-4
ZRB_LLM_API_KEY=sk-your-openai-key
ZRB_LLM_BASE_URL=https://api.openai.com/v1

# Optional Prompts
ZRB_LLM_PERSONA=You are a helpful assistant.

# Advanced Settings
ZRB_LLM_ACCESS_LOCAL_FILE=false
ZRB_LLM_ACCESS_INTERNET=false
ZRB_LLM_MAX_REQUESTS_PER_MINUTE=60
ZRB_RAG_EMBEDDING_API_KEY=your_rag_api_key

# Summarization and Context Enrichment
ZRB_LLM_SUMMARIZATION_TOKEN_THRESHOLD=3000
```

---

## Notes
- Ensure all required environment variables are set before running `zrb`.
- For providers like OpenAI and OpenRouter, the `ZRB_LLM_BASE_URL` is typically fixed. For self-hosted or custom endpoints, adjust this value accordingly.
- Refer to the provider’s documentation for the latest model names and API endpoints.

