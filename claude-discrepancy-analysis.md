# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs/en) fetched April 2026. Zrb features sourced from full codebase exploration of `src/zrb/` at v2.18.1.
>
> **Zrb version**: 2.18.1
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

Comprehensive CLI with 60+ flags:
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
- `--effort` — effort level (low/medium/high/max)
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
- `claude agents` — list configured subagents
- `claude auto-mode defaults` — print auto mode rules
- `claude remote-control` — start Remote Control server mode

### Zrb

`zrb llm chat` with inputs:
- `--message` / `-m` — initial message
- `--model` — model selection
- `--session` — conversation session name
- `--yolo` — bypass confirmations
- `--attach` — file attachments
- `--interactive` — toggle interactive mode
- `--help` — help text

**Status**: 🟡 **Partially supported**

**Gap**: Zrb covers the most common use cases but lacks ~55 of Claude Code's CLI flags. Critical missing: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--json-schema`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--tools`, `--disallowedTools`, `--debug`, `--plugin-dir`, `--remote-control`, `--channels`, `--chrome`.

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
- Ctrl+V / Cmd+V — **paste image from clipboard**
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
- **`!` bash prefix** — `! cmd` or `/exec cmd` runs shell and injects output (`base_ui.py:944`)
- **`@` file mention** — `@path/to/file` in message body expands to file reference; autocomplete via `completion.py`
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach` — explicit file attachment command
- `/model` — switch model mid-conversation
- `/yolo` — toggle YOLO mode
- `/save` / `/load` — persist/restore sessions; `/load` displays conversation history
- `/compress` / `/compact` — summarize conversation
- `>` / `/redirect` — save last output to file
- **`/btw`** — side question without saving to history (`_handle_btw_command` in `base_ui.py:1030`) ✅ **NEW in v2.17.0**
- **Image clipboard paste** — Ctrl+V paste support ✅ **NEW in v2.18.0**
- **ChatGPT-like interface** — alternate UI layout
- Session persistence
- Configurable greeting, ASCII art, jargon
- Tool approval dialogs with formatted output
- Streaming responses
- Git branch + dirty status in UI info area

**Status**: 🟡 **Partially supported**

**Gap**: Zrb now has `!`, `@`, `/`, `/btw`, and image paste. Still missing: Vim mode, voice input, permission mode cycling (Shift+Tab), extended thinking toggle, background task management (Ctrl+B), task list toggle (Ctrl+T), checkpoint/rewind menu (Esc+Esc), prompt suggestions from git history, transcript viewer, color themes, configurable status line, session branching (`/branch`/`/fork`), terminal progress bar, custom `@` suggestion scripts.

**Effort to close**:
- **Medium** (3–5 weeks):
  1. Shift+Tab permission mode cycling (1 day)
  2. Background bash tasks / Ctrl+B (1 week)
  3. Prompt suggestions from git history (1 week)
  4. Vim mode (2–3 weeks) — significant `prompt_toolkit` work
  5. Checkpoint/rewind (see §14)
  6. Voice input (2–3 weeks)
  7. Color themes (1–2 days)

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~55+): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/cost`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw`, `/tasks`, `/permissions`, `/security-review`, `/stats`, `/theme`, `/voice`, `/agents`, `/rename`, `/schedule`, `/effort`, `/desktop`, `/fast`, `/statusline`, etc.

**Bundled skills** as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`

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
- `/yolo` — toggle YOLO mode
- `>`, `/redirect` — save last output to file
- `!`, `/exec` — execute shell command and inject output
- `/model <name>` — set model mid-conversation
- `/btw <question>` — side question without history ✅ **NEW in v2.17.0**
- Custom skill commands auto-registered from skill files

**Status**: 🟡 **Partially supported**

**Gap**: Core command infrastructure works. Missing: ~40 built-in management commands (`/clear`, `/config`, `/diff`, `/rewind`, `/branch`, `/export`, `/cost`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/stats`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/effort`, `/rename`, `/desktop`, `/fast`, `/statusline`), MCP prompts as commands, bundled utility skills like `/batch`, `/loop`, `/simplify`.

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
- **`CLAUDE.local.md`** — local (gitignored) personal overrides (**NEW**)
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

