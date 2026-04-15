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
- [Rewind & Snapshots](#6-rewind--snapshots)
- [TUI Debugging](#7-tui-debugging)
- [Model Autocomplete](#8-model-autocomplete)
- [RAG Configuration](#9-rag-retrieval-augmented-generation-configuration)
- [Search Engine Configuration](#10-search-engine-configuration)
- [Hooks Configuration](#11-llm-hooks-configuration)
- [Skill & Agent Search Configuration](#12-skill--agent-search-configuration)
- [Timeout Configuration](#13-timeout-configuration)
- [Interval & Delay Configuration](#14-interval--delay-configuration)
- [Size & Limit Configuration](#15-size--limit-configuration)
- [Retry Configuration](#16-retry-configuration)
- [Pagination Configuration](#17-pagination-configuration)

---

## 1. Core LLM Routing

These variables define which LLM Zrb uses for its primary reasoning and how it connects to the provider.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MODEL` | Primary LLM model (`provider:model-name`) | `openai:gpt-4o` (if unset) |
| `ZRB_LLM_SMALL_MODEL` | Faster model for background tasks | Falls back to `ZRB_LLM_MODEL` |
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
| `ZRB_USE_TIKTOKEN` | Use tiktoken for accurate counting | `off` (false) |
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
| `ZRB_LLM_ASSISTANT_ASCII_ART` | ASCII banner art name | `default` (built-in) |
| `ZRB_ASCII_ART_DIR` | Directory for custom ASCII art files | `.zrb/ascii-art` |

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
| `ZRB_LLM_INCLUDE_TOOL_GUIDANCE` | Include per-tool usage guidance | `1` |
| `ZRB_LLM_INCLUDE_CLAUDE_SKILLS` | Include Claude skills | `1` |
| `ZRB_LLM_INCLUDE_CLI_SKILLS` | Include CLI skills | `0` |
| `ZRB_LLM_INCLUDE_PROJECT_CONTEXT` | Include project docs | `1` |

### Tool Guidance

The tool guidance section tells the LLM when and how to use each available tool. All built-in tools ship with guidance pre-registered. When you add a custom tool, register its guidance so the LLM knows how to use it:

```python
from zrb import LLMChatTask

task = LLMChatTask(name="chat")
task.add_tool(my_tool)

task.prompt_manager.add_tool_guidance(
    group="My Domain",
    name="MyTool",
    use_when="When the user asks about inventory or stock levels",
    key_rule="Always filter by warehouse_id; an empty result means no stock, not an error.",
)
```

Guidance entries for tools that are not registered on the task are automatically suppressed at runtime, so the prompt never grows stale. Set `ZRB_LLM_INCLUDE_TOOL_GUIDANCE=0` to disable the entire section if you manage tool instructions another way.

---

## 5. Journal & Context Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_JOURNAL_DIR` | Long-term notes directory | `~/.zrb/llm-notes/` |
| `ZRB_LLM_JOURNAL_INDEX_FILE` | Main index file name | `index.md` |
| `ZRB_LLM_HISTORY_DIR` | Conversation history directory | `~/.zrb/llm-history/` |

---

## 6. Rewind & Snapshots

Zrb can take a full filesystem snapshot before each AI turn, letting you restore any previous state mid-session with `/rewind`.

**How it works:**

1. Before each AI response, Zrb copies your working directory into an isolated shadow git repository (`<ZRB_LLM_SNAPSHOT_DIR>/<session-name>/`).
2. Each snapshot is a git commit in that shadow repo — completely separate from your project's own git history.
3. `/rewind` lists all snapshots; `/rewind <n>` or `/rewind <sha>` restores both the filesystem and conversation history to the selected point.

> **Note:** Rewind is off by default. Enable it only for sessions where you want undo capability — snapshotting a large working directory (e.g., one containing `node_modules/`) will be slow.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_ENABLE_REWIND` | Enable filesystem snapshots and `/rewind` command | `off` |
| `ZRB_LLM_SNAPSHOT_DIR` | Directory to store shadow git repos for each session | `~/.zrb/llm-snapshots/` |

### Python API

```python
from zrb import LLMChatTask

task = LLMChatTask(
    name="chat",
    enable_rewind=True,           # None → falls back to ZRB_LLM_ENABLE_REWIND
    snapshot_dir="/tmp/my-snaps", # None → falls back to ZRB_LLM_SNAPSHOT_DIR
)
```

### `/rewind` commands

| Input | Effect |
|-------|--------|
| `/rewind` | List all snapshots (newest first) with index, short SHA, timestamp, and user message |
| `/rewind <n>` | Restore snapshot number `n` from the list (1-based) |
| `/rewind <sha>` | Restore by full or partial SHA |

Restore rewinds **both** the working directory files **and** the conversation history to the state captured at that snapshot, so the AI's context stays consistent with the restored files.

### Shadow repo layout

```
~/.zrb/llm-snapshots/
└── <session-name>/
    └── .git/          ← isolated git repo (never touches your project git)
    └── <files ...>    ← mirror of your working directory at each turn
```

---

## 7. TUI Debugging

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SHOW_TOOL_CALL_DETAIL` | Print tool arguments before execution | `off` |
| `ZRB_LLM_SHOW_TOOL_CALL_RESULT` | Print raw tool return values | `off` |

---

## 8. Model Autocomplete

When using the `/model` command in LLM chat, Zrb provides autocomplete suggestions from different model sources. These variables control which sources appear in the suggestions.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SHOW_OLLAMA_MODELS` | Include Ollama models in autocomplete | `on` |
| `ZRB_LLM_SHOW_PYDANTIC_AI_MODELS` | Include pydantic-ai KnownModelName models in autocomplete | `on` |

### Python API

```python
from zrb import LLMChatTask

task = LLMChatTask(
    name="chat",
    show_ollama_models=False,        # None → falls back to ZRB_LLM_SHOW_OLLAMA_MODELS
    show_pydantic_ai_models=False,    # None → falls back to ZRB_LLM_SHOW_PYDANTIC_AI_MODELS
)
```

### Use Cases

- **Disable Ollama models** when Ollama is not installed or not running, to avoid connection errors during autocomplete
- **Disable pydantic-ai models** to show only custom model names configured via `custom_model_names` parameter

---

## 9. RAG (Retrieval-Augmented Generation) Configuration

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

## 10. Search Engine Configuration

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

## 11. LLM Hooks Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_HOOKS_ENABLED` | Enable hook system globally | `1` |
| `ZRB_HOOKS_DIRS` | Additional hook directories (colon-separated) | (empty) |
| `ZRB_HOOKS_TIMEOUT` | Default timeout for hook execution (ms) | `30000` |
| `ZRB_HOOKS_LOG_LEVEL` | Logging level for hooks | `INFO` |

---

## 12. Skill & Agent Search Configuration

These variables control where Zrb searches for skills and agents.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SEARCH_PROJECT` | Search project dirs (filesystem root → cwd) for config dir names | `on` |
| `ZRB_LLM_SEARCH_HOME` | Search home directory (`~/.claude/`, `~/.zrb/`) | `on` |
| `ZRB_LLM_CONFIG_DIR_NAMES` | Config subdirectory names to look for in each dir (colon-separated) | `.claude:.zrb` |
| `ZRB_LLM_BASE_SEARCH_DIRS` | Explicit base dirs containing `skills/`, `agents/`, `plugins/` | (empty) |
| `ZRB_LLM_EXTRA_SKILL_DIRS` | Additional direct skill directories | (empty) |
| `ZRB_LLM_EXTRA_AGENT_DIRS` | Additional direct agent directories | (empty) |
| `ZRB_LLM_PLUGIN_DIRS` | Additional plugin directories | (empty) |

### Search Priority

Zrb searches for skills/agents in this order (highest to lowest priority):

1. **User Home** - `~/.claude/`, `~/.zrb/` + plugins within
2. **Project Traversal** - Filesystem root → cwd for each config dir name + plugins within
3. **Configured Plugins** - Directories in `ZRB_LLM_PLUGIN_DIRS`
4. **Base Search Dirs** - Directories in `ZRB_LLM_BASE_SEARCH_DIRS` + plugins within
5. **Extra Direct Dirs** - `ZRB_LLM_EXTRA_SKILL_DIRS`, `ZRB_LLM_EXTRA_AGENT_DIRS`
6. **Builtin** - Built-in skills/agents (always included)

### Directory Structure

```
~/.claude/
├── skills/
│   └── my-skill/
│       └── SKILL.md
├── agents/
│   └── my-agent/
│       └── AGENT.md
└── plugins/
    └── my-plugin/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── skills/
        │   └── plugin-skill/
        │       └── SKILL.md
        └── agents/
            └── plugin-agent/
                └── AGENT.md
```

---

## 13. Timeout Configuration

All timeout values are in **milliseconds**. Divide by 1000 to convert to seconds.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_SSE_KEEPALIVE_TIMEOUT` | How long to wait before sending an SSE keepalive ping (ms) | `60000` |
| `ZRB_WEB_SHUTDOWN_TIMEOUT` | Graceful web server shutdown timeout (ms) | `10000` |
| `ZRB_LLM_REQUEST_TIMEOUT` | Maximum time to wait for an LLM response (ms) | `300000` |
| `ZRB_LLM_INPUT_QUEUE_TIMEOUT` | Polling interval for the chat input queue (ms) | `500` |
| `ZRB_LLM_SHELL_KILL_WAIT_TIMEOUT` | Time to wait for a shell process to exit after SIGTERM before SIGKILL (ms) | `5000` |
| `ZRB_LLM_WEB_PAGE_TIMEOUT` | Playwright page load timeout (ms) | `30000` |
| `ZRB_LLM_WEB_HTTP_TIMEOUT` | HTTP request timeout for web tools and search (ms) | `30000` |
| `ZRB_LLM_MODEL_FETCH_TIMEOUT` | Timeout for fetching Ollama model list (ms) | `5000` |
| `ZRB_CMD_CLEANUP_TIMEOUT` | Time to wait for a process to exit after interrupt before killing (ms) | `2000` |
| `ZRB_LLM_GIT_CMD_TIMEOUT` | Timeout for git commands used to build system context (ms) | `1000` |

---

## 14. Interval & Delay Configuration

All interval and delay values are in **milliseconds**.

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_UI_STATUS_INTERVAL` | Polling interval for the TUI status loop (ms) | `1000` |
| `ZRB_LLM_UI_LONG_STATUS_INTERVAL` | Interval for updating slow-changing info (CWD, git branch) in TUI (ms) | `60000` |
| `ZRB_LLM_UI_REFRESH_INTERVAL` | Prompt-toolkit application refresh rate (ms) | `500` |
| `ZRB_LLM_UI_FLUSH_INTERVAL` | How often buffered output is flushed to event-driven UIs (ms) | `500` |
| `ZRB_SCHEDULER_TICK_INTERVAL` | How often the Scheduler task checks its cron pattern (ms) | `60000` |
| `ZRB_HTTP_CHECK_INTERVAL` | Default polling interval for `HttpCheck` tasks (ms) | `5000` |
| `ZRB_TCP_CHECK_INTERVAL` | Default polling interval for `TcpCheck` tasks (ms) | `5000` |
| `ZRB_TASK_READINESS_DELAY` | Initial delay before starting readiness checks (ms) | `500` |

---

## 15. Size & Limit Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MAX_COMPLETION_FILES` | Maximum files scanned for path autocompletion | `5000` |
| `ZRB_LLM_MAX_OUTPUT_CHARS` | Maximum characters returned by shell command and file read tools | `100000` |
| `ZRB_LLM_FILE_READ_LINES` | Lines to preserve at head and tail when truncating file reads | `1000` |
| `ZRB_LLM_HISTORY_MAX_DISPLAY_CHARS` | Maximum characters shown by the `/history` command | `5000` |
| `ZRB_LLM_HISTORY_TRUNCATE_LENGTH` | Maximum chars per field when formatting history entries | `100` |
| `ZRB_LLM_PROJECT_DOC_MAX_CHARS` | Maximum chars loaded from each project doc file (e.g. CLAUDE.md) | `8000` |
| `ZRB_CMD_BUFFER_LIMIT` | Asyncio subprocess read-buffer limit in bytes | `102400` |
| `ZRB_LLM_UI_MAX_BUFFER_SIZE` | Maximum buffered output chars before a forced flush (event-driven UIs) | `2000` |

---

## 16. Retry Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_LLM_MAX_CONTEXT_RETRIES` | Maximum retries when the LLM returns a context-window error | `5` |
| `ZRB_LLM_TOOL_MAX_RETRIES` | Maximum retries for individual tool calls | `3` |
| `ZRB_LLM_MCP_MAX_RETRIES` | Maximum retries when connecting to MCP servers | `3` |

---

## 17. Pagination Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ZRB_WEB_SESSION_PAGE_SIZE` | Default page size for chat session listings | `20` |
| `ZRB_WEB_API_PAGE_SIZE` | Default page size for generic API list endpoints | `20` |
| `ZRB_WEB_TASK_SESSION_PAGE_SIZE` | Default page size for task session listings | `10` |

---