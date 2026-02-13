🔖 [Home](../../../README.md) > [Documentation](../../README.md) > [Installation and Configuration](../README.md) > [Configuration](./README.md)

# LLM Configuration for `zrb`

`zrb` uses `pydantic-ai` under the hood to manage Large Language Model (LLM) configurations. This document outlines how to configure the LLM for `zrb` using environment variables.

---

## Core Environment Variables

The following environment variables are used to configure the LLM in `zrb`:

- **`ZRB_LLM_MODEL`**: Specifies the primary LLM model to use (e.g., `openai:gpt-4o`, `deepseek:deepseek-reasoner`, `ollama:llama3.1`).
- **`ZRB_LLM_SMALL_MODEL`**: Specifies a smaller/faster model for summarization and auxiliary tasks (e.g., `openai:gpt-4o-mini`). Defaults to `openai:gpt-4o-mini`.
- **`ZRB_LLM_API_KEY`**: The API key for the LLM provider.
- **`ZRB_LLM_BASE_URL`**: The base URL for the LLM API (required for some providers or custom endpoints).

## Optional Dependencies (Extras)

Zrb supports additional LLM providers via optional dependencies. Install them using pip extras:

```bash
# Install with specific provider support
pip install "zrb[xai]"           # xAI (Grok) support
pip install "zrb[voyageai]"      # Voyage AI embeddings and RAG
pip install "zrb[anthropic]"     # Anthropic Claude
pip install "zrb[cohere]"        # Cohere
pip install "zrb[groq]"          # Groq
pip install "zrb[mistral]"       # Mistral AI
pip install "zrb[huggingface]"   # Hugging Face Hub inference
pip install "zrb[rag]"           # RAG capabilities (ChromaDB)
pip install "zrb[all]"           # All optional dependencies
```

