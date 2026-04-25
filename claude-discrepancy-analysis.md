# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (docs.anthropic.com/en/docs/claude-code) fetched April 2026. Zrb features sourced from full codebase exploration of `src/zrb/` at v2.22.6.
>
> **Zrb version**: 2.22.6
>
> **Legend**:
> - ✅ **Fully supported** — identical or functionally equivalent
> - 🟡 **Partially supported** — exists but with notable gaps
> - ❌ **Not supported** — missing entirely
> - 🔵 **Zrb-only** — Zrb has this; Claude Code does not

---

## Table of Contents

1. [CLI Interface & Flags](#1-cli-interface--flags)
2. [Interactive Terminal Mode](#2-interactive-terminal-mode)
3. [Slash Commands / Custom Commands](#3-slash-commands--custom-commands)
4. [Memory System](#4-memory-system)
5. [Hooks System](#5-hooks-system)
6. [MCP (Model Context Protocol)](#6-mcp-model-context-protocol)
7. [Subagents / Multi-Agent Orchestration](#7-subagents--multi-agent-orchestration)
8. [Agent Teams (Experimental)](#8-agent-teams-experimental)
9. [Skills System](#9-skills-system)
10. [Permission Modes & Tool Approval](#10-permission-modes--tool-approval)
11. [Settings & Configuration System](#11-settings--configuration-system)
12. [Built-in Tools](#12-built-in-tools)
13. [IDE Integrations](#13-ide-integrations)
14. [Session Management & Checkpointing](#14-session-management--checkpointing)
15. [Web UI](#15-web-ui)
16. [Auto Mode (Safety Classifier)](#16-auto-mode-safety-classifier)
17. [GitHub / CI/CD Integration](#17-github--cicd-integration)
18. [Sandboxing](#18-sandboxing)
19. [Remote & Cloud Sessions](#19-remote--cloud-sessions)
20. [Plugins System](#20-plugins-system)
21. [Rate Limiting & Budget Control](#21-rate-limiting--budget-control)
22. [Platform Support](#22-platform-support)
23. [LSP / Code Intelligence](#23-lsp--code-intelligence)
24. [Context Compaction](#24-context-compaction)
25. [Vim Mode & Editor Features](#25-vim-mode--editor-features)
26. [Voice Input](#26-voice-input)
27. [Diff Viewer](#27-diff-viewer)
28. [Task / Todo System](#28-task--todo-system)
29. [Scheduling](#29-scheduling)
30. [Worktree Isolation](#30-worktree-isolation)
31. [Side Questions (`/btw`)](#31-side-questions-btw)
32. [Channels & Remote Control](#32-channels--remote-control)
33. [Summary & Roadmap](#33-summary--roadmap)

---

## 1. CLI Interface & Flags

### Claude Code

Comprehensive CLI with 70+ flags across 30+ subcommands:
- `claude "query"` — non-interactive single query
- `-p` / `--print` — print mode (no interactive)
- `-c` / `--continue` — resume last conversation
- `-r` / `--resume` — resume by session ID or name
- `-n` / `--name` — set session display name
- `--model` — select model
- `--permission-mode` — set permission mode at startup
- `--dangerously-skip-permissions` — bypass all confirmations
- `--allow-dangerously-skip-permissions` — add bypassPermissions to Shift+Tab cycle
- `--enable-auto-mode` — unlock auto mode in Shift+Tab cycle
- `--max-turns` — limit agentic turns
- `--max-budget-usd` — spending cap
- `--output-format` — `text`, `json`, `stream-json`
- `--input-format` — `text`, `stream-json`
- `--system-prompt` / `--system-prompt-file` — replace system prompt
- `--append-system-prompt` / `--append-system-prompt-file` — append to system prompt
- `--add-dir` — extend working directories
- `--mcp-config` — load MCP config from file
- `--strict-mcp-config` — only use `--mcp-config` servers
- `--agent` — use specific subagent for whole session
- `--agents` — define session-only subagents via JSON
- `--worktree` / `-w` — run in isolated git worktree
- `--tmux` — create tmux session for worktree
- `--verbose` — detailed logging
- `--debug [categories]` — debug mode with filtering
- `--debug-file <path>` — write debug to specific file
- `--bare` — minimal mode (skip hooks, skills, plugins, MCP, memory, CLAUDE.md)
- `--no-session-persistence` — ephemeral sessions
- `--json-schema` — structured JSON output
- `--effort` — effort level (low/medium/high/xhigh/max)
- `--fork-session` — create new session ID when resuming
- `--fallback-model` — automatic fallback on overload
- `--include-partial-messages` — streaming events in output
- `--include-hook-events` — include hook events in stream-json output
- `--betas` — beta headers for API
- `--channels` — listen for channel notifications
- `--chrome` / `--no-chrome` — Chrome browser integration
- `--disable-slash-commands` — disable all skills and commands
- `--disallowedTools` — remove tools from model context
- `--allowedTools` — tools that execute without permission prompt
- `--tools` — restrict which built-in tools Claude can use
- `--ide` — auto-connect to IDE on startup
- `--init` / `--init-only` — run initialization hooks
- `--maintenance` — run maintenance hooks
- `--from-pr` — resume sessions linked to GitHub PR
- `--remote` — create new web session on claude.ai
- `--remote-control` / `--rc` — start session with Remote Control enabled
- `--teleport` — resume web session in local terminal
- `--teammate-mode` — how agent team teammates display
- `--permission-prompt-tool` — MCP tool for permission prompts in non-interactive mode
- `--plugin-dir` — load plugins from directory (session only)
- `--replay-user-messages` — re-emit user messages for acknowledgment
- `--session-id` — use specific session UUID
- `--setting-sources` — control which setting scopes load
- `--settings` — load additional settings from file/JSON
- `--exclude-dynamic-system-prompt-sections` — improve cross-user prompt caching in print mode
- `claude agents` — list configured subagents
- `claude auto-mode defaults` — print auto mode rules
- `claude remote-control` — start Remote Control server mode
- `claude auth` — authentication (login, logout, status)
- `claude mcp` — configure MCP servers
- `claude plugin` — manage plugins
- `claude setup-token` — generate OAuth token
- `claude update` — update to latest version

### Zrb

`zrb llm chat` with inputs:
- `--message` / `-m` — initial message
- `--model` — model selection
- `--session` — conversation session name
- `--yolo` — bypass confirmations (full or selective: `--yolo "Write,Edit"`)
- `--attach` — file attachments
- `--interactive` — toggle interactive mode
- `--help` — help text

**Status**: 🟡 **Partially supported**

**Gap**: Zrb covers the most common use cases but lacks ~60 of Claude Code's CLI flags. Critical missing: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--json-schema`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--tools`, `--disallowedTools`, `--debug`, `--plugin-dir`, `--remote-control`, `--channels`, `--chrome`.

**Effort to close**:
- **Medium** (2–3 weeks): Map each Claude Code flag to existing Zrb config options and expose them as CLI inputs on `LLMChatTask`. The underlying infrastructure (rate limiting, session management, YOLO) already exists.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich interactive TUI:
- Vim mode (`/vim` or via `/config`) with full NORMAL/INSERT/navigation
- Voice input (push-to-talk)
- `!` bash prefix — run shell command and add to conversation
- `@` file path mention with autocomplete (respects `.gitignore` via `respectGitignore` setting)
- Custom `@` suggestion script (`fileSuggestion` setting)
- `/` command palette
- Multiline input (Shift+Enter, Option+Enter, `\`+Enter, Ctrl+J)
- Keyboard shortcuts: Ctrl+C, Ctrl+D, Ctrl+L, Ctrl+O (verbose), Ctrl+R (history search)
- Ctrl+B — background bash commands
- Ctrl+T — toggle task list
- Esc+Esc — rewind/checkpoint menu
- Shift+Tab — cycle permission modes
- Alt+M — cycle permission modes
- Option+P — switch model without clearing prompt
- Option+T — toggle extended thinking
- Option+O — toggle fast mode
- Tab / Right arrow — accept prompt suggestions
- Ctrl+V / Cmd+V — paste image from clipboard
- `/btw` — side question without polluting history
- Prompt suggestions (grayed-out from git history, follow-up suggestions)
- PR review status in footer
- Transcript viewer (Ctrl+O)
- Color themes (`/theme`)
- Status line with configurable components
- Ctrl+X Ctrl+K — kill all background agents
- `Ctrl+G` / `Ctrl+X Ctrl+E` — open in external editor
- Command history per working directory (Ctrl+R)
- Session branching (`/branch` / `/fork`)
- `/rename` — change session name mid-conversation
- Terminal progress bar (ConEmu, Ghostty, iTerm2)
- Spinner tips (configurable, custom verbs)
- Reduced motion setting (`prefersReducedMotion`)
- Deep link support (`claude-cli://open?q=...`)

### Zrb

`prompt_toolkit`-based TUI (`src/zrb/llm/ui/`):
- Multi-line input support (trailing `\` continuation)
- Command history with reverse search
- **`!` bash prefix** — `! cmd` or `/exec cmd` runs shell and injects output (`base_ui.py`)
- **`@` file mention** — `@path/to/file` in message body expands to file reference; autocomplete via `completion.py`
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach` — explicit file attachment command
- `/model` — switch model mid-conversation
- `/yolo` — toggle YOLO mode (supports selective: `/yolo Write,Edit`)
- `/save` / `/load` — persist/restore sessions; `/load` displays conversation history
- `/compress` / `/compact` — summarize conversation
- `>` / `/redirect` — save last output to file
- **`/btw`** — side question without saving to history ✅
- **Image clipboard paste** — Ctrl+V paste support ✅
- **`/rewind`** — restore filesystem + conversation to a previous snapshot ✅
- **ChatGPT-like interface** — alternate UI layout
- **MultiUI** — broadcast to multiple channels simultaneously (terminal + Telegram + web), first-response-wins for input ✅ **NEW in v2.14.0**
- Session persistence
- Configurable greeting, ASCII art, jargon
- Tool approval dialogs with formatted output
- Streaming responses
- Git branch + dirty status in UI info area
- **Active worktree shown in system context** ✅ **NEW in v2.22.3**

**Status**: 🟡 **Partially supported**

**Gap**: Zrb now has `!`, `@`, `/`, `/btw`, image paste, `/rewind`, and MultiUI. Still missing: Vim mode, voice input, permission mode cycling (Shift+Tab), extended thinking toggle, background task management (Ctrl+B), task list toggle (Ctrl+T), Esc+Esc rewind shortcut, prompt suggestions from git history, transcript viewer, color themes, configurable status line, session branching (`/branch`/`/fork`), terminal progress bar, custom `@` suggestion scripts.

**Effort to close**:
- **Medium** (3–5 weeks):
  1. Shift+Tab permission mode cycling (1 day)
  2. Background bash tasks / Ctrl+B (1 week)
  3. Prompt suggestions from git history (1 week)
  4. Vim mode (2–3 weeks) — significant `prompt_toolkit` work
  5. Color themes (1–2 days)
  6. Voice input (2–3 weeks)

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~55+): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/cost`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw`, `/tasks`, `/permissions`, `/security-review`, `/stats`, `/theme`, `/voice`, `/agents`, `/rename`, `/schedule`, `/effort`, `/desktop`, `/fast`, `/statusline`, etc.

**Bundled skills** as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`, `/team-onboarding`, `/proactive`

**Custom skills** become slash commands automatically.

**MCP prompts** become `/mcp__<server>__<prompt>` commands.

**Features**: argument interpolation (`$ARGUMENTS`, `$N`), dynamic context injection (`` !`command` ``), command palette with fuzzy search, `--disable-slash-commands` flag to disable all.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1` (positional)
- Skill-based commands via `get_skill_custom_command(skill_manager)`
- Commands registered with `LLMChatTask.add_custom_command()`
- Skills become slash commands via their `name` metadata
- Interactive command palette (via `prompt_toolkit`)

Built-in slash commands:
- `/compress` / `/compact` — summarize conversation
- `/attach` — attach file to next message
- `/q`, `/bye`, `/quit`, `/exit` — exit session
- `/info`, `/help` — show help
- `/save <name>` — save conversation
- `/load <name>` — load conversation + display history
- `/yolo [tools]` — toggle YOLO mode (full or selective)
- `>`, `/redirect` — save last output to file
- `!`, `/exec` — execute shell command and inject output
- `/model <name>` — set model mid-conversation
- `/btw <question>` — side question without history ✅
- `/rewind` — restore filesystem + conversation to snapshot ✅
- Custom skill commands auto-registered from skill files

**Status**: 🟡 **Partially supported**

**Gap**: Core command infrastructure works. Missing: ~40 built-in management commands (`/clear`, `/config`, `/diff`, `/branch`, `/export`, `/cost`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/stats`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/effort`, `/rename`, `/desktop`, `/fast`, `/statusline`), MCP prompts as commands, bundled utility skills like `/batch`, `/loop`, `/simplify`.

**Effort to close**:
- **Medium** (3–5 weeks): Most built-in commands are wrappers over existing functionality.

---

## 4. Memory System

### Claude Code

**Two mechanisms:**

**CLAUDE.md files** (human-authored):
- Managed/enterprise: system-wide policy
- User-level: `~/.claude/CLAUDE.md` (applies to all projects)
- Project-level: `./CLAUDE.md` or `./.claude/CLAUDE.md` (team-shared)
- **`CLAUDE.local.md`** — local (gitignored) personal overrides
- Subdirectory: lazy-loaded when Claude reads files in that dir
- `@import` syntax for including other files (max 5 hops)
- `claudeMdExcludes` to skip files
- `.claude/rules/` for path-scoped rules (YAML `paths:` frontmatter)
- `<!-- comments -->` stripped before context injection
- Skills from `--add-dir` are loaded; CLAUDE.md from `--add-dir` are not by default (set `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`)

**Auto memory** (Claude-authored):
- Claude writes its own notes during conversations
- Stored: `~/.claude/projects/<project>/memory/MEMORY.md` + topic files
- First 200 lines or 25KB loaded at session start
- Toggle: `/memory` command or `autoMemoryEnabled` setting
- Custom directory via `autoMemoryDirectory` setting

### Zrb

**CLAUDE.md / AGENTS.md / GEMINI.md / README.md auto-loading** (`src/zrb/llm/prompt/claude.py`):
- `create_project_context_prompt()` included in `PromptManager` by default
- Search path: `~/.claude/` → filesystem root → … → CWD (all parents + CWD)
- Loads `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md` from every directory
- Content: most specific occurrence (closest to CWD) loaded, up to `MAX_PROJECT_DOC_CHARS = 4000` chars
- All occurrences listed; model told to `Read` others on demand
- Toggle via `LLM_INCLUDE_PROJECT_CONTEXT` env var

**Journal system** (analog to Claude Code's auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`) — persistent notes written by LLM or user
- Injected into LLM context via `PromptManager`
- Read/write/search via journal tools; auto-approved for journal dir
- **Bidirectional journal graph** ✅ **NEW in v2.20.1**: Backlinks protocol, every forward link requires a backlink entry, step-by-step guide embedded in skill
- **Granular journal control** ✅ **NEW in v2.22.6**: `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` (controls system prompt section) and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` (controls end-of-session reminder) independently

**Companion files** ✅ **NEW in v2.22.1**: `ActivateSkill` now returns the skill's directory path and companion file listing alongside the skill content, enabling skills to reference templates and examples.

**Status**: 🟡 **Partially supported**

**Gap**: CLAUDE.md auto-loading implemented. Missing:
- 4000-char truncation limit per file (should be configurable or removed)
- `CLAUDE.local.md` gitignored personal overrides
- `@import` syntax for chaining memory files
- `.claude/rules/` path-scoped rules with YAML `paths:` frontmatter
- `claudeMdExcludes` to skip files
- `<!-- comments -->` stripping before injection
- Subdirectory lazy-loading
- `/memory` command to list/toggle/edit memory files interactively
- `autoMemoryDirectory` custom directory setting

**Effort to close**:
- **Low-Medium** (1–2 weeks):
  1. Raise/remove 4000-char limit or make configurable (1 day)
  2. `CLAUDE.local.md` support (1 day)
  3. `<!-- comments -->` stripping (1 day)
  4. Implement `@import` syntax (2–3 days)
  5. `.claude/rules/` path-scoped rule loading (3–5 days)
  6. `/memory` interactive management command (2–3 days)

---

## 5. Hooks System

### Claude Code

**27 hook events** across 8 categories:
- Session: `SessionStart`, `SessionEnd`, `InstructionsLoaded`
- User: `UserPromptSubmit`, **`UserPromptExpansion`** (new)
- Tool: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, **`PostToolBatch`** (new), `PermissionRequest`, `PermissionDenied`
- Agent teams: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`
- Claude response: `Stop`, `StopFailure`
- File/env: `CwdChanged`, `FileChanged`, `ConfigChange`
- Compaction: `PreCompact` (can block compaction by exiting 2), `PostCompact`
- MCP: `Elicitation`, `ElicitationResult`
- Worktree: `WorktreeCreate`, `WorktreeRemove`
- Notification: `Notification`

**5 handler types**:
1. `command` (shell) — exit codes: 0 (success), 2 (blocking error)
2. `http` (POST request) — 2xx responses parsed as JSON
3. **`mcp_tool`** (call tool on MCP server, **new**) — path substitution `${tool_input.field}`; non-blocking if disconnected
4. `prompt` (Claude eval) — custom model and timeout
5. `agent` (sub-agent with tools)

**Features**:
- Conditional execution via `if` field (permission rule syntax)
- Async hooks (`"async": true`) — command hooks only
- `statusMessage` for spinner
- `once` per session (skills)
- Decision output: `allow`, `deny`, `ask`, `defer`, `block` (compaction blocking)
- `additionalContext` injection
- `updatedInput` for modifying tool inputs
- `CLAUDE_ENV_FILE` for persisting env vars
- `allowedHttpHookUrls` security allowlist
- `httpHookAllowedEnvVars` env var allowlist
- `allowManagedHooksOnly` policy
- `disableAllHooks` setting
- Config locations: user, project, local, managed policy, plugin, skill/agent frontmatter
- `/hooks` management UI
- Plugin `monitors` manifest key for auto-armed background monitors

### Zrb

**9 hook events** (`src/zrb/llm/hook/types.py`):
- `SESSION_START`, `SESSION_END`
- `USER_PROMPT_SUBMIT`
- `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE`
- `NOTIFICATION`
- `STOP`
- `PRE_COMPACT`

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent)

**Features**:
- Operator-based matchers: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`
- Async/sync execution with timeouts (`HOOKS_TIMEOUT`, default 30000ms)
- Skill frontmatter hook definitions
- `HookManager` singleton with YAML/JSON config and factory registration (`add_hook_factory()`)
- Config from: `HOOKS_DIRS`, `HOOKS_TIMEOUT`
- Claude Code string compatibility mapping
- **`HookResult.with_system_message(replace_response=True/False)`** ✅ **NEW in v2.18.0**: `replace_response=True` replaces Claude's response; `False` runs as side effect
- **`HookResult.with_additional_context()`** — injects additional context into conversation
- **Built-in journaling hook** ✅ **NEW in v2.18.0**: Auto-registered when `LLM_INCLUDE_JOURNAL=on`; fires reminder at `SESSION_END` after meaningful activity
- **Hook factory registration** ✅ **NEW in v2.18.0**: `add_hook_factory()` for dynamic config-driven hook registration

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has 9 of Claude Code's 27 events (33%). Missing events: `InstructionsLoaded`, `StopFailure`, `CwdChanged`, `FileChanged`, `ConfigChange`, `PostCompact`, `Elicitation`, `ElicitationResult`, `WorktreeCreate`, `WorktreeRemove`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `PermissionRequest`, `PermissionDenied`, `UserPromptExpansion`, `PostToolBatch`. Missing handler types: `http`, `mcp_tool`. Missing features: `CLAUDE_ENV_FILE` persistence, `once` flag, `statusMessage`, `/hooks` management UI, conditional `if` field, `allowedHttpHookUrls`, `allowManagedHooksOnly`, `updatedInput` modification.

Note: Zrb has `with_additional_context()` and `with_system_message()` which partially cover `additionalContext` and `updatedInput` patterns.

**Effort to close**:
- **Medium-High** (4–5 weeks):
  1. Add missing event types to `HookEvent` enum (1–2 days)
  2. Fire missing events at appropriate lifecycle points (1 week)
  3. Add `http` handler type (2–3 days)
  4. Add `mcp_tool` handler type (2–3 days)
  5. Add `if` conditional field, `once` flag, `statusMessage`, async flag (2–3 days)
  6. `allowedHttpHookUrls` / `allowManagedHooksOnly` security settings (2 days)
  7. `CLAUDE_ENV_FILE` persistence mechanism (2 days)
  8. `/hooks` management command in TUI (2–3 days)

---

## 6. MCP (Model Context Protocol)

### Claude Code

**Transports**: `stdio`, `http`, `sse`, `ws`

**Config scopes** (priority order):
1. Managed: `managed-settings.json` `mcpServers` key
2. User: `~/.claude.json` (user-scoped)
3. Local project: `~/.claude.json` (per-project)
4. Project: `.mcp.json`
5. CLI: `--mcp-config` flag

**Features**:
- `claude mcp add` CLI command for easy setup
- OAuth authentication for MCP servers
- MCP prompts become `/mcp__<server>__<prompt>` commands
- MCP tool search (deferred tools for scale)
- MCP resources (`ListMcpResourcesTool`, `ReadMcpResourceTool`)
- Subagent-scoped MCP servers
- `allowManagedMcpServersOnly` / `deniedMcpServers` policy
- `--strict-mcp-config`
- `/mcp` command for interactive management
- `enableAllProjectMcpServers`, `enabledMcpjsonServers`, `disabledMcpjsonServers` settings
- `allowedMcpServers` managed allowlist
- Channels for MCP server notifications (research preview)
- Centralized MCP registry with marketplace support
- `extraKnownMarketplaces` for custom sources

### Zrb

- Transports: `stdio`, `sse`
- Config: `mcp-config.json` searched from home → project hierarchy → CWD
- Environment variable expansion in config
- Integrated via `load_mcp_config()` in `LLMChatTask`
- Uses Pydantic AI's `MCPServerStdio` / `MCPServerSSE`
- Configurable retry count via `LLM_MCP_MAX_RETRIES` (default: 3)

**Status**: 🟡 **Partially supported**

**Gap**: Core MCP functionality works (`stdio`, `sse`). Missing: `http` and `ws` transports, CLI command for easy server addition (`zrb mcp add`), OAuth authentication, MCP prompts as slash commands, MCP tool search/deferred loading, MCP resources tools, subagent-scoped MCP, `/mcp` interactive management UI, managed-only policy, granular enable/disable per server, MCP registry/marketplace, Channels (MCP notifications).

**Effort to close**:
- **Medium** (3–4 weeks):
  1. `ws` and `http` transport support (3–5 days, depends on Pydantic AI)
  2. `zrb mcp add` CLI command (2 days)
  3. MCP prompts → slash commands auto-discovery (3–4 days)
  4. MCP resources tools (2–3 days)
  5. `/mcp` management UI (2–3 days)
  6. OAuth support (1–2 weeks, complex)
  7. Deferred/lazy tool loading for scale (1 week)

---

## 7. Subagents / Multi-Agent Orchestration

### Claude Code

Declarative subagent system via markdown files with YAML frontmatter:
- File locations: managed > `--agents` flag > `.claude/agents/` > `~/.claude/agents/` > plugin `agents/`
- Frontmatter fields: `name`, `description`, `prompt`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `initialPrompt`, `color`, `persistent memory directory`
- Invocation: natural language, `@-mention` (guaranteed), `--agent` flag, `agent` setting, `/agents` command
- Foreground vs background: Ctrl+B to background
- Subagent context compaction (auto at ~95%)
- Tool access control: `tools` allowlist, `disallowedTools` denylist
- Subagent isolation: `isolation: worktree`
- Subagent memory: `memory: user/project/local` → persistent memory directory at `~/.claude/agent-memory/`
- Auto-delegation based on description matching
- `/agents` interactive management UI
- `claude agents` CLI command
- Managed subagents (organization-wide deployment)

**Built-in subagents**: Explore, Plan, general-purpose, Bash, statusline-setup, Claude Code Guide

### Zrb

Delegate tool system:
- `create_delegate_to_agent_tool()` — sequential sub-agent call
- `create_parallel_delegate_tool()` — concurrent multi-agent (`DelegateToAgentsParallel`)
- `SubAgentManager` with tool registry, lazy-loading from filesystem
- Tool/toolset factories for dynamic resolution at execution time
- `BufferedUI` for output synchronization
- Agent discovery from `.agent.md` files in `agents/` directories
- Shared rate limiter across agents
- Foreground/background via async execution
- **`SubAgentManager` uses `llm_config.resolve_model()`** ✅ **NEW in v2.22.0**: Sub-agents now respect global model getter/renderer pipeline
- **Agent .md filtering fixed** ✅ **NEW in v2.22.3**: Only `.md` files directly inside an `agents/` directory recognized as agents
- **Active worktree in delegate messages** ✅ **NEW in v2.22.3**: Sub-agents reminded to use `cwd` and absolute paths

**Built-in agents** (in `src/zrb/llm_plugin/agents/`):
- `generalist` (was `subagent`), `researcher`, `code-reviewer`

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has working multi-agent delegation but implemented as tools (programmatic), not as declarative YAML/Markdown files that Claude auto-discovers via `@-mention`. Missing: file-based agent definitions with full frontmatter support (`.zrb/agents/` / `.claude/agents/`), `@-mention` invocation, subagent-specific `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `initialPrompt`, `color`, persistent agent memory directory, `/agents` management UI, `claude agents` CLI command, managed subagents.

**Effort to close**:
- **High** (6–8 weeks):
  1. File-based agent definition loader with full frontmatter parsing (1 week)
  2. `@-mention` in TUI input with agent typeahead (3–4 days)
  3. Natural language delegation (3–4 days)
  4. Per-agent permission mode, maxTurns, memory (1 week)
  5. Subagent-scoped MCP (1 week)
  6. Worktree isolation per agent (1–2 weeks)
  7. `/agents` management UI (3–4 days)

---

## 8. Agent Teams (Experimental)

### Claude Code

- Multiple Claude Code instances working together
- Shared task list with self-coordination
- Inter-agent direct messaging (`SendMessage` tool)
- Display modes: in-process (Shift+Down to cycle) or split tmux panes (`--teammate-mode`)
- `TeamCreate` / `TeamDelete` tools
- File locking for race condition prevention
- Task dependencies between team members
- Hooks: `TeammateIdle`, `TaskCreated`, `TaskCompleted`
- Storage: `~/.claude/teams/`, `~/.claude/tasks/`
- Subagent definitions usable as teammate specs
- `--teammate-mode` flag: `auto`, `in-process`, `tmux`
- `teammateMode` config setting

### Zrb

`create_parallel_delegate_tool()`:
- Concurrent multi-agent execution
- Aggregated results
- Shared rate limiter and UI lock
- Error handling per agent

No team coordination, no inter-agent messaging, no shared task list.

**Status**: ❌ **Not supported** (parallel delegation exists but not agent teams)

**Gap**: Zrb's parallel delegation is a tool call, not persistent coordinated agents. Missing: persistent agent team lifecycle, inter-agent messaging, shared task list with dependencies, display modes (tmux split), team-specific hooks, file locking, `TeamCreate`/`TeamDelete`, `--teammate-mode`.

**Effort to close**:
- **Very High** (8–12 weeks): Fundamentally different architecture.

---

## 9. Skills System

### Claude Code

File-based skill system (`.claude/skills/<skill-name>/SKILL.md` or `.claude/commands/<name>.md`):
- Scopes: managed/enterprise > personal > project > plugin
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `effort`, `context` (fork), `agent`, `hooks`, `paths`, `shell`
- Supporting files in skill directory (templates, examples, scripts)
- String substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`
- Dynamic context injection: `` !`command` `` runs shell at load time; fenced `` ```! `` for multi-line
- Skills in forked subagent context (`context: fork`, `agent: Explore`)
- `allowed-tools` grants pre-approval for tool calls during skill
- Path-scoped activation (`paths:` glob patterns)
- Monorepo auto-discovery from nested `.claude/skills/`
- Skills from `--add-dir` directories are loaded
- `disableSkillShellExecution` managed policy setting
- Bundled skills: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`
- Follows [Agent Skills](https://agentskills.io) open standard

### Zrb

Comprehensive skill system (`src/zrb/llm/skill/`):
- File types: `.skill.md`, `.skill.py`
- Scopes: default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`) — hierarchy root→CWD
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`
- Auto-scan on first access, manual reload (lazy initialization via `_ensure_scanned()`)
- Lazy file reading with content caching
- Factory function support for dynamic skills
- `get_skill_custom_command()` maps skills to slash commands
- `create_activate_skill_tool()` for Claude to invoke skills
- **`ActivateSkill` returns companion files** ✅ **NEW in v2.22.1**: Returns skill directory path and companion file listing

Built-in skills in `src/zrb/llm_plugin/skills/`:
- `core-coding`, `core-journaling`, `research-and-plan`, `testing`, `debug`, `review`, `refactor`, `skill-creator`, `git-summary`, `init`

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` frontmatter field, `hooks` in skill frontmatter, `paths:` glob activation patterns, `shell` field, `` !`command` `` dynamic context injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitution variables, bundled utility skills (`/batch`, `/loop`, `/simplify`, `/claude-api`).

**Effort to close**:
- **Low** (1–2 weeks):
  1. Add `effort`, `hooks`, `paths`, `shell` frontmatter fields (2–3 days)
  2. `` !`command` `` preprocessing at load time (1–2 days)
  3. `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR` substitutions (1 day)
  4. Add `/loop` and `/simplify` bundled skills (2–3 days each)

---

## 10. Permission Modes & Tool Approval

### Claude Code

**6 permission modes**:
- `default` — read-only auto-approve; prompt for write/execute
- `acceptEdits` — auto-approve reads and file edits
- `plan` — read-only; Claude plans but doesn't execute
- `auto` — all actions with background safety classifier (Team/Enterprise + Sonnet 4.6/Opus 4.6 only)
- `bypassPermissions` — no checks (containers/VMs only)
- `dontAsk` — auto-deny everything not pre-approved

**Mode switching**: Shift+Tab cycling during session; `--permission-mode` flag at startup; `defaultMode` setting.

**Permission rules**: `Tool`, `Tool(specifier)`, glob patterns, domain restricts, MCP tool patterns
- Evaluation: deny > ask > allow (first match wins)
- Config levels: managed > CLI > local > project > user
- `allow`, `ask`, `deny`, `additionalDirectories` in settings

**PermissionRequest hook**: intercept permission dialogs
**PermissionDenied hook**: retry on auto-mode denial

### Zrb

**Tool approval system**:
- YOLO mode (`--yolo`) = full `bypassPermissions`
- **Selective YOLO** ✅ **NEW in v2.18.0** — `--yolo "Write,Edit"` or `/yolo Write,Edit` auto-approves only specified tools; UI displays `[Write,Edit]` in yellow
- `auto_approve()` function with condition callbacks
- `approve_if_path_inside_cwd`, `approve_if_path_inside_journal_dir` conditions
- Per-tool validation policies: `replace_in_file_validation_policy`, `read_file_validation_policy`
- **`bash_safe_command_policy`** ✅ **NEW in v2.18.0** — auto-approves known-safe read-only commands (`ls`, `git status`, `cat`); rejects dangerous metacharacters
- Tool call confirmation dialogs in TUI
- `ApprovalChannel` class for async approval
- Multiplex approval channels (terminal + Telegram simultaneously)
- **`MultiplexApprovalChannel`** ✅ **NEW in v2.14.0** — first response wins, cancels pending on other channels
- Override tool args at approval time (via `ApprovalResult.override_args`)

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has YOLO mode (full and selective) and per-tool approval policies. Missing: named permission modes beyond YOLO/non-YOLO, `acceptEdits` mode, `plan` mode (read-only planning), `dontAsk` mode, `auto` mode with safety classifier, Shift+Tab cycling, permission rules configuration syntax (glob patterns, domain restricts, `Bash(npm run *)` style), `PermissionRequest` / `PermissionDenied` hooks, rule evaluation precedence, admin-managed permission policies.

**Effort to close**:
- **Medium-High** (4–6 weeks):
  1. Named permission mode enum + state (1 day)
  2. `plan` mode (read-only enforcement) (3–4 days)
  3. `acceptEdits` mode (1 day)
  4. `dontAsk` mode (2 days)
  5. Permission rules config syntax parser (1 week)
  6. Rule evaluation engine with deny>ask>allow precedence (3–4 days)
  7. Shift+Tab mode cycling in TUI (1 day)
  8. `PermissionRequest` / `PermissionDenied` hook events (2 days)

---

## 11. Settings & Configuration System

### Claude Code

**4 config scopes**: managed (system) > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`)

**JSON schema** at `https://json.schemastore.org/claude-code-settings.json` for autocomplete

**Key settings categories**: permissions, model, UI/UX, auto-updates, shell, hooks, files, plugins, worktrees, memory, MCP, voice, attribution, environment, sandbox

**`/config` command**: interactive tabbed settings UI

**Global config** in `~/.claude.json`: `editorMode` (vim/normal), `autoConnectIde`, `showTurnDuration`, `terminalProgressBarEnabled`, `teammateMode`

**Server-managed settings**: remote delivery via Claude.ai admin console; MDM/OS-level policies (macOS plist, Windows registry); file-based `managed-settings.json` with drop-in `managed-settings.d/` directory.

### Zrb

**Single config source**: `CFG` singleton loaded from environment variables (prefix: `ZRB_`)

Categories: `ZRB_LLM_MODEL`, `ZRB_LLM_API_KEY`, `ZRB_WEB_HTTP_PORT`, `ZRB_LLM_MAX_TOKENS`, rate limits, directories, UI, search, hooks, MCP, RAG, timeouts, intervals, sizes, retries.

**All magic numbers configurable since v2.20.0**: timeout configs (ms), interval configs (ms), size/limit configs, retry configs, pagination configs, model visibility controls.

**New in v2.21.0** — Tool Guidance System:
- `ToolGuidance` dataclass for declarative per-tool usage hints
- `add_tool_guidance()` / `add_tool_guidance_factory()` on `LLMTask` and `LLMChatTask`
- `CFG.LLM_INCLUDE_TOOL_GUIDANCE` toggle (default: `on`)

**New in v2.22.0** — Global Model Pipeline:
- `LLMConfig.model_getter` and `model_renderer` for centralized model routing
- `llm_config.resolve_model(base_model=None)` method
- Task-level overrides config-level defaults

**New in v2.22.6** — Retry Configuration:
- `LLM_API_MAX_RETRIES` (default: 3) — transient provider error retries
- `LLM_API_MAX_WAIT` (default: 60s) — max exponential backoff wait

**New in v2.22.6** — Granular Journal Config:
- `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` — controls journal mandate in system prompt
- `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` — controls end-of-session reminder independently

**Status**: 🟡 **Partially supported**

**Gap**: Zrb's config is env-var only (no JSON settings files), no layered scopes (user/project/local/managed), no `/config` interactive UI, no JSON schema validation, no managed/enterprise policy layer, no server-managed settings.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. JSON settings file loader with scope hierarchy (1 week)
  2. Merge settings with env vars (2 days)
  3. JSON schema generation (2–3 days)
  4. `/config` interactive settings UI in TUI (1 week)

---

## 12. Built-in Tools

### Claude Code (38+ tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` |
| `Write` | ✅ `write_file` |
| `Edit` | ✅ `replace_in_file` (fuzzy match added v2.22.6) |
| `Bash` | ✅ `run_shell_command` (actionable suggestions, 120s default timeout v2.22.6) |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` (ripgrep acceleration v2.22.3) |
| `Agent` (spawn subagent) | 🟡 `create_delegate_to_agent_tool` (programmatic, not declarative) |
| `WebFetch` | ✅ `open_web_page` |
| `WebSearch` | ✅ `search_internet` (SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | 🟡 Exists as hook/approval but not standalone LLM tool |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full LSP tool suite |
| `TaskCreate/Get/List/Update/Stop` | ✅ `write_todos`, `get_todos`, `update_todo`, `clear_todos` (system context integration v2.22.3) |
| `CronCreate/Delete/List` | ❌ Not implemented as LLM tools |
| `EnterPlanMode` / `ExitPlanMode` | 🟡 `CreatePlan`, `ViewPlan`, `UpdatePlan` exist but no plan mode enforcement |
| `EnterWorktree` / `ExitWorktree` | ✅ Fully implemented (`enter_worktree`, `exit_worktree`, `list_worktrees`) with ContextVar tracking (v2.22.3) |
| `Monitor` (stream background events) | ❌ Not implemented |
| `SendMessage` (agent teams) | ❌ Agent teams not implemented |
| `TeamCreate` / `TeamDelete` | ❌ Agent teams not implemented |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` | ❌ Not implemented |
| `ReadMcpResourceTool` | ❌ Not implemented |
| `PowerShell` | ❌ Not implemented (Windows-only) |
| `Skill` (invoke skills) | ✅ `create_activate_skill_tool()` (returns companion files v2.22.1) |
| `RemoteTrigger` | ❌ Not implemented |

**Additional Zrb tools not in Claude Code** 🔵:
- `read_files` (batch read multiple files)
- `write_files` (batch write multiple files)
- `analyze_file` (AST-based code analysis)
- `analyze_code` (code structure analysis with ripgrep acceleration)
- `create_rag_from_directory` (RAG embeddings with ChromaDB)
- `create_list_zrb_task_tool` (list Zrb tasks)
- `create_run_zrb_task_tool` (run Zrb tasks as tools)
- `create_activate_skill_tool` (invoke skills)
- `create_parallel_delegate_tool` (parallel multi-agent)
- Long-term note tools (`ReadLongTermNote`, `ReadContextualNote`)
- `CreatePlan`, `ViewPlan`, `UpdatePlan` (planning system)
- **Tool Guidance System** (`add_tool_guidance()` / `add_tool_guidance_factory()`) for per-tool hints ✅ **NEW in v2.21.0**

**Status**: 🟡 **Partially supported**

**Gap**: Core file/shell/web/worktree tools are well-covered. Missing: `AskUserQuestion` as standalone tool, `NotebookEdit`, `CronCreate/Delete/List`, `Monitor`, `SendMessage`, `TeamCreate`/`TeamDelete`, `ToolSearch`, MCP resource tools, `RemoteTrigger`, `PowerShell`.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. `AskUserQuestion` tool (2–3 days)
  2. `NotebookEdit` for Jupyter notebooks (3–4 days)
  3. `CronCreate`/`CronDelete`/`CronList` (3–4 days, reuse Zrb's Scheduler)
  4. `ToolSearch` deferred loading (1 week)

---

## 13. IDE Integrations

### Claude Code

**VS Code Extension**:
- Native graphical panel, sidebar, or new tab
- Inline diff review with accept/reject
- `@`-mention files/folders with fuzzy search
- Selection context sharing
- Drag files as attachments
- Multiple conversations in tabs/windows
- Resume past/remote conversations
- Plugin management UI
- Auto-install extension when running in VS Code terminal

**JetBrains Plugin**:
- IntelliJ IDEA, PyCharm, WebStorm, etc.
- Interactive diff viewing
- Selection context sharing
- Shift+Tab permission mode cycling

**Desktop App**:
- Standalone macOS/Windows application
- Visual diff review
- Multiple sessions side by side
- Computer use (macOS)
- `Dispatch` — send tasks from phone, desktop opens session
- Desktop scheduled tasks
- `/desktop` command to hand off terminal session

### Zrb

**Web UI** (FastAPI-based):
- Browser-based chat interface
- Session persistence (SQLite backend since v2.15.0)
- Model switching
- YOLO mode toggle
- Authentication (JWT)
- SSE streaming
- **ChatGPT-like interface** layout ✅
- Tool approval in browser (edit tool call args on-the-fly)
- **HTTP Chat API** 🔵 **NEW in v2.15.0**: REST endpoints for programmatic access (create/delete sessions, send messages, SSE stream, history management)
- **Jinja2 templates + local mermaid.js** ✅ **NEW in v2.22.4**: Better frontend with no external CDN dependency

No VS Code / JetBrains / Desktop app integration.

**Status**: ❌ **Not supported** (IDE integrations); 🟡 Web UI is a different paradigm

**Effort to close**:
- **Very High** (3–6 months for full parity)

---

## 14. Session Management & Checkpointing

### Claude Code

**Checkpointing**:
- Automatic checkpoint before every file edit
- Every user prompt creates a new checkpoint
- Persist across sessions (30 days by default, `cleanupPeriodDays`)
- Rewind menu (Esc+Esc): restore code+conversation, restore conversation only, restore code only
- `/rewind` command
- Session branching (`/branch` / `/fork`)

**Session management**:
- Sessions stored per working directory
- `--continue` / `-c` resumes last session
- `--resume` / `-r` resumes by ID or name, or shows picker
- `--name` / `-n` set session display name; `/rename` mid-session
- `--fork-session` creates new ID when resuming
- `--from-pr` resumes sessions linked to GitHub PR
- `--no-session-persistence` for ephemeral sessions
- Session export (`/export`)
- Session statistics (`/stats`, `/insights`)
- Auto-timestamped config file backups (5 most recent)

### Zrb

**Session management**:
- `FileHistoryManager` stores conversation history to disk (`~/.zrb/history/{name}.json`)
- Named sessions via `--session` input
- Conversation persistence per session name
- Automatic timestamped backups (format: `<session>-YYYY-MM-DD-HH-MM-SS.json`)
- History summarization on long contexts
- `/load <name>` displays loaded conversation history with icons
- Fuzzy search for session discovery
- `NoSaveHistoryManager` for ephemeral sessions (equivalent to `--no-session-persistence`)
- **SQLite-backed sessions** ✅ **NEW in v2.15.0**: `ChatSessionManager` for web UI session storage with full CRUD

**Rewind / Snapshot system** ✅:
- `SnapshotManager` using shadow git repositories for filesystem snapshots
- `/rewind` command — interactive picker to restore filesystem + conversation history
- Three restore modes: filesystem + conversation, conversation only, filesystem only
- Snapshots track message count for consistent history restoration
- Default snapshot location: `~/.zrb/llm-snapshots/`
- Config: `LLM_ENABLE_REWIND=on`, `LLM_SNAPSHOT_DIR`, `LLM_UI_COMMAND_REWIND`

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has rewind/snapshot and ephemeral sessions. Key remaining gaps: rewind is opt-in (`LLM_ENABLE_REWIND=on`) rather than automatic; no Esc+Esc keyboard shortcut for rewind menu; no session branching/forking; no resume-by-ID picker; no session naming at startup (`--name`); no session export; no session statistics; no `--from-pr` resume.

**Effort to close**:
- **Medium** (3–4 weeks):
  1. Enable rewind by default (1 day)
  2. Esc+Esc keyboard shortcut for rewind menu (1–2 days)
  3. Session branching (fork conversation at point) (1 week)
  4. Resume-by-ID picker in TUI (2–3 days)
  5. `--name` flag for session naming at startup (1 day)
  6. Session export to plain text (1 day)
  7. Session statistics (2–3 days)

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, requires subscription).

### Zrb

🔵 **Zrb-only feature**: Full FastAPI-based web UI:
- Browser-based chat interface at `http://localhost:21213`
- Real-time SSE streaming
- Session persistence (SQLite backend)
- Model switching
- YOLO mode toggle
- JWT authentication (guest + admin roles)
- SSL/TLS support
- Task browsing and execution
- REST API for programmatic access (`/api/v1/chat/` endpoints)
- ChatGPT-like interface layout
- Tool approval in browser with edit-args capability
- `HTTPChatApprovalChannel` for web-based tool approvals
- **Jinja2 templates + local mermaid.js** ✅ **NEW in v2.22.4**: Better frontend rendering, no external CDN dependency
- **Configurable shutdown timeout** ✅ **NEW in v2.22.4**: `CFG.WEB_SHUTDOWN_TIMEOUT`

**Status**: 🔵 **Zrb advantage** — local web UI is a Zrb strength not present in Claude Code CLI

---

## 16. Auto Mode (Safety Classifier)

### Claude Code

Separate background classifier model reviews each action before execution:
- Receives user messages and tool calls (not Claude's text — prevents prompt injection)
- Default block list: downloading+executing code, production deploys, mass deletions, IAM changes
- Default allow list: local file ops, dependency installs, read-only HTTP
- Fallback to prompting after 3 consecutive or 20 total blocks
- Configurable via `autoMode.environment`, `autoMode.allow`, `autoMode.soft_deny`
- `disableAutoMode` managed setting to prevent auto mode
- `useAutoModeDuringPlan` — use auto mode semantics in plan mode
- `claude auto-mode defaults` — print classifier rules
- Requires Team/Enterprise/API plan + Sonnet 4.6 or Opus 4.6

### Zrb

No equivalent safety classifier. YOLO mode bypasses all confirmations; non-YOLO requires user approval.

**Status**: ❌ **Not supported**

**Effort to close**:
- **High** (4–6 weeks):
  1. Pre-action classification hook: call a lightweight LLM before executing any tool (1 week)
  2. Default block/allow rules (1 week)
  3. Configurable rules in settings file (1 week)
  4. Fallback-to-prompting counter logic (2 days)
  5. Integration with permission mode system (1 week)

---

## 17. GitHub / CI/CD Integration

### Claude Code

- **GitHub Actions**: `@claude` mention in PR comments/issues triggers workflow
- **GitLab CI/CD**: pipeline integration
- **GitHub Code Review**: automatic review bot on every PR
- **`/install-github-app`**: set up Claude GitHub app
- **`--from-pr`**: resume sessions linked to GitHub PR
- **`/pr-comments`**: fetch and display GitHub PR comments
- **PR status footer**: shows open PR status in session footer
- **`/security-review`**: analyze pending changes for vulnerabilities
- **Slack integration**: mention `@Claude` in Slack to get a PR back
- **`/batch`**: spawns parallel agents in git worktrees, each creates a PR

### Zrb

🔵 **Zrb-only**: Task automation system with Git utilities (`src/zrb/builtin/`):
- `git` group: git-related built-in tasks
- `run_shell_command` tool can run `gh`, `git` commands
- RAG tools for code analysis
- `review` built-in skill: structured code + security review with OWASP Top 10 checklist

No native GitHub app, no CI/CD pipeline integration, no PR comment triggers, no Slack integration, no GitHub Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**:
- **High** (4–8 weeks):
  1. GitHub Actions workflow template calling `zrb llm chat -p` (1–2 days)
  2. GitLab CI template (1 day)
  3. PR status footer via `gh` CLI in TUI (1–2 days)
  4. `/pr-comments` command (2–3 days)
  5. `/security-review` built-in skill (already partly done via `review` skill, 1 day to adapt)
  6. GitHub webhook → Zrb trigger (2–3 weeks)
  7. Slack bot integration (2–3 weeks, separate project)

---

## 18. Sandboxing

### Claude Code

OS-level process sandboxing for Bash tool:
- `sandbox.enabled`: enable sandboxing
- `sandbox.failIfUnavailable`: fail if sandboxing unavailable
- `sandbox.excludedCommands`: commands exempt from sandboxing
- `sandbox.filesystem.allowWrite`, `denyWrite`, `denyRead`: filesystem access control
- `sandbox.network.allowedDomains`, `deniedDomains`, `allowUnixSockets`: network control

### Zrb

No OS-level sandboxing. Permission system only.

**Status**: ❌ **Not supported**

**Effort to close**:
- **High** (3–5 weeks, platform-dependent):
  1. macOS: `sandbox-exec` profiles for child processes (1–2 weeks)
  2. Linux: `seccomp` profiles or `bubblewrap` (1–2 weeks)
  3. Docker-based sandboxing as alternative (1 week)

---

## 19. Remote & Cloud Sessions

### Claude Code

- `--remote` flag: create new web session on claude.ai
- `--teleport`: resume web session in local terminal
- `--remote-control` / `--rc`: start session with Remote Control enabled
- `claude remote-control`: start Remote Control server mode
- Remote control from claude.ai, Claude app
- **Channels**: push events from Telegram, Discord, iMessage, custom webhooks via MCP channel plugins
- **Dispatch**: send tasks from phone → Desktop app opens session
- Cloud sessions shared across devices
- Remote Control session names with prefix setting
- `--channels` flag for channel listeners

### Zrb

🔵 **Zrb-only**: Built-in web server:
- `zrb server start` → local web UI at `http://localhost:21213`
- REST API for external access
- JWT authentication
- SSL/TLS support
- **MultiUI** ✅ **NEW in v2.14.0**: Broadcast to multiple channels (terminal + Telegram + web) simultaneously; first response wins for input routing
- **MultiplexApprovalChannel** ✅ **NEW in v2.14.0**: Route tool approvals to multiple channels

No cloud sessions, no Remote Control protocol, no Channels, no Dispatch, no multi-device sync.

**Status**: 🟡 **Different approach** — Zrb has a local web server and multi-channel support; Claude Code has cloud infrastructure

**Gap**: True cloud sessions require cloud infrastructure. The Remote Control and Channels features (Telegram, Discord, iMessage, webhooks) are partially bridged by Zrb's MultiUI/MultiplexApprovalChannel pattern but there's no drop-in Channels system.

**Effort to close**:
- **Low–Medium** for remote API (existing web server already provides this)
- **Medium** (2–3 weeks) for simple remote control:
  1. WebSocket-based remote control in web UI (1 week)
  2. Telegram/Discord channel plugins (2 weeks, separate projects)
  3. Webhook channel support (1–2 weeks)
- **Very High** for true cloud sessions

---

## 20. Plugins System

### Claude Code

Plugin architecture:
- Install from marketplace or local directory
- `--plugin-dir` for session-only plugins
- Plugin structure: `hooks/hooks.json`, `agents/`, `skills/`, `mcp.json`, `monitors` manifest key
- Plugin scopes for hooks, agents, skills, MCP servers
- `claude plugin` CLI command
- `/plugin` interactive management
- `/reload-plugins` without restart
- **Plugin marketplaces**: source-based marketplaces (e.g., `claude-plugins-official`)
- `blockedMarketplaces` / `strictKnownMarketplaces` managed settings
- `pluginTrustMessage` custom trust warning
- Channel plugins via marketplace

### Zrb

**Skill/Agent system** (closest analog):
- Skills from multiple directories act as mini-plugins
- `CFG.LLM_PLUGIN_DIRS` for user plugin directories
- MCP config from multiple locations
- Agent definitions scanned from `agents/` directories
- Hook factories for dynamic hook registration

No formal plugin packaging/marketplace, no `claude plugin` command, no plugin lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (via skills + MCP + agents, but no plugin packaging/marketplace)

**Effort to close**:
- **Medium** (3–4 weeks):
  1. Define plugin package format (directory with `plugin.yaml` manifest) (3–4 days)
  2. Plugin installer (`zrb plugin add`) (1 week)
  3. Plugin directory scanning (skills, agents, hooks, MCP from plugin dir) (1 week)
  4. `/reload-plugins` command (2 days)

---

## 21. Rate Limiting & Budget Control

### Claude Code

- `--max-budget-usd` flag: per-session spending cap
- `/cost` command: show token usage statistics
- `/usage` command: plan usage limits and rate limit status
- Rate limit status in footer/status area
- Fallback model on overload (`--fallback-model`)
- Token usage per turn

### Zrb

🔵 **Zrb advantage**: Sophisticated rate limiting + transient error retry:
- `LLMLimiter`: requests/minute + tokens/minute limits
- `ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`
- Shared limiter across sub-agents
- Automatic throttling with context window management
- **Transient provider error retry** ✅ **NEW in v2.22.6**: Exponential backoff for HTTP 429/5xx errors; honors `Retry-After` header; caps wait at `LLM_API_MAX_WAIT` (default: 60s); configurable `LLM_API_MAX_RETRIES` (default: 3); set to `1` to disable

Missing: per-session budget cap, `/cost` command, cumulative spend tracking, fallback model on overload.

**Status**: 🟡 **Partially supported** (rate limiting + retry better than Claude Code; budget control missing)

**Effort to close**:
- **Low** (3–5 days):
  1. Track cumulative token usage and estimated cost per session (2 days)
  2. `--max-budget` input on `LLMChatTask` (1 day)
  3. `/cost` command showing token stats (1 day)
  4. Fallback model configuration in CFG (1 day)

---

## 22. Platform Support

### Claude Code

- **macOS**: Intel + Apple Silicon (native install, Homebrew, Desktop app)
- **Linux**: Native install, Docker
- **Windows**: Native (WSL + native), PowerShell install, WinGet, Desktop app
- **iOS/Android**: Claude mobile app (cloud sessions, Dispatch)
- **Browser**: claude.ai/code (web)

### Zrb

- **macOS**: ✅ Full support
- **Linux**: ✅ Full support
- **Windows**: 🟡 Partial (Python/pip install works; PowerShell autocomplete added in v2.20.0 ✅; native clipboard via PowerShell in v2.18.1 ✅; no native installer)
- **Docker**: 🔵 Docker images available
- **Android/Termux**: 🔵 Documented support
- **Browser**: 🔵 Web UI via `zrb server start`

**Status**: 🟡 **Partially supported** for Windows; ✅ excellent for macOS/Linux

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool:
- Post-edit: automatically reports type errors and warnings
- `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`
- Requires installing language-specific plugin

### Zrb

🔵 **Zrb advantage**: More comprehensive LSP integration:
- `LSPManager` singleton with lazy startup and idle timeout (300s)
- Symbol-based API (more LLM-friendly than position-based)
- Full suite: `find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, `rename_symbol` (with dry-run)
- Auto-detect language servers (pyright, gopls, tsserver, rust-analyzer, etc.)
- Project root detection (`.git`, `pyproject.toml`, `go.mod`, etc.)
- All LSP tools auto-approved in `chat.py`

**Status**: ✅ **Fully supported** (Zrb arguably better)

---

## 24. Context Compaction

### Claude Code

- Auto-compaction at ~95% context capacity
- Manual: `/compact [instructions]` with optional focus
- `PreCompact` / `PostCompact` hooks
- Matcher: `manual` vs `auto`
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` env var
- Original transcript preserved in `.jsonl`

### Zrb

Two-layer auto-summarization system:

**Layer 1 — Per-message summarization**:
- Individual tool results exceeding threshold are summarized in-place

**Layer 2 — Conversational history summarization**:
- Triggers when messages > `LLM_HISTORY_SUMMARIZATION_WINDOW` OR total tokens > threshold
- Intelligent split: respects tool call/return pairs
- Chunk-and-summarize with `<state_snapshot>` consolidation
- **Parallel chunk summarization** ✅: all chunks run concurrently via `asyncio.gather`; progress shows `Compressing chunk X/total`
- **Active skills tracked** ✅: `<active_skills>` section in state snapshot; restored on context recovery
- **All summarizer agents use model pipeline** ✅ **NEW in v2.22.0**: `create_conversational_summarizer_agent()` and `create_message_summarizer_agent()` accept `model_getter`/`model_renderer`

**Manual compaction**: `/compress` / `/compact` commands

**Status**: 🟡 **Partially supported**

**Gap**: Core auto-compaction robustly implemented with parallel chunks and skill tracking. Missing: `PreCompact` hook event (removed in v2.18.0 simplification — needs re-adding), `PostCompact` hook event, focus instructions for manual compact (`/compress [instructions]`), original transcript preservation in `.jsonl`.

**Effort to close**:
- **Low** (3–5 days):
  1. Re-add `PreCompact`/`PostCompact` hook events (2 days)
  2. Accept optional focus-instructions argument in `/compress [instructions]` (1–2 days)

---

## 25. Vim Mode & Editor Features

### Claude Code

Full Vim editor mode in TUI:
- NORMAL/INSERT mode switching
- Complete navigation: `h/j/k/l`, `w/e/b/0/$`, `gg/G`, `f/F/t/T`
- Editing: `x`, `dd`, `D`, `dw`, `cc`, `C`, `yy`, `p`, `>>`, `J`, `.`
- Text objects: `iw/aw`, `i"/a"`, `i(/a(`, `i[/a[`, `i{/a{`
- Activate via `/vim` or `/config`
- `editorMode: "vim"` in `~/.claude.json`

### Zrb

No Vim mode. Standard `prompt_toolkit` input only.

**Status**: ❌ **Not supported**

**Effort to close**:
- **Medium** (2–3 weeks): Implement Vim mode as a `prompt_toolkit` key binding layer.

---

## 26. Voice Input

### Claude Code

- Push-to-talk voice dictation
- Requires a Claude.ai account
- `voiceEnabled` setting, `/voice` command to toggle
- `language` setting for dictation language

### Zrb

No voice input.

**Status**: ❌ **Not supported**

**Effort to close**:
- **Medium** (2–3 weeks): Integrate `speech_recognition` or `whisper` library for push-to-talk in TUI.

---

## 27. Diff Viewer

### Claude Code

- `/diff` command: interactive diff viewer for uncommitted changes and per-turn diffs
- Visual diff in IDE extensions (accept/reject hunks)
- Checkpoint-based diff (before/after each turn)

### Zrb

No interactive diff viewer. Changes applied directly; git diff accessible via `run_shell_command`.

**Status**: ❌ **Not supported** (in TUI; available via shell)

**Effort to close**:
- **Low–Medium** (1–2 weeks): Implement `/diff` command using `unified_diff` or `rich` library.

---

## 28. Task / Todo System

### Claude Code

**TaskCreate/Update/Get/List/Stop tools** (for background bash tasks):
- Background tasks with unique IDs
- Auto-cleaned on exit
- `Ctrl+T` to toggle task list UI
- `CLAUDE_CODE_TASK_LIST_ID` env var to share task list across sessions

**TodoWrite** (for non-interactive/SDK mode):
- Session-scoped checklist

### Zrb

🔵 **Zrb advantage**: More comprehensive todo system:
- `TodoManager` with persistent JSON storage (`~/.zrb/todos/{session}.json`)
- States: `pending`, `in_progress`, `completed`, `cancelled`
- Auto-generated IDs, timestamps, progress calculation
- `write_todos`, `get_todos`, `update_todo`, `clear_todos` tools
- Session isolation
- **Pending todos in system context every turn** ✅ **NEW in v2.22.3**: Active (pending/in_progress) todos rendered into system prompt automatically; LLM never starts blind about current task state
- **Session wiring via ContextVar** ✅ **NEW in v2.22.3**: All todo tools automatically resolve session identity without explicit `session=` arguments

🔵 **Zrb-only**: Full task automation framework (separate from LLM todos):
- `CmdTask`, `LLMTask`, task DAG, dependencies, retries, scheduling

**Status**: ✅ **Fully supported** (Zrb advantage on persistent todos with system context integration)

---

## 29. Scheduling

### Claude Code

**`CronCreate`/`CronDelete`/`CronList` tools**: schedule recurring or one-shot prompts within session

**`/schedule` command**: create cloud-scheduled tasks

**`/loop [interval] <prompt>`**: repeating prompt within session (bundled skill)

**Desktop scheduled tasks**: run on local machine via Desktop app

**Cloud scheduled tasks**: run on Anthropic-managed infrastructure, persist even when computer is off; create from web, Desktop app, or `/schedule`

### Zrb

🔵 **Zrb advantage**: Full `Scheduler` task type for cron-based automation (separate from LLM tools). `CmdTask` with cron-like scheduling.

No `CronCreate`/`CronDelete`/`CronList` as LLM-callable tools within a chat session. No cloud-scheduled tasks.

**Status**: 🟡 **Partially supported** (scheduling at task level; not as in-session LLM tools; no cloud scheduling)

**Effort to close**:
- **Low** for in-session scheduling (2–3 days): Wrap Zrb's `Scheduler` as `CronCreate`/`CronDelete`/`CronList` LLM tools.
- **Very High** for cloud scheduling (requires cloud infrastructure).

---

## 30. Worktree Isolation

### Claude Code

Git worktree isolation is a first-class feature:

**CLI**:
- `--worktree` / `-w` flag: run Claude in isolated git worktree
- `--tmux` flag: create tmux session for the worktree
- Auto-cleans if no changes; returns worktree path and branch if changes made

**Agent definitions**:
- `isolation: worktree` in agent frontmatter — each subagent gets its own worktree
- Worktree branch auto-named from agent name + ULID

**Built-in tools**:
- `EnterWorktree` — create and enter a new git worktree
- `ExitWorktree` — exit and optionally clean up the worktree

**Hook events**:
- `WorktreeCreate` — fires when a worktree is created
- `WorktreeRemove` — fires when a worktree is destroyed

**`/batch` command**:
- Spawns multiple agents in parallel worktrees, each creates a PR

**Worktree settings**:
- `worktree.symlinkDirectories` — symlink large dirs to avoid duplication
- `worktree.sparsePaths` — sparse-checkout for faster startup
- `.worktreeinclude` file to copy gitignored files into worktrees

### Zrb

**Worktree tools** ✅:
- `enter_worktree(branch_name)` — creates isolated git worktree (`src/zrb/llm/tool/worktree.py`)
- `exit_worktree(worktree_path, keep_branch)` — removes worktree, optionally deletes branch
- `list_worktrees()` — lists all active worktrees for current repo
- **All worktree tools wrapped in `tool_wrapper`** ✅ **NEW in v2.21.0**: Returns structured `{"error": "..."}` instead of raising exceptions

**Worktree tracking enhancements** ✅ **NEW in v2.22.3**:
- `EnterWorktree` sets an `active_worktree` ContextVar; `ExitWorktree` clears it
- Active worktree path injected into every system context and delegate messages
- LLM reminded to pass `cwd` to `Bash` and use absolute paths for file tools
- `EnterWorktree` auto-adds `.zrb/worktree/` to the repo's `.gitignore` via `_ensure_gitignore()`

**Worktree storage**:
- Worktrees placed inside the repo under `.{ROOT_GROUP_NAME}/worktree/`
- Uses `git rev-parse --show-toplevel` to resolve repo root

**Status**: 🟡 **Partially supported**

**Gap**: Core worktree tools are implemented with repo-local storage and ContextVar tracking. Missing: `--worktree` / `-w` CLI flag (start session in isolated worktree), `--tmux` flag, `isolation: worktree` in agent definitions, `WorktreeCreate`/`WorktreeRemove` hook events, `/batch` command, worktree settings (`symlinkDirectories`, `sparsePaths`), auto-cleanup of empty worktrees on session end, `.worktreeinclude` support.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. `--worktree` CLI flag for `zrb llm chat` (1–2 days)
  2. `isolation: worktree` support in subagent definitions (1 week, after file-based agent defs)
  3. `WorktreeCreate` / `WorktreeRemove` hook events (2 days)
  4. Auto-cleanup of empty worktrees on session end (2 days)
  5. `/batch` command (2–3 weeks, requires worktree + parallel delegation + PR creation)

---

## 31. Side Questions (`/btw`)

### Claude Code

`/btw <question>` — ask a side question that does NOT get added to the conversation history:
- Claude answers the question but the Q&A pair is dropped from the transcript
- Does not interrupt in-progress agent work

### Zrb

✅ **Fully implemented** (`_handle_btw_command` in `base_ui.py`):
- `/btw <question>` detected in command handlers
- Sends question to model in a temporary context (not appended to `_history_manager`)
- Displays answer without writing to session history
- Shares conversation context with main session for relevant answers

**Status**: ✅ **Fully supported**

---

## 32. Channels & Remote Control

### Claude Code

- **Remote Control**: Control an active Claude Code session from claude.ai or the Claude app. Start with `--remote-control` flag or `claude remote-control` command.
- **Channels**: Push external events into a running session via MCP channel plugins. Supports Telegram, Discord, iMessage, custom webhooks. Enable with `--channels` flag and `channelsEnabled` managed setting.
- **`allowedChannelPlugins`** managed setting — restrict which channel plugins are allowed.
- **Dispatch**: Send tasks from your phone → Desktop app opens a session automatically.
- **`CLAUDE_CODE_REMOTE`** env var: set to `"true"` in remote environments (available to hooks).

### Zrb

🔵 **Zrb-only existing**:
- **MultiUI** ✅ **NEW in v2.14.0**: Runs CLI + Telegram + web channels simultaneously; broadcasts output to all; first-response-wins for input
- **MultiplexApprovalChannel** ✅ **NEW in v2.14.0**: Routes tool approvals to multiple channels simultaneously; first response wins
- HTTP Chat API ✅ **NEW in v2.15.0**: REST API for external message injection into sessions

The nearest analog to Channels: any external service can POST to `/api/v1/chat/sessions/{id}/messages` to push messages into an active session.

No Remote Control protocol. No native Channels plugin system. No Dispatch.

**Status**: 🟡 **Partially covered** (Zrb's MultiUI + HTTP API cover the core use cases; lacks standardized protocol)

**Gap**: Zrb's web server + MultiUI provides some remote access, but lacks the standardized Remote Control protocol and Channels plugin system. Gap has narrowed since v2.14.0 but the push-notification / channel plugin ecosystem is absent.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. WebSocket-based remote control for web UI (1 week)
  2. Webhook endpoint for pushing messages into active sessions (already partially done via HTTP API, needs refinement)
  3. Telegram/Discord channel plugins (2 weeks, separate projects)

---

## 33. Summary & Roadmap

### Changes Since v2.20.1

#### Zrb improvements (v2.20.1 → v2.22.6)

| Feature | Old Status | New Status | Details |
|---------|-----------|-----------|---------|
| Tool Guidance System | ❌ 0% | 🔵 Zrb advantage | `ToolGuidance` dataclass, `add_tool_guidance()` API, `# Tool Usage Guide` in system prompt (v2.21.0) |
| Pending Todos in System Context | ❌ | 🔵+ | Active todos rendered every turn; LLM never starts blind (v2.22.3) |
| Active Worktree Tracking | 🟡 | 🟡+ | ContextVar tracking, .gitignore auto-update, injected in system context + delegate messages (v2.22.3) |
| Global Model Pipeline | 🔵 Task-level | 🔵 Enhanced | `LLMConfig.model_getter/renderer` for centralized routing; all sub-agents + summarizers use it (v2.22.0) |
| Transient Error Retry | ❌ | 🔵 Advantage | Exponential backoff, Retry-After header, `LLM_API_MAX_RETRIES`, caps at `LLM_API_MAX_WAIT` (v2.22.6) |
| Fuzzy Editing | ❌ | 🔵 Advantage | Trailing-whitespace + indentation-flexible fallback in `replace_in_file` (v2.22.6) |
| Ripgrep Acceleration | ❌ | 🔵 Advantage | `search_files` uses `rg --files-with-matches` first, Python fallback (v2.22.3) |
| Recent Commits in Context | ❌ | 🔵 Advantage | Last 5 git commits shown in system prompt every turn (v2.22.3) |
| System Context Detection | 🟡 | 🟡+ | Infra types (Terraform, k8s, AWS/GCP/Azure), tool hints (`rg`, `jq`, `gh`), token limit (v2.22.1-2.22.3) |
| Web Frontend | 🔵 | 🔵+ | Jinja2 templates, local mermaid.js, no external CDN (v2.22.4) |
| Companion File Returns | ❌ | ✅ | `ActivateSkill` returns skill directory + companion files (v2.22.1) |
| Bash Default Timeout | 30s | 120s | Actionable `[SYSTEM SUGGESTION]` messages for common failures (v2.22.6) |
| Granular Journal Config | ❌ | ✅ | `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` + `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` independently (v2.22.6) |
| Tool Error Handling | ❌ | ✅ | `tool_wrapper` decorator; structured `{"error": "..."}` returns; no session crash (v2.21.0) |
| Request Limit Override | ❌ | ✅ | `request_limit=None` overrides pydantic-ai's 50-request cap on tool-use loops (v2.22.6) |
| Invalid Tool Retry | ❌ | ✅ | Detects HTTP 400 invalid-tool errors; injects corrective message; one-shot retry (v2.22.5) |
| HTTP Chat API | — | 🔵 | REST API for programmatic session/message management (v2.15.0, already in v2.20.1 but notable) |
| MultiUI / MultiplexApproval | — | 🔵 | Multi-channel broadcast + first-wins approval (v2.14.0, already in v2.20.1 but notable) |

#### New Claude Code features since April 14, 2026 analysis

| Feature | Impact on Gap |
|---------|--------------|
| **`UserPromptExpansion`** hook event | Small gap widened (§5) |
| **`PostToolBatch`** hook event | Small gap widened (§5) |
| **`mcp_tool`** hook handler type (5th type) | Moderate gap widened (§5) |
| **`xhigh`** effort level added | Minor gap (§1) |
| Various new settings | Gap widened (§11) |

### Overall Coverage Assessment

| Category | Status | Change vs v2.20.1 |
|----------|--------|-----------------|
| CLI Flags | 🟡 ~25% coverage | = (CC added more flags) |
| Interactive TUI | 🟡 ~68% | ↑ (active worktree in context) |
| Slash Commands | 🟡 ~42% | = |
| Memory/CLAUDE.md | 🟡 ~70% | ↑ (companion files, granular journal) |
| Hooks | 🟡 ~33% (9/27 events) | ↓ (CC added 3 new events + MCP tool handler) |
| MCP | 🟡 ~55% | = |
| Subagents | 🟡 ~45% | ↑ (model pipeline, agent filtering) |
| Agent Teams | ❌ 0% | = |
| Skills | ✅ ~82% | ↑ (companion files) |
| Permission Modes | 🟡 ~32% | ↑ (selective YOLO, safe command policy) |
| Settings System | 🟡 ~33% | ↑ (tool guidance, global model pipeline, retry config) |
| Built-in Tools | 🟡 ~73% | ↑ (ripgrep, fuzzy edit, tool wrapper, system context) |
| IDE Integrations | ❌ 0% | = |
| Session/Checkpoint | 🟡 ~55% | = |
| Web UI | 🔵 Zrb advantage | ↑↑ (Jinja2, HTTP API, MultiUI) |
| Auto Mode | ❌ 0% | = |
| GitHub/CI Integration | ❌ 0% | = |
| Sandboxing | ❌ 0% | = |
| Remote/Cloud | 🟡 Different approach | ↑ (MultiUI + HTTP API narrow gap) |
| Channels & Remote Control | 🟡 ~25% | ↑ (HTTP API, MultiUI cover basic cases) |
| Plugins | 🟡 ~35% | = |
| Rate Limiting | 🟡 ~75% | ↑↑ (transient error retry with exponential backoff) |
| Platform Support | 🟡 ~82% | = |
| LSP | ✅ Zrb advantage | = |
| Context Compaction | 🟡 ~83% | ↑ (model pipeline in summarizers) |
| Vim Mode | ❌ 0% | = |
| Voice Input | ❌ 0% | = |
| Diff Viewer | ❌ 0% | = |
| Task/Todo | ✅ Zrb advantage | ↑↑ (system context integration, ContextVar session wiring) |
| Scheduling | 🟡 ~40% | = |
| Worktree Isolation | 🟡 ~62% | ↑ (ContextVar tracking, gitignore auto-update) |
| Side Questions (`/btw`) | ✅ 100% | = |

### Zrb Unique Advantages (Superset Features)

1. 🔵 **Local Web UI**: Full browser-based interface with auth, streaming, task management, browser-based tool approvals, Jinja2 templates, local mermaid.js
2. 🔵 **HTTP Chat API**: REST API for programmatic session and message management (`/api/v1/chat/`)
3. 🔵 **MultiUI + MultiplexApprovalChannel**: Broadcast to multiple channels simultaneously (terminal + Telegram + web); first-response-wins for input and approvals
4. 🔵 **Task Automation Framework**: CmdTask, LLMTask, Scaffolder, Scheduler, HttpCheck, TcpCheck — a full DAG-based automation engine
5. 🔵 **Android/Termux support**: Runs on mobile devices
6. 🔵 **Batch file tools**: `read_files`, `write_files` (multi-file in one call)
7. 🔵 **AST-based code analysis**: `analyze_file`, `analyze_code`
8. 🔵 **RAG/embeddings**: `create_rag_from_directory` with ChromaDB for semantic search
9. 🔵 **Run Zrb tasks as LLM tools**: LLM can discover and execute any Zrb task
10. 🔵 **Long-term notes**: `ReadLongTermNote`, `ReadContextualNote`
11. 🔵 **Richer LSP**: `rename_symbol` with dry-run, workspace symbols, better project root detection
12. 🔵 **Persistent todos with system context**: Session-isolated, timestamped, status-tracked; active todos shown in every turn automatically
13. 🔵 **Self-hosted**: no subscription required, bring your own API key
14. 🔵 **Multi-model**: any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, Mistral, HuggingFace, Cohere, etc.)
15. 🔵 **White-labeling**: create custom CLIs via Zrb's framework
16. 🔵 **Flexible web search**: SearXNG with page/safe_search/language params; also supports Brave + SerpAPI backends
17. 🔵 **Planning system**: CreatePlan, ViewPlan, UpdatePlan tools for persistent plan management
18. 🔵 **Global model tiering pipeline**: `llm_config.model_getter`/`model_renderer` for centralized model routing; all sub-agents, summarizers, and tool agents respect the pipeline
19. 🔵 **Bidirectional journal graph**: Notes system with backlinks protocol and `<active_skills>` restoration on context recovery
20. 🔵 **Fully configurable limits**: All timeouts, intervals, retries, and size limits exposed as env vars (no hard-coded magic numbers)
21. 🔵 **Tool Guidance System**: Declarative `ToolGuidance` dataclass; `add_tool_guidance()` / `add_tool_guidance_factory()` API; per-tool hints composited into `# Tool Usage Guide` section of system prompt; suppressed for unregistered tools
22. 🔵 **Transient provider error retry**: Exponential backoff for HTTP 429/5xx; honors `Retry-After` header; configurable `LLM_API_MAX_RETRIES` and `LLM_API_MAX_WAIT`
23. 🔵 **Fuzzy file editing**: Trailing-whitespace-tolerant and indentation-flexible fallback in `replace_in_file`
24. 🔵 **Ripgrep acceleration**: `search_files` uses `rg` when available; graceful Python fallback
25. 🔵 **Rich system context**: Infra type detection (Terraform, k8s, AWS/GCP/Azure), recent git commits, pending todos, active worktree path, token limit — all auto-injected every turn
26. 🔵 **Selective YOLO**: `--yolo "Write,Edit"` or `/yolo Write,Edit` auto-approves only named tools

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. **Re-add hook events** — `PreCompact`, `PostCompact`, and key missing events like `SubagentStart/Stop` (3–4 days); also `UserPromptExpansion`, `PostToolBatch`
2. **Extended CLI flags**: `--permission-mode`, `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--effort` (1 week)
3. **JSON settings files** with scope hierarchy (user/project/local) (1 week)
4. **Named permission modes**: add `plan`, `acceptEdits`, `dontAsk` (1 week)
5. **Shift+Tab mode cycling** (1 day)
6. **`/cost` command** + budget tracking (3–5 days)
7. **Additional built-in slash commands**: `/clear`, `/config`, `/cost`, `/export`, `/permissions`, `/diff` (1 week)
8. **`/compress [focus]`** with optional focus instructions (1–2 days)
9. **MCP prompts as slash commands** (3 days)
10. **`--worktree` CLI flag** (1–2 days)
11. **CLAUDE.local.md support** (1 day)
12. **Enable rewind by default** + Esc+Esc shortcut (2–3 days)
13. **`Monitor` tool** for streaming background process events (2–3 days)

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

14. **Full worktree isolation** — `isolation: worktree` in subagent definitions + `/batch` command (2–3 weeks)
15. **File-based agent definitions** (`.zrb/agents/`) + `@-mention` invocation (2–3 weeks)
16. **`/agents` management UI** (3–4 days)
17. **GitHub CI/CD templates** (1 week)
18. **Plugin packaging format** (1–2 weeks)
19. **Missing built-in tools**: `AskUserQuestion`, `NotebookEdit`, `CronCreate/Delete/List` (2 weeks)
20. **MCP `http`/`ws` transports** + OAuth + resources tools (2–3 weeks)
21. **Permission rules config syntax** (1 week)
22. **`http` hook handler type** + `mcp_tool` handler type (1 week)
23. **Skill enhancements**: `effort`, `paths`, `shell`, `hooks`, `!command` injection (1 week)

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

24. **Auto mode safety classifier** (4–6 weeks)
25. **IDE integrations** (VS Code extension, JetBrains plugin) — separate major projects (3–4 months)
26. **Vim mode** in TUI (2–3 weeks)
27. **Agent Teams** — persistent coordinated agents (2–3 months)
28. **OS-level sandboxing** (3–5 weeks)
29. **Voice input** (2–3 weeks)
30. **Desktop app** (Electron/Tauri wrapper) (4–6 weeks)
31. **Cloud scheduled tasks** (requires cloud infrastructure)
32. **GitHub Code Review bot** (2–3 weeks)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~6–8 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~8–12 months with 2–3 developers

> **Net assessment**: Zrb made strong progress from v2.20.1 → v2.22.6. Major gains: **Tool Guidance System** (declarative per-tool hints composited into system prompt), **transient provider error retry** (exponential backoff + Retry-After header), **global model pipeline** (centralized getter/renderer across all sub-agents and summarizers), **pending todos + recent commits auto-injected into every turn**, **active worktree ContextVar tracking**, **ripgrep acceleration**, and **fuzzy file editing**. The overall feature advantage gap vs Claude Code continues to narrow on the "quality of execution" dimension even while Claude Code expands coverage (added `UserPromptExpansion`, `PostToolBatch`, and `mcp_tool` hooks). Zrb's expanding set of unique advantages (26 items) demonstrates it is becoming a genuine superset in many dimensions — especially multi-model support, local web UI, multi-channel approval, tool guidance, context richness, and error resilience.

---

*Analysis updated: 2026-04-25 | Claude Code docs: docs.anthropic.com/en/docs/claude-code | Zrb version: 2.22.6*
