🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration

# LLM Integration (AI Assistant)

Zrb comes with a powerful, built-in AI assistant that can understand your codebase, perform actions on your behalf, and automate complex software engineering tasks.

---

## Table of Contents

- [Interactive Chat](#interactive-chat-zrb-llm-chat)
  - [TUI Commands](#tui-commands)
  - [Session Token Tracking](#session-token-tracking)
  - [Approval Policies](#approval-policies)
  - [Troubleshooting: Voice & Photo](#troubleshooting-voice--photo)
- [Built-in LLM Tools](#built-in-llm-tools)
- [Permission Policy System](./permission-policy.md)
- [Sandbox (Filesystem Containment)](./sandbox.md)
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
| `/attach <file_path>` | Attach a file to next message (capped by `LLM_MAX_ATTACHMENT_BYTES`, default 20MB; content is sniffed against its extension) |
| `/photo [device]` | Capture a photo from the camera and attach it to the next message (device is optional; auto-detected per platform) |
| `>` or `/redirect` (bare) | Copy last AI response to clipboard |
| `>` or `/redirect <file_path>` | Save last AI response to a file |
| `/copy` (bare) | Copy full conversation transcript to clipboard |
| `/copy <file_path>` | Save full conversation transcript to file |
| `!` or `/exec <shell_cmd>` | Execute shell command |
| `/btw <text>` | Inject a side note for the next turn without sending it as a message (runs while the assistant is thinking) |
| `/plan` | Toggle [Plan Mode](./plan-mode.md) (read-only discovery) |
| `/rewind [n\|sha]` | List or restore filesystem + history [snapshots](../configuration/llm-config.md#6-rewind--snapshots) (requires `ZRB_LLM_ENABLE_REWIND`) |
| `/voice` | Toggle push-to-talk voice dictation on/off (requires `ZRB_LLM_VOICE_ENABLED`; see [Voice Dictation](../configuration/llm-config.md#23-voice-dictation)) |

> 💡 **Tip:** Any `/command` that matches a loaded skill will be executed as a skill.
>
> The token(s) that trigger each command are configurable — see [Slash Command Aliases](../configuration/llm-config.md#17-slash-command-aliases).

### Session Token Tracking

The TUI status bar tracks accumulated LLM token usage across all requests in a session. After the first LLM request completes, the status bar displays a token count like:

```
💸 1.5k in · 34 out
```

The counters reset whenever you switch conversations via `/load`, since past sessions' spend is not persisted. Tokens are tracked per-UI instance — in a `MultiUI` setup each child UI maintains its own totals.

There are no configuration knobs for this feature; it always appears (non-zero after the first request) and uses the theme's `FAINT` style.

### Approval Policies

By default, Zrb prompts for confirmation before executing most tools. This is controlled by YOLO mode and the [Permission Policy](./permission-policy.md) system:

| Mode | Behavior |
|------|----------|
| **YOLO off** | All tools require confirmation |
| **YOLO on** | All tools auto-approved |
| **Selective YOLO** | Only specified tools auto-approved (e.g., `/yolo Write,Edit`) |
| **Permission Policy** | Fine-grained `ALLOW`/`DENY`/`ASK` rules that can override YOLO |
| **Plan Mode** | Strict read-only mode for discovery. See [Plan Mode](./plan-mode.md) |

**Safe Command Policy:** The `Shell` tool automatically approves known-safe read-only commands (e.g., `ls`, `git status`, `cat`, `grep`) without requiring YOLO mode. Commands with dangerous shell metacharacters (`>`, `|`, `;`, `&`, `` ` ``, `$()`, `\n`, `\r`) always require explicit approval. Known-safe prefixes include `ls`, `cat`, `grep`, `git status`, `printenv`, and similar read-only commands — note that bare `env` is intentionally excluded as `env FOO=1 rm -rf x` can execute arbitrary commands.

### Troubleshooting: Voice & Photo

`/voice` and `/photo` depend on OS-level microphone/camera access, so failures are usually platform setup, not a zrb bug.

**Voice (`/voice`):**

| Symptom | Solution |
|---------|----------|
| `/voice` says voice dictation is disabled | Set `ZRB_LLM_VOICE_ENABLED=true` — see [Voice Dictation](../configuration/llm-config.md#23-voice-dictation) |
| `RuntimeError` mentioning `sounddevice` or `vosk` | Those are optional dependencies: `pip install sounddevice vosk numpy` (or switch `ZRB_LLM_VOICE_MODE` to `openai`/`google`/`multimodal`) |
| Recording starts but no audio is captured | Check OS microphone permissions for your terminal app; on Linux, check that PulseAudio/PipeWire is running |
| No sound on WSL | WSL2 needs WSLg (Windows 11) or a PulseAudio server bridged from Windows for audio passthrough |
| Termux: no microphone access | Install `termux-api` (`pkg install termux-api`) and the Termux:API app from F-Droid; grant microphone permission to Termux:API in Android settings |

**Photo (`/photo`):**

| Symptom | Solution |
|---------|----------|
| "Camera capture failed" with no other detail | Install `ffmpeg` — it's the capture backend on every desktop platform |
| macOS: capture fails or returns a black frame | Grant your terminal app camera access in **System Settings > Privacy & Security > Camera** — easy to miss, since the OS doesn't always prompt for a CLI tool |
| Linux: no camera found | Check `/dev/video0` exists and your user is in the `video` group (`sudo usermod -aG video $USER`, then re-login) |
| Windows: capture fails or picks the wrong camera | Auto-detection parses `ffmpeg -f dshow -list_devices true -i dummy`; if it fails or the machine has multiple cameras, run that command yourself to find the device name and pass it explicitly: `/photo "<device name>"` |
| WSL: no camera found | WSL2 has no camera passthrough by default — set up [usbipd-win](https://github.com/dorssel/usbipd-win) to attach the webcam to the WSL2 kernel |
| WSL: `usbipd attach` fails with `Device busy (exported)` even after `usbipd bind` | Windows itself is still holding the camera. This is common for a laptop's **built-in/integrated camera** — Windows' Frame Server keeps a handle on it (for Windows Hello, the Camera app, background video-conferencing processes, etc.) and often won't release it even when nothing appears to be using it, sometimes not even after a reboot. An **external USB webcam** attaches far more reliably than an integrated one. If you must use the integrated camera, try closing Windows Hello/Camera/Teams/Zoom first, or as a last resort disable the built-in camera in Device Manager before attaching (`usbipd attach --wsl --busid=<id>`) — re-enable it afterward to use it on Windows again |
| Termux (native or `proot-distro`): "Camera capture failed" | Install the Termux:API app (F-Droid) and `pkg install termux-api`. `/photo` works from inside `proot-distro` too — the capture writes to Termux's real home directory rather than a temp path, so it's visible from both native Termux and a proot guest |

---

## Programmatic Usage (`LLMTask` and `LLMChatTask`)

You can also integrate the LLM directly into your automated workflows using two specialized task types. Both accept `message`, `system_prompt`, and `prompt_manager` as values, templates, callables, or sections — see the full guide at **[Programming the Prompt](programming-the-prompt.md)** for examples of each rung.

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
| `Shell` | `run_shell_command` | Execute non-interactive shell commands. Streams output live and truncates large results. Always requires non-interactive flags (e.g., `-y`). Pass `background=True` for long-running processes (dev servers, watchers) to get a handle immediately instead of blocking. zrb's only shell tool — sub-agents that list `Bash` (the Claude Code name) are mapped to it on load; pass `shell="bash"` if bash is needed specifically. |
| `MonitorProcess` | `monitor_process` | Check, wait on, or kill a background process started with `Shell` `background=True`. Pass `wait=N` to block up to N seconds (returns early on exit), or `kill=True` to terminate. |

### File System

| Tool | Function | Description |
|------|----------|-------------|
| `LS` | `list_files` | Recursively list files up to 3 levels deep, auto-excluding `.git`, `node_modules`, `__pycache__`, etc. |
| `Glob` | `glob_files` | Find files matching a glob pattern (e.g., `**/*.py`). |
| `Grep` | `search_files` | Search file contents by regex pattern. Supports `context_lines` (default 2), `files_only=True` to return only matching file paths, `case_sensitive=False` for case-insensitive search, and `file_pattern` to restrict to specific file types. |
| `Read` | `read_file` | Read a UTF-8 text file between `start_line` and `end_line` (1-indexed, inclusive; defaults: 1 to end). Every line is numbered `cat -n`-style (number right-aligned in six columns, then a tab) so `file:line` citations are read, not counted; strip the prefix through the first tab before passing text to `Edit`, which also strips it itself if it slips through. PDF text is returned unnumbered — its line breaks come from the extractor, not the document. The char cap is measured on file content, before numbering. Output exceeding the char cap is truncated at the end — narrow the range or use `Grep` to locate the section you need. Issue parallel `Read` calls to load several files in one turn. |
| `Write` | `write_file` | Write or overwrite a file. |
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
| `DelegateToAgent` | Delegate a sub-task to a named sub-agent (discovered from `agents/` directories). Pass `tasks=[{...}, ...]` to fan out several concurrently in one call. See sub-agents section below. |
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

### Custom Python Tools

Any Python function can be registered as a tool. The assistant automatically understands the function's purpose from its docstring and type annotations.

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

If you build your own `LLMTask` / `LLMChatTask` and want it to have zrb's standard tools (Read/Write/Shell/Grep/…), guidance, and the MCP toolset factory — the same set the built-in `chat` agent gets — use **`defer_common_tools(host)`**, not `apply_common_tools(host)`:

```python
from zrb import LLMTask
from zrb.llm.common_tools import defer_common_tools

my_task = LLMTask(name="my-agent", ...)
defer_common_tools(my_task)   # register shipped tools + guidance, lazily
my_task.append_tool(get_weather) # then layer on your own
```

**Why deferred is the default.** `apply_common_tools` transitively imports `pydantic_ai` (~1.7s) as a side effect of resolving the shipped tools. Task-definition modules are imported on **every** `zrb` CLI invocation — so calling `apply_common_tools` at module scope makes every `zrb` command in your project (even unrelated ones like `zrb --help`) pay that import cost. `defer_common_tools` registers the same tools/guidance but delays the heavy import until the task actually runs its first turn. Constructing the task and adding your own plain-function tools stay import-cheap.

`defer_common_tools` works on `LLMChatTask`, `LLMTask`, and `SubAgentManager` — they each drain the deferred registration on their first run. The built-in `chat` agent and sub-agents already have it deferred, so you only need this for hosts you construct yourself. Call it once per host.

> **When to use eager `apply_common_tools` instead:** only if you built a *custom* host type (one that is not an `LLMChatTask`/`LLMTask`/`SubAgentManager`) — those have no run-time trigger to drain a deferred registration, so they must apply eagerly. You can also use it if you genuinely need the tools registered before the first run (e.g. to introspect the tool list at import time), accepting the eager `pydantic_ai` import.

### Sub-agents

Zrb can automatically discover and manage sub-agents defined in JSON or YAML files within an `agents/` directory. The primary assistant can then delegate complex tasks to these specialized agents using the built-in `DelegateToAgent` tool.

Sub-agent files are discovered from (in priority order):
1. `~/.zrb/agents/`, `~/.claude/agents/` — user-global agents
2. `<project>/.zrb/agents/`, `<project>/.claude/agents/` — project agents (traversed upward from cwd)
3. Plugin agent directories, from `ZRB_LLM_PLUGIN_DIRS`
4. Paths in `CFG.LLM_BASE_SEARCH_DIRS`
5. Paths in `ZRB_LLM_EXTRA_AGENT_DIRS`
6. Zrb's built-in agents
7. `self._root_dir` (recursive scan target)

> 💡 **Benefit:** Sub-agents isolate context and keep the main conversation history clean.

---

## Model Capabilities

Zrb maintains a per-model capability registry that tracks what each model can and can't do — image/audio/video/document input, whether parallel tool calls are supported, and so on. It's used internally to decide things like *"should I let pydantic-ai emit parallel tool calls for this model?"* and *"is the user attaching an image to a text-only model — describe it via the multimodal fallback?"*.

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

The AI Assistant is designed for long-running, complex tasks and has a sophisticated context management system.

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

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > LLM Integration
