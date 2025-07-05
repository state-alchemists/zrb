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

## Provider-Specific Configurations

### OpenAI
```env
ZRB_LLM_MODEL=gpt-4
ZRB_LLM_API_KEY=your_openai_api_key
ZRB_LLM_BASE_URL=https://api.openai.com/v1
```

### Gemini
```env
ZRB_LLM_MODEL=gemini-pro
ZRB_LLM_API_KEY=your_gemini_api_key
ZRB_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
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

---

## Example `.env` File

Here’s an example `.env` file for OpenAI:
```env
# OpenAI Configuration
ZRB_LLM_MODEL=gpt-4
ZRB_LLM_API_KEY=sk-your-openai-key
ZRB_LLM_BASE_URL=https://api.openai.com/v1

# Optional Prompts
ZRB_LLM_SYSTEM_PROMPT=You are a helpful assistant.
ZRB_LLM_INTERACTIVE_SYSTEM_PROMPT=How can I help you today?
```

---

## Notes
- Ensure all required environment variables are set before running `zrb`.
- For providers like OpenAI and OpenRouter, the `ZRB_LLM_BASE_URL` is typically fixed. For self-hosted or custom endpoints, adjust this value accordingly.
- Refer to the provider’s documentation for the latest model names and API endpoints.