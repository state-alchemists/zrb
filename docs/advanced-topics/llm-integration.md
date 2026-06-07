🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
- [Programmatic Usage](#programmatic-usage-llmtask-and-llmchattask)
- [Built-in LLM Tools](#built-in-llm-tools)
- [Permission Policy System](./permission-policy.md)
- [Plan Mode](./plan-mode.md)
- [Custom Tools and Sub-agents](#custom-tools-and-sub-agents)
- [Model Capabilities](#model-capabilities)
- [Context Management](#context-management)
- [Quick Reference](#quick-reference)

---

## Interactive Chat (`zrb llm chat`)

The primary way to interact with AI Assistant is through an interactive terminal user interface (TUI).

```bash
zrb llm chat "Can you help me refactor the user authentication service?"
```

This launches a full-screen chat application where you can have a conversation with the assistant.

### TUI Commands

| Command | Description |
|---------|-------------|
| `/q`, `/bye`, `/quit`, `/exit` | Exit the application |
| `/info`, `/help` | Show all available commands |
| `/compress`, `/compact` | Summarize conversation to free context |
| `/model <name>` | Switch LLM model (e.g., `/model openai:gpt-4o`) |
| `/yolo` or `/yolo <tools>` | Toggle auto-execute mode. With tool names (e.g., `/yolo Write,Edit`), selectively auto-approve only those tools |
| `/load <name>` | Load a named session |
| `/save <name>` | Save current session |
| `/attach <file_path>` | Attach a file to next message |
| `>` or `/redirect` (bare) | Copy last AI response to clipboard |
| `>` or `/redirect <file_path>` | Save last AI response to a file |
| `/copy` (bare) | Copy full conversation transcript to clipboard |
| `/copy <file_path>` | Save full conversation transcript to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |
| `/btw <text>` | Inject a side note for the next turn without sending it as a message (runs while the assistant is thinking) |
| `/plan` | Toggle [Plan Mode](./plan-mode.md) (read-only discovery) |
| `/rewind [n\|sha]` | List or restore filesystem + history [snapshots](../configuration/llm-config.md#6-rewind--snapshots) (requires `ZRB_LLM_ENABLE_REWIND`) |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.
>
> The token(s) that trigger each command are configurable — see
> [Slash Command Aliases](../configuration/llm-config.md#17-slash-command-aliases).

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode and the [Permission Policy](./permission-policy.md) system:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |
| **Permission Policy** | Fine-grained `ALLOW`/`DENY`/`ASK` rules that can override YOLO |
| **Plan Mode** | Strict read-only mode for discovery. See [Plan Mode](./plan-mode.md) |

**Safe Command Policy:** Both `Shell` and `Bash` tools automatically approve known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&&`) always require explicit approval.

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types.

### `LLMTask` (Single-Shot)

Use `LLMTask` for single-shot requests where you need the LLM to process input and return a result without conversational history.

```python
from zrb import LLMTask, cli

summarize_task = cli.add_task(
    LLMTask(
        name="summarize",
        system_prompt="You are an expert summarizer.",
        message="Please summarize the following text: {ctx.input.text}"
    )
)
```

### `LLMChatTask` (Conversational)

Use `LLMChatTask` to create your own fully customizable, interactive chat interfaces.

```python
from zrb import LLMChatTask, cli, StrInput

custom_chat = cli.add_task(
    LLMChatTask(
        name="custom-chat",
        ui_greeting="Hello from your custom assistant!",
        input=[StrInput(name="user_message", ...)],
        message="{ctx.input.user_message}"
    )
)
```

> 📖 **API Reference:** For the full `LLMChatTask` builder API — tools, guidance, hooks, policies, triggers, and custom commands — see the [LLMChatTask API Reference](../task-types/llmchat-task.md).

### Comparison

| Feature | `LLMTask` | `LLMChatTask` |
|---------|-----------|---------------|
| **Use case** | Single-shot processing | Interactive chat |
| **History** | None | Persistent session |
| **TUI** | No | Yes |
| **Custom tools** | Yes | Yes |

---

## Built-in LLM Tools

The assistant comes with a rich set of built-in tools. These are automatically available in every `LLMTask` and `LLMChatTask` unless you override the tool list.

### Shell & Execution

| Tool | Function | Description |
|------|----------|-------------|
| `Shell` | `run_shell_command` | Execute non-interactive shell commands. Streams output live and truncates large results. Always requires non-interactive flags (e.g., `-y`). |
| `Bash` | `run_shell_command` | Alias for `Shell` (Claude compatibility). Same behavior and arguments. |

### File System

| Tool | Function | Description |
|------|----------|-------------|
| `LS` | `list_files` | Recursively list files up to 3 levels deep, auto-excluding `.git`, `node_modules`, `__pycache__`, etc. |
| `Glob` | `glob_files` | Find files matching a glob pattern (e.g., `**/*.py`). |
| `Grep` | `search_files` | Search file contents by regex pattern. Supports `context_lines` (default 2), `files_only=True` to return only matching file paths, `case_sensitive=False` for case-insensitive search, and `file_pattern` to restrict to specific file types. |
| `Read` | `read_file` | Read a single file's contents with optional line-range slicing and auto-truncation. Issue parallel `Read` calls to load several files in one turn. |
| `Write` | `write_file` | Write or overwrite a file. |
| `Edit` | `replace_in_file` | Make targeted string replacements in a single file. |

### Web

| Tool | Function | Description |
|------|----------|-------------|
| `OpenWebPage` | `open_web_page` | Fetch a URL and return its content as Markdown. Optionally summarizes via a sub-agent to reduce token usage. |
| `SearchInternet` | `search_internet` | Search the web by query string. Defaults to Google News RSS (free, no setup). Optionally use SerpAPI, Brave, or SearXNG via `ZRB_SEARCH_INTERNET_METHOD`. |

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
| `WriteTodos` | `write_todos` | Create or replace the session todo list (persisted to `~/.zrb/todos/<session>.json`). |
| `GetTodos` | `get_todos` | Get the current todo list and progress summary. |
| `UpdateTodo` | `update_todo` | Update the status of a single todo item (`pending` → `in_progress` → `completed`). |
| `ClearTodos` | `clear_todos` | Discard the entire current todo list. |

### Knowledge Base (RAG)

| Tool factory | Description |
|---|---|
| `create_rag_from_directory` | Creates a semantic search tool over a local directory of documents (ChromaDB + OpenAI embeddings). Returns a callable tool you register with `add_tool()`. Requires `chromadb` and `openai` packages. |

```python
from zrb.llm.tool.rag import create_rag_from_directory

search_docs = create_rag_from_directory(
    tool_name="SearchDocs",
    tool_description="Search project documentation.",
    document_dir_path="./docs",
    vector_db_path="./.chroma",
)

my_chat_task.add_tool(search_docs)
```

### MCP (Model Context Protocol)

The assistant can connect to external MCP servers defined in `mcp-config.json`. See [MCP Support](mcp-support.md) for setup.

### Agent Delegation & Skills

| Tool | Description |
|------|-------------|
| `DelegateToAgent` | Delegate a sub-task to a named sub-agent. Sub-agents are discovered from `agents/` directories. See sub-agents section below. |
| `ActivateSkill` | Load a named skill (a set of prompts and tools) into the current session. |

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

## Tool Guidance

Every built-in tool ships with guidance that tells the LLM **when to use it** and **what the most important behavioral rule is**. When you add a custom tool, you can register the same kind of guidance so the LLM knows how to use it correctly.

Guidance is automatically filtered at runtime — entries for tools that are not registered on the task are suppressed, so the LLM never sees instructions for tools it cannot use.

### Static guidance (most common)

Use `add_tool_guidance()` with one or more `ToolGuidance` objects. This is the standard approach for tools whose names are known at definition time.

```python
from zrb import LLMChatTask, ToolGuidance

my_chat_task.add_tool(my_custom_tool)

my_chat_task.add_tool_guidance(
    ToolGuidance(
        group_name="My Domain",
        tool_name="MyCustomTool",
        when_to_use="When the user asks about X or needs to look up Y",
        key_rule="Always pass a valid ID; never call without first calling ListItems.",
    )
)
```

`ToolGuidance` fields:

| Field | Required | Description |
|-------|----------|-------------|
| `group_name` | Yes | Section heading in the rendered prompt. Created automatically on first use. |
| `tool_name` | Yes | Must match the tool's `__name__` attribute. |
| `when_to_use` | No | One sentence: the condition that should trigger this tool. |
| `key_rule` | No | The single most important constraint, gotcha, or sequencing requirement. |

### Dynamic guidance (config-dependent tool names)

Use `add_tool_guidance_factory()` when the tool name depends on runtime config or context. Each factory is a `Callable[[AnyContext], ToolGuidance]` evaluated at the start of each conversation turn.

```python
from zrb.config.config import CFG

my_chat_task.add_tool_guidance_factory(
    lambda ctx: ToolGuidance(
        group_name="My Domain",
        tool_name=f"List{CFG.ROOT_GROUP_NAME.capitalize()}Items",
        when_to_use="Before operating on any item — confirm it exists",
    )
)
```

This is only needed when the tool name itself is dynamic. For static names, use `add_tool_guidance()` instead.

> **Note:** `add_tool_guidance_factory()` and `add_tool_guidance_section_factory()` are available on `LLMChatTask`, `LLMTask`, and `SubAgentManager` — all of which conform to the `CommonToolHost` protocol in `zrb.llm.common_tools`.

---

## Custom Tools and Sub-agents

You can extend the assistant's capabilities with your own Python functions.

### Custom Python Tools

Any Python function can be registered as a tool. The assistant automatically understands the function's purpose from its docstring and type annotations.

```python
def get_weather(location: str) -> str:
    """Gets the current weather for a given location."""
    # ... your implementation ...

my_chat_task.add_tool(get_weather)
```

### Sub-agents

Zrb can automatically discover and manage sub-agents defined in JSON or YAML files within an `agents/` directory. The primary assistant can then delegate complex tasks to these specialized agents using the built-in `DelegateToAgent` tool.

Sub-agent files are discovered from (in priority order):
1. `~/.zrb/agents/`, `~/.claude/agents/` — user-global agents
2. `<project>/.zrb/agents/`, `<project>/.claude/agents/` — project agents (traversed upward from cwd)
3. Paths in `ZRB_LLM_EXTRA_AGENT_DIRS`

> 💡 **Benefit:** Sub-agents isolate context and keep the main conversation history clean.

---

## Model Capabilities

Zrb maintains a per-model capability registry that tracks what each model can and can't do — image/audio/video input, whether parallel tool calls are supported, and so on. It's used internally to decide things like *"should I let pydantic-ai emit parallel tool calls for this model?"* and *"is the user attaching an image to a text-only model — describe it via the multimodal fallback?"*.

The registry ships with a built-in name-pattern table (it knows about GPT-4o, Claude, Gemini, Llava, etc.) and exposes a module-level singleton you can extend from `zrb_init.py`:

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

The AI Assistant is designed for long-running, complex tasks and has a sophisticated context management system.

### Two-Tier Summarization

| Level | Trigger | Action |
|-------|---------|--------|
| **Message-level** | Single tool output too large | Summarize before adding to history |
| **Conversational** | Overall history grows too large | Compress older messages to `<state_snapshot>` |

### 30% Retention Policy

When summarization triggers, the system:

| Action | Description |
|--------|-------------|
| Compress | Oldest 70% → state snapshot |
| Retain | Most recent 30% verbatim |
| Preserve | Tool call/return pairs never separated |
| Split | At conversation turn boundaries |

### Journal System

For persistent, long-term memory, Zrb uses a journal system—a directory of Markdown files (default: `~/.zrb/llm-notes/`) where the assistant can keep notes. The `index.md` file is automatically included in every context.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `zrb llm chat` | Start interactive chat |
| `zrb llm chat "message"` | Start with initial message |

| Task Type | Import | Use Case |
|-----------|--------|----------|
| `LLMTask` | `from zrb import LLMTask` | Single processing |
| `LLMChatTask` | `from zrb import LLMChatTask` | Interactive chat |

---