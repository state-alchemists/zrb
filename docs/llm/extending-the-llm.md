🔖 [Documentation Home](../../README.md) > [LLM](./) > Extending the LLM

# Extending the LLM (Tools, Sub-agents, Capabilities)

Built-in tools, how to write your own, sub-agent delegation, per-model capability overrides, and the context-management internals behind `zrb llm chat`. For the end-user TUI commands, troubleshooting, and `LLMTask`/`LLMChatTask` usage, see [LLM Integration](llm-integration.md).

---

## Table of Contents

- [Built-in LLM Tools](#built-in-llm-tools)
- [Telling the LLM how to use a tool](#telling-the-llm-how-to-use-a-tool)
- [Custom Tools and Sub-agents](#custom-tools-and-sub-agents)
- [Model Capabilities](#model-capabilities)
- [Context Management](#context-management)

---

## Built-in LLM Tools

Every `LLMTask` and `LLMChatTask` gets these unless you override the tool list.

### Shell & Execution

| Tool | Function | Description |
|------|----------|-------------|
| `Shell` | `run_shell_command` | Execute non-interactive shell commands. Streams output live and truncates large results. Always requires non-interactive flags (e.g., `-y`). Pass `background=True` for long-running processes (dev servers, watchers) to get a handle immediately instead of blocking. zrb's only shell tool — sub-agents that list `Bash` (the Claude Code name) are mapped to it on load; pass `shell="bash"` if bash is needed specifically. |
| `MonitorProcess` | `monitor_process` | Check, wait on, or kill a background process started with `Shell` `background=True`. Pass `wait=N` to block up to N seconds (returns early on exit), or `kill=True` to terminate. |

### File System

| Tool | Function | Description |
|------|----------|-------------|
| `LS` | `list_files` | Recursively list files up to 3 levels deep, auto-excluding `.git`, `node_modules`, `__pycache__`, etc. |
| `Glob` | `glob_files` | Find files matching a glob pattern (e.g., `**/*.py`). |
| `Grep` | `search_files` | Search file contents by regex pattern. Supports `context_lines` (default 2), `files_only=True` to return only matching file paths, `case_sensitive=False` for case-insensitive search, and `file_pattern` to restrict to specific file types. |
| `Read` | `read_file` | Read a UTF-8 text file from `start_line` to `end_line` (1-indexed, inclusive; default: whole file). Lines are numbered `cat -n`-style (six right-aligned columns, then a tab); strip through the first tab before passing text to `Edit`, which also strips it if one slips through. PDF text comes back unnumbered. Output past the char cap (measured before numbering) is truncated at the end — narrow the range or `Grep` first. Issue parallel `Read` calls to load several files in one turn. |
| `Write` | `write_file` | Write a file. Overwriting an existing file with `mode="w"` requires that this session has already Read it (or Written/Edited it to its current content) — otherwise the call is refused with a pointer back to `Read` (ADR-0084). Appends (`mode="a"`) need no prior read. Binary (non-UTF-8) files are refused in every mode. |
| `Edit` | `replace_in_file` | Make targeted string replacements in a single file. |

### Web

| Tool | Function | Description |
|------|----------|-------------|
| `WebFetch` | `open_web_page` | Fetch a URL and return its content as Markdown. Optionally summarizes via a sub-agent to reduce token usage. |
| `WebSearch` | `search_internet` | Search the web by query string. Defaults to Google News RSS (free, no setup). Optionally use SerpAPI, Brave, or SearXNG via `ZRB_SEARCH_INTERNET_METHOD`. |

### User Interaction

| Tool | Function | Description |
|------|----------|-------------|
| `AskUserQuestion` | `ask_user_question` | Ask the user one or more structured multiple-choice questions mid-turn and return their answers. Interactive sessions only — in non-interactive runs (`--interactive false`) it short-circuits with a `[SYSTEM SUGGESTION]` instead of blocking on stdin. |

### Code Intelligence

| Tool | Function | Description |
|------|----------|-------------|
| `AnalyzeFile` | `analyze_file` | Semantic analysis of a single file via LLM sub-agent. Use for architecture/intent questions, not raw content retrieval. |
| `AnalyzeCode` | `analyze_code` | Deep code analysis for an entire directory. Requires LSP to be configured. See [LSP Support](lsp-support.md). |
| `LspFindDefinition` | — | Jump to the canonical definition of a symbol. |
| `LspFindReferences` | — | Find all call sites and usages of a symbol across the project. |
| `LspGetDiagnostics` | — | Get type errors, warnings, and lint issues for a file. |
| `LspGetDocumentSymbols` | — | List all symbols defined in a file. |
| `LspGetWorkspaceSymbols` | — | Find a symbol by name across the workspace. |
| `LspGetHoverInfo` | — | Get type signature or documentation for a symbol. |
| `LspRenameSymbol` | — | Rename a symbol safely across the codebase (dry_run=True by default to preview before applying). |
| `LspListServers` | — | List active Language Server Protocol servers. |

### Planning & Task Tracking

| Tool | Function | Description |
|------|----------|-------------|
| `TodoWrite` | `write_todos` | Create or replace the session todo list (persisted to `~/.zrb/todos/<session>.json`). Replacing the full list subsumes per-item status updates and clearing. |
| `TodoRead` | `get_todos` | Get the current todo list and progress summary. |

### Knowledge Base (RAG)

| Tool factory | Description |
|---|---|
| `create_rag_from_directory` | Creates a semantic search tool over a local directory of documents (ChromaDB + OpenAI embeddings). Returns a callable tool you register with `append_tool()`. Requires `chromadb` and `openai` packages. |

```python
from zrb.llm.tool.rag import create_rag_from_directory

search_docs = create_rag_from_directory(
    tool_name="SearchDocs",
    tool_description="Search project documentation.",
    document_dir_path="./docs",
    vector_db_path="./.chroma",
)

my_chat_task.append_tool(search_docs)
```

### MCP (Model Context Protocol)

The assistant can connect to external MCP servers defined in `mcp-config.json`. See [MCP Support](mcp-support.md) for setup.

### Agent Delegation & Skills

| Tool | Description |
|------|-------------|
| `DelegateToAgent` | Delegate a sub-task to a named sub-agent (discovered from `core_agents/` and `agents/` directories). Pass `tasks=[{...}, ...]` to fan out several concurrently in one call — concurrency is capped at `LLM_MAX_PARALLEL_DELEGATIONS` (default 10; `0` disables), pacing rather than rejecting large batches, and each task may set `isolate_worktree: true` to run in its own git worktree. See sub-agents section below. |
| `SearchAgent` | Find sub-agents by name or description keywords. The `DelegateToAgent` roster only lists the first `LLM_MAX_AGENTS_IN_ROSTER` agents, so use this when the agent you need is not on it. |
| `ActivateSkill` | Load a named skill (a set of prompts and tools) into the current session. |
| `SearchSkill` | Find skills by name or description keywords. The skill catalogue in the `workflow` prompt section only lists the first `LLM_MAX_SKILLS_IN_CATALOG` skills, so use this when the skill you need is not listed. |

### Git Worktrees

| Tool | Function | Description |
|------|----------|-------------|
| `ListWorktrees` | `list_worktrees` | List all active git worktrees. Call before `EnterWorktree` to avoid duplicates. |
| `EnterWorktree` | `enter_worktree` | Create an isolated git worktree for risky or experimental changes. |
| `ExitWorktree` | `exit_worktree` | Finish work in a worktree and clean it up. |

### Zrb Task Execution

| Tool | Description |
|------|-------------|
| `ListZrbTasks` | List all available Zrb tasks in the current project. |
| `RunZrbTask` | Execute a registered Zrb task by name from within a conversation. |

---

## Telling the LLM how to use a tool

A tool describes itself. Its **docstring** and type annotations become the JSON schema pydantic-ai sends on every request, so whatever the model needs to know sits right next to the arguments it is filling in — that is the whole mechanism (ADR-0045).

```python
def check_stock(warehouse_id: str, sku: str) -> dict:
    """Look up on-hand stock for one SKU in one warehouse.

    Always pass warehouse_id — a lookup without it scans every site and times
    out. An empty result means no stock on hand, not an error. To find a
    warehouse id first, use ListWarehouses.
    """
    ...

my_chat_task.append_tool(check_stock)
```

Write three things into the docstring: when to reach for this tool, the one constraint that trips callers up, and which tool to use instead when this is the wrong one.

> **This relocates token cost, it does not remove it.** pydantic-ai serializes every registered tool's docstring *and* schema into every request, so a docstring is not deferred context. What it buys is locality — the rule is in front of the model at the moment it matters. The lever on prompt weight is the **number** of registered tools; see *Deferred-loading tools* below.

### Cross-cutting policy

For a rule that is not about any one tool, append it to the system prompt rather than repeating it in N docstrings:

```python
my_chat_task.prompt_manager.append_prompt(
    "## Inventory rules\n- Never quote stock without a warehouse."
)
```

`append_prompt` content is emitted after all built-in sections. If the policy depends on live runtime state instead, register a live-context provider (`add_live_context`) so it is re-evaluated every turn without invalidating the cached prompt.

---

## Custom Tools and Sub-agents

You can extend the assistant's capabilities with your own Python functions.

> **Where to put your extension.** Everything below mutates a *per-task* host (`my_task.append_tool`, `my_task.prompt_manager.append_prompt`, a manager bound to a fresh registry). To change the shipped behavior **globally** — every `zrb llm chat` and every `LLMTask` in the project — configure the shared registries instead: `tool_registry`, `skill_registry`, `sub_agent_registry`, `hook_registry`, `prompt_registry` plus their `ZRB_LLM_TOOLS` / `ZRB_LLM_SKILLS` / `ZRB_LLM_AGENTS` / `ZRB_LLM_HOOKS` / `ZRB_LLM_PROMPT` env twins. One mental model, three channels (env vars name things, `zrb_init.py` builds things, task args override one host) — see [LLM Component Collections](../configuration/llm-collections.md).

### Custom Python Tools

Any Python function can be a tool; its docstring and type annotations describe it to the model.

```python
def get_weather(location: str) -> str:
    """Gets the current weather for a given location."""
    # ... your implementation ...

my_chat_task.append_tool(get_weather)
```

For a tool that needs per-run context, or that you want resolved fresh each turn, register a **factory** instead. Each factory is a `Callable[[AnyContext], ...]` evaluated at the start of every turn; return a single tool, a list, or `[]` to skip registration conditionally.

```python
my_chat_task.append_tool_factory(lambda ctx: get_weather)
```

### Deferred-loading tools

A registered tool's schema (docstring + parameters) is serialized into **every** turn's request, whether or not the model uses it. For tools that are rarely needed, wrap them with pydantic-ai's `defer_loading=True` to hide the schema until the model searches for the tool by name. This is the one real lever on tool-definition weight.

```python
from pydantic_ai import Tool

my_chat_task.append_tool(Tool(get_weather, defer_loading=True))
```

The trade-off is discovery: a deferred tool is invisible until searched for, so give it a name the model would think to search. This is how zrb ships its own rarely-used tools (`analyze_code`, worktree/LSP tools, `MonitorProcess`, MCP toolsets, …). Tools that are useless in a given environment are better *unregistered* than deferred — zrb skips the LSP tools when no language server is installed, the worktree tools outside a git repo, and the journal tools when `ZRB_LLM_JOURNAL_ENABLED` is off.

Note that `defer_loading` (a per-turn *token*-cost lever) is unrelated to import cost: `from pydantic_ai import Tool` at module scope eagerly imports `pydantic_ai` (~1.7s). To keep that off the `zrb` startup path, do the import and the `Tool(...)` wrap inside a factory, which runs only when the task first executes:

```python
def _deferred(ctx):
    from pydantic_ai import Tool  # imported lazily, on first run
    return Tool(get_weather, defer_loading=True)

my_chat_task.append_tool_factory(_deferred)
```

### Equipping a custom host with the shipped tool surface

If you build your own `LLMTask` / `LLMChatTask` and want it to have zrb's standard tools (Read/Write/Shell/Grep/…), guidance, and the MCP toolset factory — the same set the built-in `chat` agent gets — call **`apply_common_tools(host)`**:

```python
from zrb import LLMTask
from zrb.llm.common_tools import apply_common_tools

my_task = LLMTask(name="my-agent", ...)
apply_common_tools(my_task)   # register shipped tools + guidance, lazily
my_task.append_tool(get_weather) # then layer on your own
```

**It stays import-cheap.** `apply_common_tools` only appends per-run providers through the host's public append API; nothing resolves until the first agent build, so the `pydantic_ai` import (~1.7s) stays off the `import zrb` path that every CLI invocation takes. Call it once, when you construct the host. Hosts with an approval channel also get the shell-safety policy; programmatic hosts get the tools without it.

`apply_common_tools` works on `LLMChatTask`, `LLMTask`, and `SubAgentManager`. A `SubAgentManager` resolves tools *by name* from agent definitions (read-only agents are name-gated), so its `get_tool_registry` includes the shipped static set lazily and manual registrations win name collisions. Its factory/toolset providers are resolved by the names requested in each agent definition. The built-in `chat` agent and `sub_agent_manager` already have it applied — you only need this for hosts you construct yourself.

### Sub-agents

Zrb discovers sub-agents defined in Claude-compatible `AGENT.md` or `*.agent.md` files; the main assistant delegates to them with `DelegateToAgent`.

Sub-agent files are discovered from (in priority order):
1. `~/.zrb/agents/`, `~/.claude/agents/` — user-global agents
2. `<project>/.zrb/agents/`, `<project>/.claude/agents/` — project agents (traversed upward from cwd)
3. Plugin agent directories, from `ZRB_LLM_PLUGIN_DIRS`
4. Paths in `CFG.LLM_BASE_SEARCH_DIRS`
5. Paths in `ZRB_LLM_EXTRA_AGENT_DIRS`
6. Zrb's built-in `core_agents/` — always included
7. Zrb's optional built-in `agents/` — included when `LLM_ENABLE_BUILTIN_AGENTS` is enabled
8. The manager's `scan_root` (recursive scan target)

Core agents are listed before optional ones in the `AVAILABLE AGENTS` roster and `SearchAgent` results. `generalist` is the built-in core agent, so it stays available with optional built-in agents disabled. Sub-agents keep their work out of the main conversation's context.

---

## Model Capabilities

> Not to be confused with the `capabilities` constructor argument on `LLMTask`/`LLMChatTask` — that's pydantic-ai's own `AbstractCapability` list (`ProcessHistory`, `Thinking`, `WebSearch`, …), documented in [Model, Model Settings & Capabilities](../task-types/llmchat-task.md#model-model-settings--capabilities). This section is zrb's own registry, described below.

Zrb keeps a per-model capability registry (image/audio/video/document input, parallel tool calls, …). It decides, for example, whether to allow parallel tool calls, or whether an image sent to a text-only model goes through the multimodal fallback. It ships a name-pattern table (GPT-4o, Claude, Gemini, Llava, …); extend its singleton from `zrb_init.py`:

```python
from zrb.llm.util.capabilities import model_capabilities

# Tell zrb about your private model
model_capabilities.register(
    "my-private-model",
    supports_image_input=True,
    supports_parallel_tool_calls=False,
)
```

`register(pattern, **overrides)` takes a case-insensitive regex matched against the bare model name (the part after `provider:`) and any subset of capability fields. Unspecified fields keep their pattern-table values. Most recently registered entries take priority on match.

### Capability fields

| Field | Type | Meaning |
|-------|------|---------|
| `supports_image_input` | `bool` | Model accepts image attachments |
| `supports_audio_input` | `bool` | Model accepts audio attachments |
| `supports_video_input` | `bool` | Model accepts video attachments |
| `supports_document_input` | `bool` | Model accepts document attachments (PDF/docx/xlsx/doc/xls as opaque binary — plain-text formats always pass through regardless of this flag) |
| `supports_parallel_tool_calls` | `bool \| None` | Tri-state: `True` known-good, `False` known-malforms parallel calls (zrb sets `parallel_tool_calls=False` at the provider level), `None` unknown — pass through |

Field names mirror LiteLLM's `supports_*` conventions.

### Querying

```python
caps = model_capabilities.get("openai:gpt-4o")
if caps.supports_image_input:
    ...

# Convenience predicate
if model_capabilities.supports_modality("openai:gpt-4o", "image"):
    ...
```

`get()` returns conservative defaults (`False`/`None`) for `None` or unknown models, so callers should treat absence as "unknown — pass through" rather than "actively unsupported".

> 💡 The default singleton is shared across the process. Tests that need full isolation can instantiate `ModelCapabilityRegistry()` directly.

---

## Context Management

### Two-Tier Summarization

| Level | Trigger | Action |
|-------|---------|--------|
| **Message-level** | Single tool output too large | Summarize before adding to history |
| **Conversational** | Overall history grows too large | Compress older messages to `<state_snapshot>` |

### Message-Count-Based Retention

When summarization triggers, the system splits history by message count, not by percentage: `target_keep_count = min(summary_window, len(messages))`, where `summary_window` defaults to 100 messages (`LLM_HISTORY_SUMMARIZATION_WINDOW`). Everything older than that target split point is compressed into a state snapshot; the rest is retained verbatim.

| Action | Description |
|--------|-------------|
| Compress | Messages older than the target split point → state snapshot |
| Retain | Newest `summary_window` messages (default 100) verbatim |
| Preserve | Tool call/return pairs never separated |
| Split | At conversation turn boundaries |

The actual split point is adjusted by a backward/forward search that looks for a safe turn boundary near that target — it won't cut a tool call away from its return. Within that search, a token-based safety valve prevents the retained slice from growing too large: if keeping messages back to a candidate split point would exceed 70% of the conversational token threshold, the search stops extending further back. That 70%/token figure is an internal bound on the search, not the primary retention rule.

### Journal System

Long-term memory is a directory of Markdown notes (default `~/.zrb/llm-notes/`) that the agent writes through `LogActivity`/`WriteJournalNote` and reads through `SearchJournal`. How it is stored and when its index reaches the model: [LLM Journal System](../technical-specs/llm-context.md). Knobs: [LLM Configuration → Journal & Context Storage](../configuration/llm-config.md#5-journal--context-storage).

---

🔖 [Documentation Home](../../README.md) > [LLM](./) > Extending the LLM
