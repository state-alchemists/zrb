🔖 [Documentation Home](../../README.md) > [Configuration](./) > LLM & Rate Limiter

# LLM & Rate Limiter Configuration

Zrb uses `pydantic-ai` to interface with a wide array of Large Language Models, granting out-of-the-box compatibility with OpenAI, Anthropic, Google Vertex, Ollama, DeepSeek, and more. This document provides an exhaustive list of environment variables to configure Zrb's AI features.

---

## 1. Core LLM Routing

These variables define which LLM Zrb uses for its primary reasoning and how it connects to the provider.

*   `ZRB_LLM_MODEL`: The primary LLM model to use for agent reasoning.
    *   Format: `provider:model-name`
    *   Examples: `openai:gpt-4o`, `anthropic:claude-3-5-sonnet-latest`, `ollama:llama3.1`, `google-vertex:gemini-1.5-pro`, `deepseek:deepseek-reasoner`, `groq:llama3-8b-8192`.
    *   Default: None (will depend on `pydantic-ai` defaults if not set)
*   `ZRB_LLM_SMALL_MODEL`: A faster, cheaper model used for background tasks like history summarization and quick analyses.
    *   Default: `openai:gpt-4o-mini`
*   `ZRB_LLM_API_KEY`: The API key for your chosen LLM provider.
    *   Default: None
*   `ZRB_LLM_BASE_URL`: An optional custom endpoint for the LLM API (e.g., pointing to OpenRouter or a local `vLLM` instance).
    *   Default: None

*(Note: Certain providers require installing optional `pip` extras, e.g., `pip install "zrb[anthropic]"` for Anthropic models. See [Installation Guide](../installation/installation.md) for details on extras.)*

---

## 2. Rate Limiting & Token Budgets

To prevent runaway AI loops, manage API costs, and stay within provider limits, Zrb enforces strict, configurable rate limits and token budgets.

*   `ZRB_LLM_MAX_REQUEST_PER_MINUTE`: Maximum number of LLM API requests allowed per minute.
    *   Default: `60`
*   `ZRB_LLM_MAX_TOKEN_PER_MINUTE`: Maximum number of total tokens (input + output) processed per minute.
    *   Default: `128000`
*   `ZRB_LLM_MAX_TOKEN_PER_REQUEST`: Hard limit on the context window size for any single LLM request.
    *   Default: `128000`
*   `ZRB_LLM_THROTTLE_SLEEP`: Number of seconds Zrb will pause if rate limits are hit.
    *   Default: `1.0`
*   `ZRB_USE_TIKTOKEN`: Whether to use the `tiktoken` library for more accurate token counting (recommended).
    *   Default: `1` (true)
*   `ZRB_TIKTOKEN_ENCODING`: The `tiktoken` encoding scheme to use (e.g., `cl100k_base`).
    *   Default: `cl100k_base`

---

## 3. Summarization Thresholds

Zrb automatically triggers background summarization agents when conversation history or individual message sizes grow too large. These thresholds dictate when compression happens to keep the context window manageable.

*   `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`: The token count that triggers summarization of the entire conversation history into a structured XML state snapshot.
    *   Default: 60% of `ZRB_LLM_MAX_TOKEN_PER_REQUEST`.
*   `ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`: The token count that triggers summarization of an *individual* large tool return (like a huge `read_file` output) or message before it enters the history.
    *   Default: 50% of `ZRB_LLM_CONVERSATIONAL_SUMMARIZATION_TOKEN_THRESHOLD`.
*   `ZRB_LLM_HISTORY_SUMMARIZATION_WINDOW`: Number of recent messages to keep completely verbatim in the conversation history during summarization.
    *   Default: `100`

---

## 4. System Prompts & Identity

You can heavily customize the LLM's behavior and identity by overriding its system prompts. Zrb looks for `.md` files (like `persona.md` or `mandate.md`) in specified directories.

*   `ZRB_LLM_ASSISTANT_NAME`: The name displayed for the AI assistant (e.g., "Pollux").
    *   Default: The root group name (e.g., `zrb`).
*   `ZRB_LLM_ASSISTANT_JARGON`: A tagline or motto for the AI assistant.
    *   Default: The root group description.
