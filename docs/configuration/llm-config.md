🔖 [Documentation Home](../README.md) > [Configuration](./) > LLM Configuration

# LLM Configuration

Zrb talks to LLMs through `pydantic-ai`, so OpenAI, Anthropic, Google Vertex, Ollama, DeepSeek and more work out of the box. Every environment variable for Zrb's AI features is listed on one of the pages below.

`Model`, `ModelSettings`, and the `capabilities` list accepted by `LLMTask`/`LLMChatTask` (see [Model, Model Settings & Capabilities](../task-types/llmchat-task.md#model-model-settings--capabilities)) are pydantic-ai's own types, passed through unchanged; [pydantic-ai's documentation](https://ai.pydantic.dev) is the source of truth for what each provider accepts. These pages cover the zrb-side knobs on top: routing, credentials, rate limits, and the defaults zrb applies first.

| Page | Covers |
|---|---|
| [LLM Models, Providers & Rate Limits](llm-models.md) | [Core LLM Routing](llm-models.md#core-llm-routing), [Rate Limiting & Token Budgets](llm-models.md#rate-limiting--token-budgets), [Model Autocomplete](llm-models.md#model-autocomplete), [Retry Configuration](llm-models.md#retry-configuration) |
| [LLM System Prompts](llm-prompts.md) | [System Prompts & Identity](llm-prompts.md#system-prompts--identity) |
| [LLM Conversation Context](llm-context.md) | [Summarization Thresholds](llm-context.md#summarization-thresholds), [Journal & Context Storage](llm-context.md#journal--context-storage), [Rewind & Snapshots](llm-context.md#rewind--snapshots) |
| [LLM Tools & Extensions](llm-tools.md) | [RAG (Retrieval-Augmented Generation) Configuration](llm-tools.md#rag-retrieval-augmented-generation-configuration), [Search Engine Configuration](llm-tools.md#search-engine-configuration), [LLM Hooks Configuration](llm-tools.md#llm-hooks-configuration), [Skill & Agent Search Configuration](llm-tools.md#skill--agent-search-configuration), [LSP Server Selection](llm-tools.md#lsp-server-selection), [Sandbox Configuration](llm-tools.md#sandbox-configuration) |
| [LLM Chat TUI](llm-tui.md) | [TUI Debugging](llm-tui.md#tui-debugging), [Slash Command Aliases](llm-tui.md#slash-command-aliases), [TUI Color Styles](llm-tui.md#tui-color-styles) |
| [LLM Timeouts & Limits](llm-limits.md) | [Timeout Configuration](llm-limits.md#timeout-configuration), [Interval & Delay Configuration](llm-limits.md#interval--delay-configuration), [Size & Limit Configuration](llm-limits.md#size--limit-configuration) |
| [LLM Voice and Camera](llm-voice-camera.md) | [Voice and Camera](llm-voice-camera.md#voice-and-camera) |
