🔖 [Documentation Home](../../README.md) > [Configuration](./) > LLM & Rate Limiter

# LLM & Rate Limiter Configuration

Zrb uses `pydantic-ai` to interface with a wide array of Large Language Models, granting out-of-the-box compatibility with OpenAI, Anthropic, Google Vertex, Ollama, DeepSeek, and more. This document provides an exhaustive list of environment variables to configure Zrb's AI features.

---

## Table of Contents

- [Core LLM Routing](#1-core-llm-routing)
- [Rate Limiting & Token Budgets](#2-rate-limiting--token-budgets)
- [Summarization Thresholds](#3-summarization-thresholds)
- [System Prompts & Identity](#4-system-prompts--identity)
- [Journal & Context Storage](#5-journal--context-storage)
- [TUI Debugging](#6-tui-debugging)
- [RAG Configuration](#7-rag-retrieval-augmented-generation-configuration)
- [Search Engine Configuration](#8-search-engine-configuration)
- [Hooks Configuration](#9-llm-hooks-configuration)

---

## 1. Core LLM Routing

These variables define which LLM Zrb uses for its primary reasoning and how it connects to the provider.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MODEL` | Primary LLM model (`provider:model-name`) | None |
| `ZRB_LLM_SMALL_MODEL` | Faster model for background tasks | `openai:gpt-4o-mini` |
| `ZRB_LLM_API_KEY` | API key for your LLM provider | None |
| `ZRB_LLM_BASE_URL` | Custom endpoint URL | None |

### Supported Providers

| Provider | Model Format | Pip Extra |
|----------|-------------|-----------|
| OpenAI | `openai:gpt-4o` | (default) |
| Anthropic | `anthropic:claude-3-5-sonnet-latest` | `pip install "zrb[anthropic]"` |
| Google Vertex | `google-vertex:gemini-1.5-pro` | `pip install "zrb[google]"` |
| Ollama | `ollama:llama3.1` | (default) |
| DeepSeek | `deepseek:deepseek-reasoner` | (default) |
| Groq | `groq:llama3-8b-8192` | (default) |

---

## 2. Rate Limiting & Token Budgets

To prevent runaway AI loops, manage API costs, and stay within provider limits, Zrb enforces strict, configurable rate limits and token budgets.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MAX_REQUEST_PER_MINUTE` | Max API requests per minute | `60` |
| `ZRB_LLM_MAX_TOKEN_PER_MINUTE` | Max tokens processed per minute | `128000` |
| `ZRB_LLM_MAX_TOKEN_PER_REQUEST` | Hard context window limit | `128000` |
| `ZRB_LLM_THROTTLE_SLEEP` | Seconds to pause when rate-limited | `1.0` |
| `ZRB_USE_TIKTOKEN` | Use tiktoken for accurate counting | `1` |
| `ZRB_TIKTOKEN_ENCODING` | Tiktoken encoding scheme | `cl100k_base` |

---

## 3. Summarization Thresholds

Zrb automatically triggers background summarization agents when conversation history or individual message sizes grow too large.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD` | Token count triggering full history summarization | 60% of `MAX_TOKEN_PER_REQUEST` |
| `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD` | Token count triggering individual message summarization | 50% of conversational threshold |
| `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW` | Recent messages to keep verbatim | `100` |

---

## 4. System Prompts & Identity

You can heavily customize the LLM's behavior and identity by overriding its system prompts.

### Identity Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_ASSISTANT_NAME` | Display name for AI assistant | Root group name |
| `ZRB_LLM_ASSISTANT_JARGON` | Tagline or motto | Root group description |
| `ZRB_LLM_ASSISTANT_ASCII_ART` | ASCII banner art | `default` (built-in) |
| `ZRB_ASCII_ART_DIR` | Directory for custom ASCII art | `.zrb/llm/prompt` |

### Prompt Customization Hierarchy

Zrb loads prompts with a multi-level override system (first found wins):

| Priority | Location | Description |
|----------|----------|-------------|
| 1 (highest) | `ZRB_LLM_PROMPT_DIR` | Local directory override |
| 2 | `ZRB_LLM_PROMPT_<NAME>` | Environment variable |
| 3 | `ZRB_LLM_BASE_PROMPT_DIR` | Shared/org directory |
| 4 (lowest) | Package default | Built-in prompts |

### Overridable Prompts

- `persona`
- `mandate`
- `git_mandate`
- `conversational_summarizer`
- `message_summarizer`
- `journal_mandate`
- `file_extractor`
- `repo_extractor`
- `repo_summarizer`
- `web_summarizer`

### Prompt Component Toggles

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_INCLUDE_PERSONA` | Include AI identity prompt | `1` |
| `ZRB_LLM_INCLUDE_MANDATE` | Include behavioral rules | `1` |
| `ZRB_LLM_INCLUDE_GIT_MANDATE` | Include git safety rules | `1` |
| `ZRB_LLM_INCLUDE_JOURNAL` | Inject journal content | `1` |
| `ZRB_LLM_INCLUDE_SYSTEM_CONTEXT` | Include OS/time details | `1` |
| `ZRB_LLM_INCLUDE_CLAUDE_SKILLS` | Include Claude skills | `1` |
| `ZRB_LLM_INCLUDE_CLI_SKILLS` | Include CLI skills | `0` |
| `ZRB_LLM_INCLUDE_PROJECT_CONTEXT` | Include project docs | `1` |

---

## 5. Journal & Context Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_JOURNAL_DIR` | Long-term notes directory | `~/.zrb/llm-notes/` |
| `ZRB_LLM_JOURNAL_INDEX_FILE` | Main index file name | `index.md` |
| `ZRB_LLM_HISTORY_DIR` | Conversation history directory | `~/.zrb/llm-history/` |

---

## 6. TUI Debugging

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SHOW_TOOL_CALL_DETAIL` | Print tool arguments before execution | `off` |
| `ZRB_LLM_SHOW_TOOL_CALL_RESULT` | Print raw tool return values | `off` |

---

## 7. RAG (Retrieval-Augmented Generation) Configuration

For advanced RAG capabilities with vector databases like ChromaDB.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_RAG_EMBEDDING_API_KEY` | API key for embedding service | None |
| `ZRB_RAG_EMBEDDING_BASE_URL` | Embedding API URL | None |
| `ZRB_RAG_EMBEDDING_MODEL` | Embedding model | `text-embedding-ada-002` |
| `ZRB_RAG_CHUNK_SIZE` | Text chunk size | `1024` |
| `ZRB_RAG_OVERLAP` | Chunk overlap size | `128` |
| `ZRB_RAG_MAX_RESULT_COUNT` | Max search results | `5` |

---

## 8. Search Engine Configuration

These variables control which internet search engine Zrb's LLM tools use.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_SEARCH_INTERNET_METHOD` | Search engine (`serpapi`, `brave`, `searxng`) | `serpapi` |

### SerpAPI (Google)

| Variable | Description | Default |
|----------|-------------|---------|
| `SERPAPI_KEY` | API key | (required) |
| `SERPAPI_LANG` | Language | `en` |
| `SERPAPI_SAFE` | Safe search | `off` |

### Brave Search

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAVE_API_KEY` | API key | (required) |
| `BRAVE_API_LANG` | Language | `en` |
| `BRAVE_API_SAFE` | Safe search | `off` |

### SearXNG (Self-hosted)

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_SEARXNG_PORT` | Port | `8080` |
| `ZRB_SEARXNG_BASE_URL` | Base URL | `http://localhost:8080` |
| `ZRB_SEARXNG_LANG` | Language | `en` |
| `ZRB_SEARXNG_SAFE` | Safe search | `0` |

---

## 9. LLM Hooks Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_HOOKS_ENABLED` | Enable hook system globally | `1` |
| `ZRB_HOOKS_DIRS` | Additional hook directories (colon-separated) | (empty) |
| `ZRB_HOOKS_TIMEOUT` | Default timeout for synchronous hooks | `30` |
| `ZRB_HOOKS_LOG_LEVEL` | Logging level for hooks | `INFO` |

---