*   `ZRB_LLM_ASSISTANT_ASCII_ART`: The ASCII art to display as a banner for the AI assistant in the TUI.
    *   Default: `default` (uses Zrb's built-in ASCII art).
    *   Possible values: `none` (no ASCII art) or a custom ASCII art string.
*   `ZRB_ASCII_ART_DIR`: Directory containing additional custom ASCII art files.
    *   Default: `.zrb/llm/prompt`

### Prompt Customization Hierarchy
Zrb loads prompts with a multi-level override system, giving you fine-grained control. The first location found is used:
1.  **Local Directory Override**: Prompt files in a directory specified by `ZRB_LLM_PROMPT_DIR` (searched from the current directory up). This is the highest priority.
2.  **Environment Variable Override**: Directly set the content of a prompt via an environment variable. The format is `ZRB_LLM_PROMPT_<PROMPT_NAME_IN_UPPER_SNAKE_CASE>`. For example:
    ```bash
    export ZRB_LLM_PROMPT_PERSONA="You are a helpful pirate assistant, arrr!"
    ```
3.  **Base Directory Override**: Prompt files in a shared, organization-wide directory specified by `ZRB_LLM_BASE_PROMPT_DIR`.
4.  **Package Default**: The built-in prompts that come with Zrb (lowest priority).

Available prompt names (that can be overridden via env var or file) include:
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
You can toggle which foundational instructions are included in the final system prompt sent to the LLM:
*   `ZRB_LLM_INCLUDE_PERSONA`: Whether to include the AI's identity and role prompt. (Default `1`)
*   `ZRB_LLM_INCLUDE_MANDATE`: Whether to include the strict behavioral rules and operational guidelines. (Default `1`)
*   `ZRB_LLM_INCLUDE_GIT_MANDATE`: Whether to include git safety rules (only if inside a git repository). (Default `1`)
*   `ZRB_LLM_INCLUDE_JOURNAL`: Whether to inject the `index.md` content from the Journal system into the prompt. (Default `1`)
*   `ZRB_LLM_INCLUDE_SYSTEM_CONTEXT`: Whether to include system environment details (OS, time, etc.). (Default `1`)
*   `ZRB_LLM_INCLUDE_CLAUDE_SKILLS`: Whether to include skills from Claude-compatible `SKILL.md` files. (Default `1`)
*   `ZRB_LLM_INCLUDE_CLI_SKILLS`: Whether to include skills from Zrb's native CLI. (Default `0`)
*   `ZRB_LLM_INCLUDE_PROJECT_CONTEXT`: Whether to include project-specific `CLAUDE.md`/`AGENTS.md` instructions. (Default `1`)

---

## 5. Journal & Context Storage

Zrb maintains context across sessions using a Journal System and history storage.

*   `ZRB_LLM_JOURNAL_DIR`: The root directory where long-term Markdown notes and project context are saved by the LLM.
    *   Default: `~/.zrb/llm-notes/`
*   `ZRB_LLM_JOURNAL_INDEX_FILE`: The name of the main index file within `ZRB_LLM_JOURNAL_DIR` that gets automatically injected into prompts.
    *   Default: `index.md`
*   `ZRB_LLM_HISTORY_DIR`: The directory where raw conversational history is persisted between sessions.
    *   Default: `~/.zrb/llm-history/`

---

## 6. TUI Debugging

These variables control the verbosity of tool execution details in the interactive Terminal User Interface (TUI).

*   `ZRB_LLM_SHOW_TOOL_CALL_DETAIL`: Set to `true` to print the JSON arguments being passed to tools in real-time before execution.
    *   Default: `off`
*   `ZRB_LLM_SHOW_TOOL_CALL_RESULT`: Set to `true` to print the raw string returned by the tool execution.
    *   Default: `off`

---

## 7. RAG (Retrieval-Augmented Generation) Configuration

For advanced RAG capabilities with local or remote vector databases (like ChromaDB), these settings apply.

*   `ZRB_RAG_EMBEDDING_API_KEY`: API key for the embedding service (e.g., OpenAI, Voyage AI).
    *   Default: None
*   `ZRB_RAG_EMBEDDING_BASE_URL`: Base URL for the embedding API.
    *   Default: None
*   `ZRB_RAG_EMBEDDING_MODEL`: The embedding model to use.
    *   Default: `text-embedding-ada-002`
*   `ZRB_RAG_CHUNK_SIZE`: Size of text chunks for indexing in the vector database.
    *   Default: `1024`
*   `ZRB_RAG_OVERLAP`: Overlap size between RAG chunks to preserve context.
    *   Default: `128`
*   `ZRB_RAG_MAX_RESULT_COUNT`: Maximum number of search results to retrieve from the vector database.
    *   Default: `5`

---

## 8. Search Engine Configuration

These variables control which internet search engine Zrb's LLM tools use when performing web searches.

*   `ZRB_SEARCH_INTERNET_METHOD`: The search engine to use.
    *   Default: `serpapi`
    *   Possible values: `serpapi` (Google Search), `brave` (Brave Search), `searxng` (self-hosted privacy-focused).
*   `SERPAPI_KEY`: API key for SerpAPI (required if `serpapi` is chosen).
    *   Default: Empty
*   `SERPAPI_LANG`: Language for SerpAPI search results.
    *   Default: `en`
*   `SERPAPI_SAFE`: Safe search setting for SerpAPI (`on` or `off`).
    *   Default: `off`
*   `BRAVE_API_KEY`: API key for Brave Search (required if `brave` is chosen).
    *   Default: Empty
*   `BRAVE_API_LANG`: Language for Brave Search results.
    *   Default: `en`
*   `BRAVE_API_SAFE`: Safe search setting for Brave Search (`off`, `moderate`, `strict`).
    *   Default: `off`
*   `ZRB_SEARXNG_PORT`: Port for your self-hosted SearXNG instance.
    *   Default: `8080`
*   `ZRB_SEARXNG_BASE_URL`: Base URL for your self-hosted SearXNG instance.
    *   Default: `http://localhost:8080`
*   `ZRB_SEARXNG_LANG`: Language for SearXNG search results.
    *   Default: `en`
*   `ZRB_SEARXNG_SAFE`: Safe search setting for SearXNG (`0` for off, `1` for moderate, `2` for strict).
    *   Default: `0`

---

## 9. LLM Hooks Configuration

Environment variables for Zrb's powerful, Claude Code-compatible Hook System.

*   `ZRB_HOOKS_ENABLED`: Whether to enable the hook system globally.
    *   Default: `1` (true)
*   `ZRB_HOOKS_DIRS`: Colon-separated list of additional directories to scan for hook configuration files.
    *   Default: Empty
*   `ZRB_HOOKS_TIMEOUT`: Default timeout (in seconds) for synchronous hooks.
    *   Default: `30`
*   `ZRB_HOOKS_LOG_LEVEL`: Logging level for hook execution.
    *   Default: `INFO`

---
