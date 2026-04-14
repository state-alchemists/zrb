🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
- [Programmatic Usage](#programmatic-usage-llmtask-and-llmchattask)
- [Built-in LLM Tools](#built-in-llm-tools)
- [Custom Tools and Sub-agents](#custom-tools-and-sub-agents)
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
| `>` or `/redirect <file_path>` | Save last response to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |

**Safe Command Policy:** The `Bash` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&&`) always require explicit approval.

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
| `Bash` | `run_shell_command` | Execute non-interactive shell commands. Streams output live and truncates large results. Always requires non-interactive flags (e.g., `-y`). |

### File System

| Tool | Function | Description |
|------|----------|-------------|
| `LS` | `list_files` | Recursively list files up to 3 levels deep, auto-excluding `.git`, `node_modules`, `__pycache__`, etc. |
| `Glob` | `glob_files` | Find files matching a glob pattern (e.g., `**/*.py`). |
| `Read` | `read_file` | Read a file's contents with optional line-range slicing and auto-truncation. |
| `Write` | `write_file` | Write or overwrite a file. |
| `Edit` | `edit_file` | Make targeted string replacements in a file. |
| `Grep` | `search_files` | Search file contents by regex pattern with context lines and file-type filtering. |

### Web

| Tool | Function | Description |
|------|----------|-------------|
| `OpenWebPage` | `open_web_page` | Fetch a URL and return its content as Markdown. Optionally summarizes via a sub-agent to reduce token usage. |
| `SearchInternet` | `search_internet` | Search the web by query string. Requires a search engine API key (SerpAPI, Brave, or SearXNG). |

### Code Intelligence

| Tool | Function | Description |
|------|----------|-------------|
| `AnalyzeCode` | `analyze_code` | Deep code analysis using the Language Server Protocol (LSP). Requires LSP to be configured. See [LSP Support](lsp-support.md). |

### Planning & Task Tracking

| Tool | Function | Description |
|------|----------|-------------|
| `WriteTodos` | `write_todos` | Create or replace the session todo list (persisted to `~/.zrb/todos/<session>.json`). |
| `GetTodos` | `get_todos` | Get the current todo list and progress summary. |
| `UpdateTodo` | `update_todo` | Update the status of a single todo item (`pending` → `in_progress` → `completed`). |

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

### Worktree

| Tool | Description |
|------|-------------|
| `CreateWorktree` | Create an isolated git worktree for safe parallel development. |
| `ExitWorktree` | Commit and close the current worktree, merging changes back. |

### Zrb Task Execution

| Tool | Description |
|------|-------------|
| `RunZrbTask` | Execute a registered Zrb task by name from within a conversation. |

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