**Journal system** (analog to Claude Code's auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`) — persistent notes written by LLM or user
- Injected into LLM context via `PromptManager`
- Read/write/search via journal tools; auto-approved for journal dir

**Disable git mandates** — `includeGitInstructions` equivalent via `ZRB_LLM_DISABLE_GIT_MANDATES` ✅ **NEW in v2.18.0**

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

**24 hook events** across 7 categories:
- Session: `SessionStart`, `SessionEnd`, `InstructionsLoaded`
- User: `UserPromptSubmit`
- Tool: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, **`PermissionDenied`** (new)
- Agent teams: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`
- Claude response: `Stop`, `StopFailure`
- File/env: `CwdChanged`, `FileChanged`, `ConfigChange`
- Compaction: `PreCompact`, `PostCompact`
- MCP: `Elicitation`, `ElicitationResult`
- Worktree: `WorktreeCreate`, `WorktreeRemove`
- Notification: `Notification`

**4 handler types**: `command` (shell), `http` (POST request), `prompt` (Claude eval), `agent` (sub-agent with tools)

**Features**:
- Conditional execution via `if` field (permission rule syntax)
- Async hooks (`"async": true`) — command hooks only
- `statusMessage` for spinner
- `once` per session (skills)
- Decision output: `allow`, `deny`, `ask`, `defer`
- `additionalContext` injection
- `updatedInput` for modifying tool inputs
- `CLAUDE_ENV_FILE` for persisting env vars (SessionStart, CwdChanged, FileChanged only)
- `allowedHttpHookUrls` security allowlist (**NEW**)
- `httpHookAllowedEnvVars` env var allowlist (**NEW**)
- `allowManagedHooksOnly` policy (**NEW**)
- `disableAllHooks` setting
- Config locations: user, project, local, managed policy, plugin, skill/agent frontmatter
- `/hooks` management UI
- `PermissionDenied` event with `retry` field (**NEW**)

### Zrb

**9 hook events** (`src/zrb/llm/hook/types.py`) — simplified in v2.18.0 from previous 14:
- `SessionStart`, `SessionEnd`
- `UserPromptSubmit`
- `PreToolUse`, `PostToolUse`, `PostToolUseFailure`
- `Notification`
- `Stop`
- `PreCompact`

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent)

**Features**:
- Operator-based matchers: `equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `regex`, `glob`
- Async/sync execution with timeouts
- Skill frontmatter hook definitions
- `HookManager` singleton with YAML/JSON config
- Config from: `HOOKS_DIRS`, `HOOKS_TIMEOUT`
- Claude Code string compatibility mapping

**Status**: 🟡 **Partially supported**

**Gap**: Zrb now has **9** of Claude Code's 24 events (was 14 of 27 — the hook system was simplified in v2.18.0, reducing coverage). Missing events: `InstructionsLoaded`, `StopFailure`, `CwdChanged`, `FileChanged`, `ConfigChange`, `PostCompact`, `Elicitation`, `ElicitationResult`, `WorktreeCreate`, `WorktreeRemove`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `PermissionRequest`, `PermissionDenied`. Missing handler type: `http`. Missing features: `additionalContext` injection, `updatedInput` modification, `CLAUDE_ENV_FILE` persistence, `once` flag, `statusMessage`, `/hooks` management UI, conditional `if` field, `allowedHttpHookUrls`, `allowManagedHooksOnly`.

**Effort to close**:
- **Medium-High** (4–5 weeks):
  1. Add missing event types back to `HookEvent` enum (1–2 days)
  2. Fire missing events at appropriate lifecycle points (1 week)
  3. Add `http` handler type (2–3 days)
  4. Add `additionalContext` and `updatedInput` to hook output protocol (2–3 days)
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

### Zrb

- Transports: `stdio`, `sse`
- Config: `mcp-config.json` searched from home → project hierarchy → CWD
- Environment variable expansion in config
- Integrated via `load_mcp_config()` in `LLMChatTask`
- Uses Pydantic AI's `MCPServerStdio` / `MCPServerSSE`

**Status**: 🟡 **Partially supported**

**Gap**: Core MCP functionality works (`stdio`, `sse`). Missing: `http` and `ws` transports, CLI command for easy server addition (`zrb mcp add`), OAuth authentication, MCP prompts as slash commands, MCP tool search/deferred loading, MCP resources tools, subagent-scoped MCP, `/mcp` interactive management UI, managed-only policy, granular enable/disable per server.

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
- Frontmatter fields: `name`, `description`, `prompt`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `initialPrompt`, **`color`** (new), **persistent memory directory** (new)
- Invocation: natural language, `@-mention` (guaranteed), `--agent` flag, `agent` setting, `/agents` command
- Foreground vs background: Ctrl+B to background
- Subagent context compaction (auto at ~95%)
- Tool access control: `tools` allowlist, `disallowedTools` denylist
- Subagent isolation: `isolation: worktree`
- Subagent memory: `memory: user/project/local` → persistent memory directory at `~/.claude/agent-memory/`
- Auto-delegation based on description matching
- `/agents` interactive management UI (**NEW**)
- `claude agents` CLI command (**NEW**)
- Managed subagents (organization-wide deployment)

**Built-in subagents**: Explore, Plan, general-purpose, Bash, statusline-setup, Claude Code Guide

### Zrb

Delegate tool system:
- `create_delegate_to_agent_tool()` — sequential sub-agent call
- `create_parallel_delegate_tool()` — concurrent multi-agent
- `SubAgentManager` with tool registry, lazy-loading from filesystem
- Tool/toolset factories for dynamic resolution at execution time
- `BufferedUI` for output synchronization
- Agent discovery from YAML configs
- Shared rate limiter across agents
- Foreground/background via async execution

**Built-in agents** (in `src/zrb/llm_plugin/agents/`):
- `generalist`, `researcher`, `code-reviewer`

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has working multi-agent delegation but implemented as tools (programmatic), not as declarative YAML/Markdown files that Claude auto-discovers. Missing: file-based agent definitions (`.zrb/agents/` / `.claude/agents/`), natural language / `@-mention` invocation, subagent-specific `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `initialPrompt`, `color`, persistent agent memory directory, `/agents` management UI, `claude agents` CLI command, managed subagents.

**Effort to close**:
- **High** (6–8 weeks):
  1. File-based agent definition loader (`.zrb/agents/*.md`, `.claude/agents/*.md`) (1 week)
  2. YAML frontmatter parsing for all fields (3–4 days)
  3. `@-mention` in TUI input with agent typeahead (3–4 days)
  4. Natural language delegation (3–4 days)
  5. Per-agent permission mode, maxTurns, memory (1 week)
  6. Subagent-scoped MCP (1 week)
  7. Worktree isolation per agent (1–2 weeks)
  8. `/agents` management UI (3–4 days)
  9. `claude agents` CLI command (1 day)

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
- Skills from `--add-dir` directories are loaded (exception to general rule)
- `disableSkillShellExecution` managed policy setting
- Bundled skills: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`
- Follows [Agent Skills](https://agentskills.io) open standard

### Zrb

Comprehensive skill system (`src/zrb/llm/skill/`):
- File types: `.skill.md`, `.skill.py`
- Scopes: default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`) — hierarchy root→CWD
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`
- Auto-scan on first access, manual reload
- Lazy file reading with content caching
- Factory function support for dynamic skills
- `get_skill_custom_command()` maps skills to slash commands
- `create_activate_skill_tool()` for Claude to invoke skills

Built-in skills in `src/zrb/llm_plugin/skills/`:
- `core-coding`, `core-journaling`, `research-and-plan`, `testing`, `debug`, `review`, `refactor`, `skill-creator`, `git-summary`, `init`

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` frontmatter field, `hooks` in skill frontmatter, `paths:` glob activation patterns, `shell` field, `` !`command` `` dynamic context injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitution variables, supporting files directory pattern, bundled utility skills (`/batch`, `/loop`, `/simplify`, `/claude-api`).

**Effort to close**:
- **Low** (1–2 weeks):
  1. Add `effort`, `hooks`, `paths`, `shell` frontmatter fields (2–3 days)
  2. `` !`command` `` preprocessing at load time (1–2 days)
  3. `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR` substitutions (1 day)
  4. Supporting files directory loading (1–2 days)
  5. Add `/loop` and `/simplify` bundled skills (2–3 days each)

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

**Mode switching**: Shift+Tab cycling during session; `--permission-mode` flag at startup; `defaultMode` setting; `--enable-auto-mode` to unlock auto mode; `--allow-dangerously-skip-permissions` to add bypassPermissions to cycle.

**Permission rules**: `Tool`, `Tool(specifier)`, glob patterns, domain restricts, MCP tool patterns
- Evaluation: deny > ask > allow (first match wins)
- Config levels: managed > CLI > local > project > user
- `allow`, `ask`, `deny`, `additionalDirectories` in settings

**PermissionRequest hook**: intercept permission dialogs
**PermissionDenied hook**: retry on auto-mode denial

### Zrb

**Tool approval system**:
- YOLO mode (`--yolo`) = `bypassPermissions`
- **More flexible YOLO** ✅ **NEW in v2.18.0** — granular YOLO control
- `auto_approve()` function with condition callbacks
- `approve_if_path_inside_cwd`, `approve_if_path_inside_journal_dir` conditions
- Per-tool validation policies: `replace_in_file_validation_policy`, `read_file_validation_policy`
- Tool call confirmation dialogs in TUI
- `ApprovalChannel` class for async approval
- Multiplex approval channels (terminal + Telegram simultaneously)

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has YOLO mode and per-tool approval policies. Missing: named permission modes beyond YOLO/non-YOLO, `acceptEdits` mode, `plan` mode (read-only planning), `dontAsk` mode, `auto` mode with safety classifier, Shift+Tab cycling, permission rules configuration syntax (glob patterns, domain restricts, `Bash(npm run *)` style), `PermissionRequest` / `PermissionDenied` hooks, rule evaluation precedence, admin-managed permission policies.

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

**Key settings** (selected new ones added since last analysis):
- `outputStyle` — configure output style to adjust system prompt (**NEW**)
- `attribution` — customize git commit/PR attribution (**NEW**)
- `fileSuggestion` — custom `@` autocomplete script (**NEW**)
- `plansDirectory` — custom plans storage path (**NEW**)
- `effortLevel` — persist effort level (**NEW**)
- `fastModePerSessionOptIn` — require per-session fast mode opt-in (**NEW**)
- `showThinkingSummaries` — show extended thinking summaries (**NEW**)
- `alwaysThinkingEnabled` — extended thinking by default (**NEW**)
- `disableDeepLinkRegistration` — disable `claude-cli://` protocol (**NEW**)
- `terminalProgressBarEnabled` — terminal progress bar (**NEW**)
- `availableModels` — restrict model selection (**NEW**)
- `spinnerTipsOverride` / `spinnerVerbs` — customize spinner (**NEW**)
- `worktree.symlinkDirectories` / `worktree.sparsePaths` — worktree optimization (**NEW**)
- `autoUpdatesChannel` — update channel (stable/latest) (**NEW**)
- `otelHeadersHelper` — dynamic OTEL headers script (**NEW**)
- `companyAnnouncements` — startup announcements (**NEW**)
- `prefersReducedMotion` — accessibility setting (**NEW**)
- `respectGitignore` — `@` file picker respects `.gitignore` (**NEW**)
- `language` — Claude's preferred response language (**NEW**)
- `allowedChannelPlugins` — channel plugin allowlist (managed) (**NEW**)
- `channelsEnabled` — enable channels feature (managed) (**NEW**)
- `forceLoginMethod` / `forceLoginOrgUUID` — org login enforcement (managed) (**NEW**)
- `forceRemoteSettingsRefresh` — fail-closed remote settings (managed) (**NEW**)
- `blockedMarketplaces` / `strictKnownMarketplaces` — plugin marketplace control (managed) (**NEW**)
- Classic settings: `permissions.*`, `model`, `agent`, `additionalDirectories`, `autoMemoryEnabled`, `mcpServers`, `hooks`, `env`, `sandbox.*`, `autoMode.*`, `cleanupPeriodDays`, `defaultShell`, `teammateMode`

**`/config` command**: interactive tabbed settings UI

**Global config** in `~/.claude.json`: `editorMode` (vim/normal), `autoConnectIde`, `showTurnDuration`, `terminalProgressBarEnabled`, `teammateMode`

**Server-managed settings** (**NEW**): remote delivery via Claude.ai admin console; MDM/OS-level policies (macOS plist, Windows registry); file-based `managed-settings.json` with drop-in `managed-settings.d/` directory.

### Zrb

**Single config source**: `CFG` singleton loaded from environment variables (prefix: `ZRB_`)

Categories: `ZRB_LLM_MODEL`, `ZRB_LLM_API_KEY`, `ZRB_WEB_HTTP_PORT`, `ZRB_LLM_MAX_TOKENS`, rate limits, directories, UI, search, hooks, MCP, RAG, `ZRB_LLM_DISABLE_GIT_MANDATES` (new in v2.18.0)

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
| `Edit` | ✅ `replace_in_file` |
| `Bash` | ✅ `run_shell_command` |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` |
| `Agent` (spawn subagent) | 🟡 `create_delegate_to_agent_tool` (programmatic, not declarative) |
| `WebFetch` | ✅ `open_web_page` |
| `WebSearch` | ✅ `search_internet` (SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | 🟡 Exists as hook/approval but not standalone LLM tool |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full LSP tool suite |
| `TaskCreate/Get/List/Update/Stop` | ✅ `write_todos`, `get_todos`, `update_todo`, `clear_todos` |
| `CronCreate/Delete/List` | ❌ Not implemented as LLM tools |
| `EnterPlanMode` / `ExitPlanMode` | 🟡 `CreatePlan`, `ViewPlan`, `UpdatePlan` exist but no plan mode enforcement (**NEW** in Zrb) |
| `EnterWorktree` / `ExitWorktree` | ✅ Fully implemented (`enter_worktree`, `exit_worktree`, `list_worktrees`) ✅ **NEW in v2.17.0** |
| `SendMessage` (agent teams) | ❌ Agent teams not implemented |
| `TeamCreate` / `TeamDelete` | ❌ Agent teams not implemented |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` | ❌ Not implemented |
| `ReadMcpResourceTool` | ❌ Not implemented |
| `PowerShell` | ❌ Not implemented (Windows-only) |
| `Skill` (invoke skills) | ✅ `create_activate_skill_tool()` |
| `RemoteTrigger` | ❌ Not implemented |

**Additional Zrb tools not in Claude Code** 🔵:
- `read_files` (batch read multiple files)
- `write_files` (batch write multiple files)
- `analyze_file` (AST-based code analysis)
- `analyze_code` (code structure analysis)
- `create_rag_from_directory` (RAG embeddings with ChromaDB)
- `create_list_zrb_task_tool` (list Zrb tasks)
- `create_run_zrb_task_tool` (run Zrb tasks as tools)
- `create_activate_skill_tool` (invoke skills)
- `create_parallel_delegate_tool` (parallel multi-agent)
- Long-term note tools (`ReadLongTermNote`, `ReadContextualNote`)
- `CreatePlan`, `ViewPlan`, `UpdatePlan` (planning system)

**Status**: 🟡 **Partially supported**

**Gap**: Core file/shell/web/worktree tools are well-covered. Missing: `AskUserQuestion` as standalone tool, `NotebookEdit`, `CronCreate/Delete/List`, `SendMessage`, `TeamCreate`/`TeamDelete`, `ToolSearch`, MCP resource tools, `RemoteTrigger`, `PowerShell`.

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
- Session persistence
- Model switching
- YOLO mode toggle
- Authentication (JWT)
- SSE streaming
- ChatGPT-like interface layout (v2.17.0)
- Tool approval in browser (edit tool call args on-the-fly)

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
- `/load <name>` displays loaded conversation history
- Fuzzy search for session discovery

**No checkpointing, no rewind, no session branching, no resume-by-ID picker.**

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has session persistence and named sessions with timestamped backups. Missing: checkpointing (snapshot before each edit), rewind/restore, session branching/forking, resume-by-ID picker, session naming at startup (`--name`), session export, session statistics.

**Effort to close**:
- **High** (5–8 weeks):
  1. Checkpoint snapshots: store file state before each write/edit tool call (1–2 weeks)
  2. Rewind menu in TUI: Esc+Esc handler, show checkpoint list (1 week)
  3. Code-only / conversation-only restore (3–4 days each)
  4. Session branching (fork conversation at point) (1 week)
  5. Resume-by-ID picker in TUI (2–3 days)
  6. `--name` flag for session naming at startup (1 day)
  7. Session export to plain text (1 day)
  8. Session statistics (2–3 days)

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, requires subscription).

### Zrb

🔵 **Zrb-only feature**: Full FastAPI-based web UI:
- Browser-based chat interface at `http://localhost:21213`
- Real-time SSE streaming
- Session persistence
- Model switching
- YOLO mode toggle
- JWT authentication (guest + admin roles)
- SSL/TLS support
- Task browsing and execution
- REST API for programmatic access
- ChatGPT-like interface layout (v2.17.0)
- Tool approval in browser with edit-args capability
- `HTTPChatApprovalChannel` for web-based tool approvals

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
- **GitHub Code Review**: automatic review bot on every PR (**NEW**)
- **`/install-github-app`**: set up Claude GitHub app
- **`--from-pr`**: resume sessions linked to GitHub PR
- **`/pr-comments`**: fetch and display GitHub PR comments
- **PR status footer**: shows open PR status in session footer
- **`/security-review`**: analyze pending changes for vulnerabilities
- **Slack integration** (**NEW**): mention `@Claude` in Slack to get a PR back
- **`/batch`**: spawns parallel agents in git worktrees, each creates a PR

### Zrb

🔵 **Zrb-only**: Task automation system with Git utilities (`src/zrb/builtin/`):
- `git` group: git-related built-in tasks
- `run_shell_command` tool can run `gh`, `git` commands
- RAG tools for code analysis

No native GitHub app, no CI/CD pipeline integration, no PR comment triggers, no Slack integration, no GitHub Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**:
- **High** (4–8 weeks):
  1. GitHub Actions workflow template calling `zrb llm chat -p` (1–2 days)
  2. GitLab CI template (1 day)
  3. PR status footer via `gh` CLI in TUI (1–2 days)
  4. `/pr-comments` command (2–3 days)
  5. `/security-review` built-in skill (1–2 days)
  6. GitHub webhook → Zrb trigger (2–3 weeks)
  7. Slack bot integration (2–3 weeks, separate project)

---

## 18. Sandboxing

### Claude Code

OS-level process sandboxing for Bash tool:
- `sandbox.enabled`: enable sandboxing
- `sandbox.filesystem.allowRead`: allowed read paths
- `sandbox.filesystem.denyRead`: denied read paths
- `sandbox.network.allowedDomains`: allowed network domains

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
- `--remote-control` / `--rc`: start session with Remote Control enabled (**NEW**)
- `claude remote-control`: start Remote Control server mode (no interactive session) (**NEW**)
- Remote control from claude.ai, Claude app (**NEW**)
- **Channels** (**NEW**): push events from Telegram, Discord, iMessage, custom webhooks via MCP channel plugins
- **Dispatch** (**NEW**): send tasks from phone → Desktop app opens session
- Cloud sessions shared across devices
- Remote Control session names with prefix setting (**NEW**)
- `--channels` flag for channel listeners (**NEW**)

### Zrb

🔵 **Zrb-only**: Built-in web server:
- `zrb server start` → local web UI
- REST API for external access
- JWT authentication
- SSL/TLS support

No cloud sessions, no Remote Control protocol, no Channels, no Dispatch, no multi-device sync.

**Status**: 🟡 **Different approach** — Zrb has a local web server; Claude Code has cloud infrastructure

**Gap**: True cloud sessions require cloud infrastructure. The Remote Control and Channels features (Telegram, Discord, iMessage, webhooks) are entirely absent — and this gap has widened with Claude Code's new Channels system.

**Effort to close**:
- **Low–Medium** for remote API (existing web server already provides this)
- **Medium** (2–3 weeks) for simple remote control:
  1. WebSocket-based remote control in web UI (1 week)
  2. Telegram/Discord bot integration (2 weeks, separate projects)
  3. Webhook channel support (1–2 weeks)
- **Very High** for true cloud sessions

---

## 20. Plugins System

### Claude Code

Plugin architecture:
- Install from marketplace or local directory
- `--plugin-dir` for session-only plugins (**NEW**)
- Plugin structure: `hooks/hooks.json`, `agents/`, `skills/`, `mcp.json`
- Plugin scopes for hooks, agents, skills, MCP servers
- `claude plugin` CLI command
- `/plugin` interactive management
- `/reload-plugins` without restart
- **Plugin marketplaces** (**NEW**): source-based marketplaces (e.g., `claude-plugins-official`)
- `blockedMarketplaces` / `strictKnownMarketplaces` managed settings (**NEW**)
- `pluginTrustMessage` custom trust warning (**NEW**)
- Channel plugins via marketplace (**NEW**)

### Zrb

**Skill system** (closest analog):
- Skills from multiple directories act as mini-plugins
- `CFG.LLM_PLUGIN_DIRS` for user plugin directories
- MCP config from multiple locations

No formal plugin packaging/marketplace, no `claude plugin` command, no plugin lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (via skills + MCP, but no plugin packaging/marketplace)

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

🔵 **Zrb advantage**: More sophisticated rate limiting:
- `LLMLimiter`: requests/minute + tokens/minute limits
- `ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`
- Shared limiter across sub-agents
- Automatic throttling with context window management

Missing: per-session budget cap, `/cost` command, cumulative spend tracking, fallback model on overload.

**Status**: 🟡 **Partially supported** (rate limiting better than Claude Code; budget control missing)

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
- **Windows**: 🟡 Partial (Python/pip install works; no native installer)
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

Zrb has a **two-layer** auto-summarization system:

**Layer 1 — Per-message summarization**:
- Individual tool results exceeding threshold are summarized in-place

**Layer 2 — Conversational history summarization**:
- Triggers when messages > `LLM_HISTORY_SUMMARIZATION_WINDOW` OR total tokens > threshold
- Intelligent split: respects tool call/return pairs
- Chunk-and-summarize with `<state_snapshot>` consolidation

**Manual compaction**: `/compress` / `/compact` commands

**Status**: 🟡 **Partially supported**

**Gap**: Core auto-compaction robustly implemented. Missing: `PreCompact` hook event (was removed in v2.18.0 simplification — needs to be re-added), `PostCompact` hook event, focus instructions for manual compact, original transcript preservation in `.jsonl`.

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

🔵 **Zrb-only**: Full task automation framework (separate from LLM todos):
- `CmdTask`, `LLMTask`, task DAG, dependencies, retries, scheduling

**Status**: ✅ **Fully supported** (Zrb advantage on persistent todos)

---

## 29. Scheduling

### Claude Code

**`CronCreate`/`CronDelete`/`CronList` tools**: schedule recurring or one-shot prompts within session

**`/schedule` command**: create cloud-scheduled tasks

**`/loop [interval] <prompt>`**: repeating prompt within session (bundled skill)

**Desktop scheduled tasks** (**NEW**): run on local machine via Desktop app

**Cloud scheduled tasks** (**NEW**): run on Anthropic-managed infrastructure, persist even when computer is off; create from web, Desktop app, or `/schedule`

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
- `--worktree` / `-w` flag: run Claude in isolated git worktree at `<repo>/.claude/worktrees/<name>`
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

**Worktree tools** ✅ **NEW in v2.17.0**:
- `enter_worktree(branch_name)` — creates isolated git worktree in temp dir (`src/zrb/llm/tool/worktree.py`)
- `exit_worktree(worktree_path, keep_branch)` — removes worktree, optionally deletes branch
- `list_worktrees()` — lists all active worktrees for current repo

**Status**: 🟡 **Partially supported** (was ❌ in previous analysis — **significant progress**)

**Gap**: Core worktree tools are now implemented. Missing: `--worktree` / `-w` CLI flag (start session in isolated worktree), `--tmux` flag, `isolation: worktree` in agent definitions, `WorktreeCreate`/`WorktreeRemove` hook events, `/batch` command, worktree settings (`symlinkDirectories`, `sparsePaths`), auto-cleanup of empty worktrees on session end, `.worktreeinclude` support.

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

✅ **Fully implemented in v2.17.0** (`_handle_btw_command` in `base_ui.py:1030`):
- `/btw <question>` detected in command handlers
- Sends question to model in a temporary context (not appended to `_history_manager`)
- Displays answer without writing to session history
- Shares conversation context with main session for relevant answers

**Status**: ✅ **Fully supported** (was ❌ in previous analysis — **closed**)

---

## 32. Channels & Remote Control

### Claude Code (**NEW section**)

- **Remote Control**: Control an active Claude Code session from claude.ai or the Claude app. Start with `--remote-control` flag or `claude remote-control` command.
- **Channels**: Push external events into a running session via MCP channel plugins. Supports Telegram, Discord, iMessage, custom webhooks. Enable with `--channels` flag and `channelsEnabled` managed setting.
- **`allowedChannelPlugins`** managed setting — restrict which channel plugins are allowed.
- **Dispatch**: Send tasks from your phone → Desktop app opens a session automatically.
- **`CLAUDE_CODE_REMOTE`** env var: set to `"true"` in remote environments (available to hooks).

### Zrb

🔵 **Zrb-only existing**: Multiplex approval channels allow routing tool approvals to multiple UIs simultaneously (terminal + Telegram + web). This is the nearest analog.

No Remote Control protocol. No Channels. No Dispatch.

**Status**: ❌ **Not supported** (Remote Control and Channels are entirely absent)

**Gap**: This is a new category since the previous analysis. Zrb's web server provides some remote access capability but lacks the bidirectional control and push notification channel system Claude Code now has.

**Effort to close**:
- **Medium** (3–4 weeks):
  1. WebSocket-based remote control for web UI (1 week)
  2. Webhook endpoint for pushing messages into active sessions (1 week)
  3. Telegram/Discord channel plugins (2 weeks, separate projects)

---

## 33. Summary & Roadmap

### Changes Since v2.16.0

#### Zrb improvements (v2.16.0 → v2.18.1)
| Feature | Old Status | New Status | Details |
|---------|-----------|-----------|---------|
| Worktree tools | ❌ 0% | 🟡 ~50% | `enter_worktree`, `exit_worktree`, `list_worktrees` implemented (v2.17.0) |
| `/btw` side questions | ❌ 0% | ✅ 100% | Fully implemented (v2.17.0) |
| Image clipboard paste | ❌ 0% | ✅ | Ctrl+V image paste (v2.18.0) |
| YOLO flexibility | 🟡 | 🟡+ | More flexible YOLO mode (v2.18.0) |
| Git mandate control | ❌ | ✅ | Disable git mandates option (v2.18.0) |
| Plan tools | ❌ | 🟡 | CreatePlan, ViewPlan, UpdatePlan exist (v2.17.0) |
| Hook events | 14 events | 9 events | Hook system simplified — some regression |

#### New Claude Code features since April 2025
| Feature | Impact on Gap |
|---------|--------------|
| Channels (Telegram, Discord, iMessage, webhooks) | New gap opened (§32) |
| Remote Control (claude.ai/app control) | New gap opened (§32) |
| Desktop app scheduled tasks | Gap widened (§29) |
| Cloud scheduled tasks | Gap widened (§29) |
| GitHub Code Review automation | Gap widened (§17) |
| Slack integration | Gap widened (§17) |
| Chrome browser integration | New gap (minor) |
| Plugin marketplaces | Gap widened (§20) |
| 30+ new settings | Gap widened (§11) |
| 20+ new CLI flags | Gap widened (§1) |
| `CLAUDE.local.md` | Small gap (§4) |
| Server-managed settings (MDM/OS) | Gap widened (§11) |
| `PermissionDenied` hook event | Small gap (§5) |
| Subagent color + persistent memory | Small gap (§7) |
| `/agents` management UI | Gap widened (§7) |
| Output styles | Gap widened (§11) |

### Overall Coverage Assessment

| Category | Status | Change vs 2.16.0 |
|----------|--------|-----------------|
| CLI Flags | 🟡 ~25% coverage | ↓ (more new flags added to CC) |
| Interactive TUI | 🟡 ~65% | ↑ (btw + image paste) |
| Slash Commands | 🟡 ~40% | = |
| Memory/CLAUDE.md | 🟡 ~70% | ↓ (CLAUDE.local.md, @import still missing) |
| Hooks | 🟡 ~35% (9/24 events) | ↓ (CC added more; Zrb simplified from 14→9) |
| MCP | 🟡 ~55% | ↓ (new OAuth, managed, resources features) |
| Subagents | 🟡 ~45% | ↓ (CC added /agents UI, color, memory dir) |
| Agent Teams | ❌ 0% | = |
| Skills | ✅ ~80% | = |
| Permission Modes | 🟡 ~30% | = |
| Settings System | 🟡 ~20% | ↓ (30+ new settings in CC) |
| Built-in Tools | 🟡 ~75% | ↑ (worktree tools added) |
| IDE Integrations | ❌ 0% | = |
| Session/Checkpoint | 🟡 ~40% | = |
| Web UI | 🔵 Zrb advantage | ↑ (ChatGPT UI, browser approvals) |
| Auto Mode | ❌ 0% | = |
| GitHub/CI Integration | ❌ 0% | ↓ (CC added Code Review + Slack) |
| Sandboxing | ❌ 0% | = |
| Remote/Cloud | 🟡 Different approach | ↓ (Channels opened new gap) |
| Channels & Remote Control | ❌ 0% | ↓ **New category** |
| Plugins | 🟡 ~35% | ↓ (CC added marketplace) |
| Rate Limiting | 🟡 ~70% | = |
| Platform Support | 🟡 ~80% | = |
| LSP | ✅ Zrb advantage | = |
| Context Compaction | 🟡 ~80% | ↓ (PreCompact event removed in Zrb v2.18.0) |
| Vim Mode | ❌ 0% | = |
| Voice Input | ❌ 0% | = |
| Diff Viewer | ❌ 0% | = |
| Task/Todo | ✅ Zrb advantage | = |
| Scheduling | 🟡 ~40% | ↓ (CC added cloud + desktop scheduling) |
| Worktree Isolation | 🟡 ~50% | ↑↑ **Major progress**: tools implemented |
| Side Questions (`/btw`) | ✅ 100% | ↑↑ **Fully closed** |

### Zrb Unique Advantages (Superset Features)

1. 🔵 **Local Web UI**: Full browser-based interface with auth, streaming, task management, browser-based tool approvals
2. 🔵 **Task Automation Framework**: CmdTask, LLMTask, Scaffolder, Scheduler, HttpCheck, TcpCheck — a full DAG-based automation engine
3. 🔵 **Android/Termux support**: Runs on mobile devices
4. 🔵 **Batch file tools**: `read_files`, `write_files` (multi-file in one call)
5. 🔵 **AST-based code analysis**: `analyze_file`, `analyze_code`
6. 🔵 **RAG/embeddings**: `create_rag_from_directory` with ChromaDB for semantic search
7. 🔵 **Run Zrb tasks as LLM tools**: LLM can discover and execute any Zrb task
8. 🔵 **Long-term notes**: `ReadLongTermNote`, `ReadContextualNote`
9. 🔵 **Richer LSP**: `rename_symbol` with dry-run, workspace symbols, better project root detection
10. 🔵 **Persistent todos**: session-isolated, timestamped, status-tracked todo lists
11. 🔵 **Self-hosted**: no subscription required, bring your own API key
12. 🔵 **Multi-model**: any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, Mistral, HuggingFace, Cohere, etc.)
13. 🔵 **White-labeling**: create custom CLIs via Zrb's framework
14. 🔵 **Flexible web search**: SearXNG with page/safe_search/language params; also supports Brave + SerpAPI backends
15. 🔵 **Multiplex approval channels**: route tool approvals to terminal + Telegram + web simultaneously
16. 🔵 **Planning system**: CreatePlan, ViewPlan, UpdatePlan tools for persistent plan management
17. 🔵 **Conversation name in output**: prints conversation name on exit for easy resumption

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. **Re-add hook events** — PRE_COMPACT, POST_COMPACT, SUBAGENT_START/STOP, TASK_CREATED/COMPLETED were lost in v2.18.0 simplification (3–4 days)
2. **Extended CLI flags**: `--permission-mode`, `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--effort` (1 week)
3. **JSON settings files** with scope hierarchy (user/project/local) (1 week)
4. **Named permission modes**: add `plan`, `acceptEdits`, `dontAsk` (1 week)
5. **Shift+Tab mode cycling** (1 day)
6. **`/cost` command** + budget tracking (3–5 days)
7. **Additional built-in slash commands**: `/clear`, `/config`, `/cost`, `/export`, `/permissions`, `/diff` (1 week)
8. **`PreCompact`/`PostCompact` hooks + `/compress [focus]`** (3–5 days)
9. **MCP prompts as slash commands** (3 days)
10. **`--worktree` CLI flag** (1–2 days)
11. **CLAUDE.local.md support** (1 day)

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

12. **Checkpoint system** + `/rewind` (2–3 weeks)
13. **Full worktree isolation** — `isolation: worktree` in subagent definitions + `/batch` command (2–3 weeks)
14. **File-based agent definitions** (`.zrb/agents/`) + `@-mention` invocation (2–3 weeks)
15. **`/agents` management UI** (3–4 days)
16. **GitHub CI/CD templates** (1 week)
17. **Plugin packaging format** (1–2 weeks)
18. **Missing built-in tools**: `AskUserQuestion`, `NotebookEdit`, `CronCreate/Delete/List` (2 weeks)
19. **MCP `http`/`ws` transports** + OAuth + resources tools (2–3 weeks)
20. **Permission rules config syntax** (1 week)
21. **Channels/webhook support** — push events into active sessions (2–3 weeks)
22. **Skill enhancements**: `effort`, `paths`, `shell`, `hooks`, `!command` injection, supporting files (1 week)

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

23. **Auto mode safety classifier** (4–6 weeks)
24. **IDE integrations** (VS Code extension, JetBrains plugin) — separate major projects (3–4 months)
25. **Vim mode** in TUI (2–3 weeks)
26. **Agent Teams** — persistent coordinated agents (2–3 months)
27. **OS-level sandboxing** (3–5 weeks)
28. **Voice input** (2–3 weeks)
29. **Desktop app** (Electron/Tauri wrapper) (4–6 weeks)
30. **Cloud scheduled tasks** (requires cloud infrastructure)
31. **GitHub Code Review bot** (2–3 weeks)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~6–8 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~8–12 months with 2–3 developers

> **Net assessment**: Zrb made genuine progress in v2.16.0–v2.18.1 (`/btw` fully closed, worktree tools added, image paste added). However, Claude Code also shipped a large amount of new functionality (Channels, Remote Control, cloud scheduling, GitHub Code Review, 20+ new CLI flags, 30+ new settings, plugin marketplace, agent memory directories), meaning the overall gap has **slightly widened** despite Zrb's improvements. The most impactful near-term closes are: re-adding the hook events simplified away in v2.18.0, adding JSON settings files, and expanding CLI flags.

---

*Analysis updated: 2026-04-08 | Claude Code docs: code.claude.com/docs/en | Zrb version: 2.18.1*