See the [Provider-Specific Configurations](#provider-specific-configurations) section for configuration details.

---

## Prompt Customization

`zrb` allows you to override its built-in system prompts by creating a custom prompt directory.

- **`ZRB_LLM_PROMPT_DIR`**: The directory where custom prompts are stored (default: `.zrb/llm/prompt` in your project root).

### How it Works

When `zrb` needs a system prompt, it first checks `ZRB_LLM_PROMPT_DIR` for a corresponding `.md` file. If the file exists, it overrides the default built-in prompt.

Available prompt names (file names) include:
- `persona.md`: Defines the AI assistant's personality and role.
- `mandate.md`: Defines the core rules and safety constraints.
- `summarizer.md`: System prompt for summarizing conversation history.
- `file_extractor.md`: System prompt for extracting information from files.
- `repo_extractor.md`: System prompt for extracting repository structures.
- `repo_summarizer.md`: System prompt for summarizing repository analysis.

---

## Advanced Configuration

### Tool Execution Visibility

These variables control the verbosity of the tool execution logs in the CLI:

- **`ZRB_LLM_SHOW_TOOL_CALL_DETAIL`**: Set to `1` or `true` to show the arguments being prepared for a tool call (default: `0`).
- **`ZRB_LLM_SHOW_TOOL_CALL_RESULT`**: Set to `1` or `true` to show the result returned by a tool (default: `0`).

### Skill & Instruction Discovery

`zrb` automatically scans for instructions and "skills" in the following locations:

1.  **Global Skills**: `~/.claude/skills/` (Looks for `SKILL.md` files).
2.  **Project Skills**: `.claude/skills/` in any directory from the filesystem root down to the current working directory.
3.  **Project Instructions**: `CLAUDE.md` or `AGENTS.md` in any directory from root to current directory.
4.  **Local Skills**: Any `SKILL.md` or `*.skill.md` file found recursively in the current project directory.
5.  **Plugin Directories**: Custom directories specified via `ZRB_LLM_PLUGIN_DIRS` (colon-separated paths) containing `agents/` and `skills/` subdirectories.

Use the `activate_skill` tool in chat to load these instructions.

### Rate Limiting and Token Management

These variables help you manage costs and stay within provider rate limits:

- **`ZRB_LLM_MAX_REQUEST_PER_MINUTE`**: Limits the number of LLM API requests per minute (default: `60`). Also accepts `ZRB_LLM_MAX_REQUESTS_PER_MINUTE` for backward compatibility.
- **`ZRB_LLM_MAX_TOKEN_PER_MINUTE`**: Limits the total tokens processed per minute (default: `128000`). Also accepts `ZRB_LLM_MAX_TOKENS_PER_MINUTE` for backward compatibility.
- **`ZRB_LLM_MAX_TOKEN_PER_REQUEST`**: Limits the tokens per individual request (default: `128000`). Also accepts `ZRB_LLM_MAX_TOKENS_PER_REQUEST` for backward compatibility.
- **`ZRB_LLM_THROTTLE_SLEEP`**: Seconds to sleep when throttling is triggered (default: `1.0`).

#### Analysis Thresholds
- **`ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD`**: Max tokens for repo extraction (default: 40% of request limit).
- **`ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD`**: Max tokens for repo summarization (default: 40% of request limit).
- **`ZRB_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD`**: Max tokens for analyzing a single file (default: 40% of request limit).

### RAG Configuration

For Retrieval-Augmented Generation (RAG), use the following:

- **`ZRB_RAG_EMBEDDING_API_KEY`**: API key for the embedding service.
- **`ZRB_RAG_EMBEDDING_MODEL`**: The embedding model to use (default: `text-embedding-ada-002`).
- **`ZRB_RAG_CHUNK_SIZE`**: Size of text chunks for indexing (default: `1024`).
- **`ZRB_RAG_OVERLAP`**: Overlap between chunks (default: `128`).
- **`ZRB_RAG_MAX_RESULT_COUNT`**: Number of results to retrieve (default: `5`).

### Search Engine Configuration

These variables control the internet search capabilities of the LLM:

- **`ZRB_SEARCH_INTERNET_METHOD`**: The search engine to use (`serpapi`, `brave`, or `searxng`). Default: `serpapi`.
- **`SERPAPI_KEY`**: API key for Google Search via SerpAPI.
- **`BRAVE_API_KEY`**: API key for Brave Search.
- **`ZRB_SEARXNG_BASE_URL`**: Base URL for a self-hosted SearXNG instance.

### Summarization and Context

`zrb` automatically summarizes conversation history to manage context window usage using a two-tier summarization system:

- **`ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW`**: Number of recent messages to keep in the "recent history" block (default: `100`).
- **`ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`**: The token count that triggers summarization of entire conversation history into structured XML state snapshots (default: 60% of request limit). Also accepts `ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD` for backward compatibility.
- **`ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`**: The token count that triggers summarization of individual large tool call results and messages (default: 50% of conversational threshold).
- **`ZRB_LLM_HISTORY_DIR`**: Directory to store conversation history (default: `~/.zrb/llm-history`).

---

## Provider-Specific Configurations

### OpenAI
```env
ZRB_LLM_MODEL=openai:gpt-4o
ZRB_LLM_API_KEY=your_openai_api_key
```

### Gemini (Google Vertex AI)
```env
ZRB_LLM_MODEL=google-vertex:gemini-1.5-pro
# Google Vertex AI typically uses Application Default Credentials (ADC)
# Ensure you have run `gcloud auth application-default login`
```

### OpenRouter
```env
ZRB_LLM_MODEL=openai:gpt-4o
ZRB_LLM_API_KEY=your_openrouter_api_key
ZRB_LLM_BASE_URL=https://openrouter.ai/api/v1
```

### DeepSeek
```env
ZRB_LLM_MODEL=deepseek:deepseek-reasoner
DEEPSEEK_API_KEY=your_deepseek_api_key
# Note: DeepSeek models use their built-in provider, no base URL needed for official API
```

### Ollama (Local)
```env
ZRB_LLM_MODEL=ollama:llama3.1
OLLAMA_API_KEY=sk-your-ollama-api-key
```

### xAI (Grok)
```env
ZRB_LLM_MODEL=xai:grok-beta
XAI_API_KEY=your_xai_api_key
```

### Voyage AI
```env
ZRB_LLM_MODEL=voyage:voyage-3
VOYAGE_API_KEY=your_voyage_api_key
```

---

## Example `.env` File

Here’s an example `.env` file for a typical setup:

```env
# Core LLM Config
ZRB_LLM_MODEL=openai:gpt-4o
ZRB_LLM_SMALL_MODEL=openai:gpt-4o-mini
OPENAI_API_KEY=sk-your-openai-key

# Prompt Customization
ZRB_LLM_PROMPT_DIR=.zrb/llm/prompt

# Plugin Directories
# ZRB_LLM_PLUGIN_DIRS=/path/to/plugins:/another/path

# Tool Debugging
ZRB_LLM_SHOW_TOOL_CALL_DETAIL=true
ZRB_LLM_SHOW_TOOL_CALL_RESULT=true

# Rate Limiting
ZRB_LLM_MAX_REQUEST_PER_MINUTE=60

# RAG
ZRB_RAG_EMBEDDING_API_KEY=your_rag_api_key
```

## Interacting with LLM

```sh
# One shot request
zrb llm chat --message "zip project directory into project.zip"

# Chat session
zrb llm chat --session my-session
```
