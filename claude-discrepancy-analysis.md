# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs/en) + internal knowledge. Zrb features sourced from full codebase exploration of `src/zrb/`.
>
> **Zrb version**: 2.16.0
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
32. [Summary & Roadmap](#32-summary--roadmap)

---

## 1. CLI Interface & Flags

### Claude Code

Comprehensive CLI with ~50+ flags:
- `claude "query"` — non-interactive single query
- `-p` / `--print` — print mode (no interactive)
- `-c` / `--continue` — resume last conversation
- `-r` / `--resume` — resume by session ID or name
- `--model` — select model
- `--permission-mode` — set permission mode at startup
- `--yolo` / `--dangerously-skip-permissions` — bypass all confirmations
- `--max-turns` — limit agentic turns
- `--max-budget-usd` — spending cap
- `--output-format` — `text`, `json`, `stream-json`
- `--input-format` — `text`, `stream-json`
- `--system-prompt` / `--append-system-prompt` — customize system prompt
- `--add-dir` — extend working directories
- `--mcp-config` — load MCP config from file
- `--agent` — use specific subagent for whole session
- `--worktree` — run in isolated git worktree
- `--verbose` — detailed logging
- `--bare` — minimal mode (skip hooks, skills, plugins, MCP, memory, CLAUDE.md)
- `--no-session-persistence` — ephemeral sessions
- `--json-schema` — structured JSON output
- `--effort` — effort level (low/medium/high/max)
- `--fork-session` — create new session ID when resuming
- `--fallback-model` — automatic fallback on overload
- `--include-partial-messages` — streaming events in output
- Plus ~30 more flags for remote control, Chrome, agent teams, etc.

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

**Gap**: Zrb covers the most common use cases but lacks ~45 of Claude Code's CLI flags. Critical missing flags: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt` override, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--json-schema`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`.

**Effort to close**:
- **Medium** (2–3 weeks): Map each Claude Code flag to existing Zrb config options and expose them as CLI inputs on `LLMChatTask`. Implement `--output-format` (json/stream-json), `--max-turns`, `--max-budget-usd`, `--system-prompt`, `--resume`. The underlying infrastructure (rate limiting, session management, YOLO) already exists.
- Most flags are thin wrappers over existing CFG settings or LLMChatTask parameters.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich interactive TUI:
- Vim mode (`/vim` or via config) with full NORMAL/INSERT/navigation
- Voice input (push-to-talk with Space)
- `!` bash prefix — run shell command and add to conversation
- `@` file path mention with autocomplete
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
- PR review status in footer (git branch integration)
- Transcript viewer (Ctrl+O)
- Color themes (`/theme`)
- Status line with configurable components
- Ctrl+X Ctrl+K — kill all background agents
- `Ctrl+G` / `Ctrl+X Ctrl+E` — open in external editor
- Command history per working directory (Ctrl+R reverse search)
- Session branching (`/branch` / `/fork`)

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
- `/save` / `/load` — persist/restore sessions; `/load` now displays conversation history (v2.16.0)
- `/compress` / `/compact` — summarize conversation (fixed in v2.16.0)
- `>` / `/redirect` — save last output to file
- **ChatGPT-like interface** — new alternate UI layout (v2.16.0)
- Session persistence
- Configurable greeting, ASCII art, jargon
- Tool approval dialogs with formatted output
- Streaming responses
- Git branch + dirty status in UI info area (`_get_git_info()`)

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has a functional TUI with `!`, `@`, and `/` all implemented. Missing: Vim mode, voice input, image paste from clipboard, permission mode cycling (Shift+Tab), extended thinking toggle, background task management (Ctrl+B), task list toggle (Ctrl+T), checkpoint/rewind menu (Esc+Esc), prompt suggestions from git history, transcript viewer, color themes, configurable status line, side questions (`/btw`), session branching (`/branch`/`/fork`).

**Effort to close**:
- **Medium** (3–5 weeks): Core interactive features are already present. Remaining items are enhancements:
  1. Shift+Tab permission mode cycling (1 day)
  2. Background bash tasks / Ctrl+B (1 week)
  3. Prompt suggestions from git history (1 week)
  4. Vim mode (2–3 weeks) — significant `prompt_toolkit` work
  5. `/btw` side questions (3–4 days) — see §31
  6. Checkpoint/rewind (see §14)
  7. Voice input (2–3 weeks)
  8. Image paste (1 week) — multimodal input pipeline
  9. Color themes (1–2 days)

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~55): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/cost`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw`, `/tasks`, `/permissions`, `/security-review`, `/stats`, `/theme`, `/voice`, etc.

**Bundled skills** as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`

**Custom skills** become slash commands automatically.

**MCP prompts** become `/mcp__<server>__<prompt>` commands.

**Features**: argument interpolation (`$ARGUMENTS`, `$N`), dynamic context injection (`` !`command` ``), command palette with fuzzy search.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1` (positional)
- Skill-based commands via `get_skill_custom_command(skill_manager)`
- Commands registered with `LLMChatTask.add_custom_command()`
- Skills become slash commands via their `name` metadata
- Interactive command palette (via `prompt_toolkit`)

Built-in slash commands (from `base_ui.py`):
- `/compress` / `/compact` — summarize conversation (fixed in v2.16.0)
- `/attach` — attach file to next message
- `/q`, `/bye`, `/quit`, `/exit` — exit session
- `/info`, `/help` — show help
- `/save <name>` — save conversation
- `/load <name>` — load conversation + display history (v2.16.0)
- `/yolo` — toggle YOLO mode
- `>`, `/redirect` — save last output to file
- `!`, `/exec` — execute shell command and inject output
- `/model <name>` — set model mid-conversation
- Custom skill commands auto-registered from skill files

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has the custom command infrastructure and skill-to-slash-command mapping. Missing: ~50 built-in management commands (`/clear`, `/config`, `/diff`, `/rewind`, `/branch`, `/export`, `/cost`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/stats`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/btw`, `/plan`), MCP prompts as commands, bundled utility skills like `/batch`, `/loop`, `/simplify`.

**Effort to close**:
- **Medium** (3–5 weeks): Most built-in commands are wrappers over existing functionality. Need to implement a command dispatch system that maps `/command` to handler functions. Many handlers are trivial (e.g., `/clear`, `/model`); others like `/diff`, `/rewind`, `/security-review` need backing implementation.

---

## 4. Memory System

### Claude Code

**Two mechanisms:**

**CLAUDE.md files** (human-authored):
- Managed/enterprise: system-wide policy
- User-level: `~/.claude/CLAUDE.md` (applies to all projects)
- Project-level: `./CLAUDE.md` or `./.claude/CLAUDE.md` (team-shared)
- Subdirectory: lazy-loaded when Claude reads files in that dir
- `@import` syntax for including other files (max 5 hops)
- `claudeMdExcludes` to skip files
- `.claude/rules/` for path-scoped rules (YAML `paths:` frontmatter, glob patterns)
- `<!-- comments -->` stripped before context injection

**Auto memory** (Claude-authored):
- Claude writes its own notes during conversations
- Stored: `~/.claude/projects/<project>/memory/MEMORY.md` + topic files
- First 200 lines or 25KB loaded at session start
- Topic files loaded on-demand
- Machine-local; not shared across machines
- Toggle: `/memory` command or `autoMemoryEnabled` setting

### Zrb

**CLAUDE.md / AGENTS.md / GEMINI.md / README.md auto-loading** (`src/zrb/llm/prompt/claude.py`):
- `create_project_context_prompt()` included in `PromptManager` by default
- Search path: `~/.claude/` → filesystem root → … → CWD (all parents + CWD)
- Loads `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md` from every directory in hierarchy
- Content: most specific occurrence (closest to CWD) loaded, up to `MAX_PROJECT_DOC_CHARS = 4000` chars
- All occurrences listed; model told to `Read` others on demand

**Journal system** (analog to Claude Code's auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`) — persistent notes written by LLM or user
- Injected into LLM context via `PromptManager` (`include_journal=True`)
- Read/write/search via journal tools; auto-approved for journal dir

**Skill/prompt system**:
- Skills from `.zrb/skills/`, `~/.zrb/skills/`, `.claude/skills/`, `~/.claude/skills/`

**Status**: 🟡 **Partially supported**

**Gap**: CLAUDE.md/AGENTS.md auto-loading is implemented and enabled by default. Missing:
- 4000-char truncation limit per file (Claude Code has no such hard limit)
- `@import` syntax for chaining memory files
- `.claude/rules/` path-scoped rules with YAML `paths:` frontmatter
- `claudeMdExcludes` to skip files
- `<!-- comments -->` stripping before injection
- Subdirectory lazy-loading
- `/memory` command to list/toggle/edit memory files interactively

**Effort to close**:
- **Low-Medium** (1–2 weeks):
  1. Raise or remove 4000-char limit — or make it configurable (1 day)
  2. `<!-- comments -->` stripping in file loader (1 day)
  3. Implement `@import` syntax (2–3 days)
  4. Add `.claude/rules/` path-scoped rule loading (3–5 days)
  5. `/memory` interactive management command (2–3 days)

---

## 5. Hooks System

### Claude Code

**27 hook events** across 6 categories:
- Session: `SessionStart`, `SessionEnd`, `InstructionsLoaded`
- User: `UserPromptSubmit`
- Tool: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`
- Agent teams: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`
- Claude response: `Stop`, `StopFailure`
- File/env: `CwdChanged`, `FileChanged`, `ConfigChange`
- Compaction: `PreCompact`, `PostCompact`
- MCP: `Elicitation`, `ElicitationResult`
- Worktree: `WorktreeCreate`, `WorktreeRemove`
- Notification: `Notification`

**4 handler types**: `command` (shell), `http` (POST request), `prompt` (Claude eval), `agent` (sub-agent with tools)

**Features**:
- Conditional execution via `if` field
- Async hooks (`"async": true`)
- Hook deduplication
- `statusMessage` for spinner
- `once` per session (skills)
- Decision output: `allow`, `deny`, `ask`, `block`
- `additionalContext` injection
- `updatedInput` for modifying tool inputs
- `CLAUDE_ENV_FILE` for persisting env vars
- Config locations: user, project, local, managed policy, plugin, skill/agent frontmatter
- `/hooks` management UI

### Zrb

**14 hook events** (`src/zrb/llm/hook/types.py`):
- `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`
- `PostToolUse`, `PostToolUseFailure`, `Notification`
- `SubagentStart`, `SubagentStop`, `Stop`
- `TeammateIdle`, `TaskCompleted`, `PreCompact`, `SessionEnd`

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent)

**Features**:
- Operator-based matchers: `equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `regex`, `glob`
- Async/sync execution with timeouts
- Skill frontmatter hook definitions
- `HookManager` singleton with YAML/JSON config
- Config from: `HOOKS_DIRS`, `HOOKS_TIMEOUT`
- Claude Code string compatibility mapping

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has 14 of Claude Code's 27 events. Missing events: `InstructionsLoaded`, `StopFailure`, `CwdChanged`, `FileChanged`, `ConfigChange`, `PostCompact`, `Elicitation`, `ElicitationResult`, `WorktreeCreate`, `WorktreeRemove`. Missing handler type: `http`. Missing features: `additionalContext` injection, `updatedInput` modification, `CLAUDE_ENV_FILE` persistence, `once` flag, `statusMessage`, `/hooks` management UI, conditional `if` field, hook deduplication.

**Effort to close**:
- **Medium** (3–4 weeks):
  1. Add missing event types to `HookEvent` enum (1 day)
  2. Fire missing events at appropriate lifecycle points (1 week)
  3. Add `http` handler type (2–3 days)
  4. Add `additionalContext` and `updatedInput` to hook output protocol (2–3 days)
  5. Add `if` conditional field, async flag, `once` flag, `statusMessage` (2–3 days)
  6. Hook deduplication (1 day)
  7. `/hooks` management command in TUI (2–3 days)
  8. `CLAUDE_ENV_FILE` persistence mechanism (2 days)

---

## 6. MCP (Model Context Protocol)

### Claude Code

**Transports**: `stdio`, `http`, `sse`, `ws`

**Config scopes** (priority order):
1. Local project: `.claude/mcp.json` or `.mcp.json`
2. User: `~/.claude/mcp.json`
3. Project: `.claude/settings.json` `mcpServers` key
4. CLI: `--mcp-config` flag

**Features**:
- `claude mcp add` CLI command for easy setup
- OAuth authentication for MCP servers (`/mcp` command)
- MCP prompts become `/mcp__<server>__<prompt>` commands
- MCP tool search (deferred tools for scale)
- MCP resources (`ListMcpResourcesTool`, `ReadMcpResourceTool`)
- Subagent-scoped MCP servers
- `allowManagedMcpServersOnly` policy
- `--strict-mcp-config`
- `/mcp` command for interactive management

### Zrb

- Transports: `stdio`, `sse`
- Config: `mcp-config.json` searched from home → project hierarchy → CWD
- Environment variable expansion in config
- Integrated via `load_mcp_config()` in `LLMChatTask`
- Uses Pydantic AI's `MCPServerStdio` / `MCPServerSSE`

**Status**: 🟡 **Partially supported**

**Gap**: Core MCP functionality works (`stdio`, `sse`). Missing: `http` and `ws` transports, CLI command for easy server addition (`zrb mcp add`), OAuth authentication, MCP prompts as slash commands, MCP tool search/deferred loading, MCP resources tools, subagent-scoped MCP, `/mcp` interactive management UI, managed-only policy.

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
- File locations: `--agents` flag > `.claude/agents/` > `~/.claude/agents/` > plugin `agents/`
- Fields: `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `initialPrompt`
- Invocation: natural language, `@-mention` (guaranteed), `--agent` flag, `agent` setting
- Foreground vs background: Ctrl+B to background
- Subagent context compaction (auto at ~95%)
- Tool access control: `tools` allowlist, `disallowedTools` denylist
- `Agent(worker)` syntax for nested agent restrictions
- Subagent isolation: `isolation: worktree`
- Subagent memory: `memory: user/project/local`
- Auto-delegation based on description matching

**Built-in subagents**: Explore, Plan, general-purpose, Bash, statusline-setup, Claude Code Guide

### Zrb

Delegate tool system:
- `create_delegate_to_agent_tool()` — sequential sub-agent call
- `create_parallel_delegate_tool()` — concurrent multi-agent
- `SubAgentManager` with tool registry
- `BufferedUI` for output synchronization
- Agent discovery from YAML configs
- Shared rate limiter across agents
- Foreground/background via async execution

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has working multi-agent delegation but implemented as tools (programmatic), not as declarative YAML files that Claude auto-discovers. Missing: file-based agent definitions (`.zrb/agents/`), natural language / `@-mention` invocation, subagent-specific `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `initialPrompt`, subagent session resumption, context compaction per subagent, tool access control syntax, `--agent` flag.

**Effort to close**:
- **High** (6–8 weeks):
  1. Implement file-based agent definition loader (`.zrb/agents/*.md`) (1 week)
  2. YAML frontmatter parsing for all fields (3–4 days)
  3. `@-mention` in TUI input with agent typeahead (3–4 days)
  4. Natural language delegation (3–4 days)
  5. Per-agent permission mode, maxTurns, memory (1 week)
  6. Subagent-scoped MCP (1 week)
  7. Worktree isolation per agent (1–2 weeks)
  8. `--agent` session flag (1 day)

---

## 8. Agent Teams (Experimental)

### Claude Code

- Multiple Claude Code instances working together
- Shared task list with self-coordination
- Inter-agent direct messaging (`SendMessage` tool)
- Display modes: in-process (Shift+Down to cycle) or split tmux panes
- `TeamCreate` / `TeamDelete` tools
- File locking for race condition prevention
- Task dependencies between team members
- Hooks: `TeammateIdle`, `TaskCreated`, `TaskCompleted`
- Storage: `~/.claude/teams/`, `~/.claude/tasks/`
- Enable: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

### Zrb

`create_parallel_delegate_tool()`:
- Concurrent multi-agent execution
- Aggregated results
- Shared rate limiter and UI lock
- Error handling per agent

No team coordination, no inter-agent messaging, no shared task list.

**Status**: ❌ **Not supported** (parallel delegation exists but not agent teams)

**Gap**: Zrb's parallel delegation is a tool call, not persistent coordinated agents. Missing: persistent agent team lifecycle, inter-agent messaging, shared task list with dependencies, display modes (tmux split), team-specific hooks, file locking, `TeamCreate`/`TeamDelete`.

**Effort to close**:
- **Very High** (8–12 weeks): Fundamentally different architecture. Requires persistent agent process management, shared task list store, inter-agent message bus, tmux/terminal multiplexing integration, team lifecycle hooks, and file locking.

---

## 9. Skills System

### Claude Code

File-based skill system (`.claude/skills/<skill-name>/SKILL.md`):
- Scopes: managed/enterprise > personal > project > plugin
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `effort`, `context` (fork), `agent`, `hooks`, `paths`, `shell`
- String substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`
- Dynamic context injection: `` !`command` `` runs shell at load time
- Skills in forked subagent context (`context: fork`, `agent: Explore`)
- `allowed-tools` grants pre-approval for tool calls during skill
- Path-scoped activation (`paths:` glob patterns)
- Monorepo auto-discovery from nested `.claude/skills/`

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

**Status**: ✅ **Fully supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` frontmatter field, `hooks` in skill frontmatter, `paths:` glob activation patterns, `shell` field, `` !`command` `` dynamic context injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitution variables, `once` hook flag, skill descriptions budget enforcement, monorepo nested auto-discovery.

**Effort to close**:
- **Low** (1–2 weeks): Zrb's skill infrastructure is excellent. Mostly additive:
  1. Add `effort`, `hooks`, `paths`, `shell` frontmatter fields (2–3 days)
  2. `` !`command` `` preprocessing at load time (1–2 days)
  3. `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR` substitutions (1 day)
  4. Descriptions budget enforcement (1 day)

---

## 10. Permission Modes & Tool Approval

### Claude Code

**6 permission modes**:
- `default` — read-only auto-approve; prompt for write/execute
- `acceptEdits` — auto-approve reads and file edits
- `plan` — read-only; Claude plans but doesn't execute
- `auto` — all actions with background safety classifier (Team/Enterprise only)
- `bypassPermissions` — no checks (containers/VMs only)
- `dontAsk` — auto-deny everything not pre-approved

**Mode switching**: Shift+Tab cycling during session; `--permission-mode` flag at startup

**Permission rules**: `Tool`, `Tool(specifier)`, glob patterns, domain restricts, MCP tool patterns
- Evaluation: deny > ask > allow (first match wins)
- Config levels: managed > CLI > local > project > user

**PermissionRequest hook**: intercept permission dialogs

### Zrb

**Tool approval system**:
- YOLO mode (`--yolo`) = `bypassPermissions`
- `auto_approve()` function with condition callbacks
- `approve_if_path_inside_cwd`, `approve_if_path_inside_journal_dir` conditions
- Per-tool validation policies: `replace_in_file_validation_policy`, `read_file_validation_policy`, `read_files_validation_policy`
- Tool call confirmation dialogs in TUI
- `ApprovalChannel` class for async approval
- Multiplex approval channels (terminal + Telegram simultaneously)

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has YOLO mode and per-tool approval policies. Missing: named permission modes beyond YOLO/non-YOLO, `acceptEdits` mode, `plan` mode (read-only planning), `dontAsk` mode (auto-deny non-allowlisted), `auto` mode with safety classifier, Shift+Tab cycling, permission rules configuration syntax (glob patterns, domain restricts, `Bash(npm run *)` style), `PermissionRequest` hook, rule evaluation precedence, admin-managed permission policies.

**Effort to close**:
- **Medium-High** (4–6 weeks):
  1. Implement named permission mode enum + state (1 day)
  2. `plan` mode (read-only enforcement) (3–4 days)
  3. `acceptEdits` mode (1 day)
  4. `dontAsk` mode (2 days)
  5. Permission rules config syntax parser (1 week)
  6. Rule evaluation engine with deny>ask>allow precedence (3–4 days)
  7. Shift+Tab mode cycling in TUI (1 day)
  8. `PermissionRequest` hook event (2 days)

---

## 11. Settings & Configuration System

### Claude Code

**4 config scopes**: managed (system) > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`)

**JSON schema** for autocomplete

**Key settings**: `permissions.*`, `model`, `agent`, `additionalDirectories`, `autoMemoryEnabled`, `autoMemoryDirectory`, `claudeMdExcludes`, `mcpServers`, `hooks`, `env`, `sandbox.*`, `autoMode.*`, `cleanupPeriodDays`, `defaultShell`, `teammateMode`

**`/config` command**: interactive tabbed settings UI

### Zrb

**Single config source**: `CFG` singleton loaded from environment variables (prefix: `ZRB_`)

Categories: `ZRB_LLM_MODEL`, `ZRB_LLM_API_KEY`, `ZRB_WEB_HTTP_PORT`, `ZRB_LLM_MAX_TOKENS`, rate limits, directories, UI, search, hooks, MCP, RAG

**Status**: 🟡 **Partially supported**

**Gap**: Zrb's config is env-var only (no JSON settings files), no layered scopes (user/project/local/managed), no `/config` interactive UI, no JSON schema validation, no managed/enterprise policy layer.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. JSON settings file loader with scope hierarchy (1 week)
  2. Merge settings with env vars (2 days)
  3. JSON schema generation (2–3 days)
  4. `/config` interactive settings UI in TUI (1 week)

---

## 12. Built-in Tools

### Claude Code (35 tools)

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
| `WebSearch` | ✅ `search_internet` (SearXNG/Brave/SerpAPI; flexible search v2.16.0) |
| `AskUserQuestion` | 🟡 Exists as hook/approval but not standalone LLM tool |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full LSP tool suite |
| `TaskCreate/Get/List/Update/Stop` | ✅ `write_todos`, `get_todos`, `update_todo`, `clear_todos` |
| `CronCreate/Delete/List` | ❌ Not implemented as LLM tools |
| `EnterPlanMode` / `ExitPlanMode` | ❌ No plan mode |
| `EnterWorktree` / `ExitWorktree` | ❌ No worktree management |
| `SendMessage` (agent teams) | ❌ Agent teams not implemented |
| `TeamCreate` / `TeamDelete` | ❌ Agent teams not implemented |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` | ❌ Not implemented |
| `ReadMcpResourceTool` | ❌ Not implemented |
| `PowerShell` | ❌ Not implemented (Windows-only) |

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

**Status**: 🟡 **Partially supported**

**Gap**: Core file/shell/web tools are well-covered. Missing: `AskUserQuestion` as standalone tool, `NotebookEdit`, `CronCreate/Delete/List`, `EnterPlanMode`/`ExitPlanMode`, `EnterWorktree`/`ExitWorktree`, `SendMessage`, `TeamCreate`/`TeamDelete`, `ToolSearch`, MCP resource tools.

**Effort to close**:
- **Medium** (2–3 weeks):
  1. `AskUserQuestion` tool (2–3 days)
  2. `NotebookEdit` for Jupyter notebooks (3–4 days)
  3. `CronCreate`/`CronDelete`/`CronList` (3–4 days, reuse Zrb's Scheduler)
  4. `EnterPlanMode`/`ExitPlanMode` (2 days, after plan mode implemented)
  5. `EnterWorktree`/`ExitWorktree` (1–2 weeks, see §30)
  6. `ToolSearch` deferred loading (1 week)

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
- Jupyter notebook execution via IDE MCP
- Built-in IDE MCP server on random port

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

### Zrb

**Web UI** (FastAPI-based):
- Browser-based chat interface
- Session persistence
- Model switching
- YOLO mode toggle
- Authentication (JWT)
- SSE streaming
- ChatGPT-like interface layout (v2.16.0)

No VS Code / JetBrains / Desktop app integration.

**Status**: ❌ **Not supported** (IDE integrations); 🟡 Web UI is a different paradigm

**Gap**: Complete lack of IDE integrations. No VS Code extension, no JetBrains plugin, no desktop app, no inline diffs in editor, no `@`-mention with editor context, no selection sharing.

**Effort to close**:
- **Very High** (3–6 months for full parity):
  1. VS Code Extension wrapping Zrb's API (4–8 weeks for MVP)
  2. JetBrains Plugin (4–8 weeks)
  3. Desktop App (Electron or Tauri, 3–6 weeks for MVP)
  4. Consider: expose Zrb's LLMChatTask as an MCP server so existing editors can connect directly

---

## 14. Session Management & Checkpointing

### Claude Code

**Checkpointing**:
- Automatic checkpoint before every file edit
- Every user prompt creates a new checkpoint
- Persist across sessions (30 days by default)
- Rewind menu (Esc+Esc): restore code+conversation, restore conversation only, restore code only
- `/rewind` command
- Session branching (`/branch` / `/fork`)

**Session management**:
- Sessions stored per working directory
- `--continue` / `-c` resumes last session
- `--resume` / `-r` resumes by ID or name, or shows picker
- `--fork-session` creates new ID when resuming
- `--from-pr` resumes sessions linked to GitHub PR
- `--no-session-persistence` for ephemeral sessions
- Session export (`/export`)
- Session statistics (`/stats`, `/insights`)

### Zrb

**Session management**:
- `FileHistoryManager` stores conversation history to disk (`~/.zrb/history/{name}.json`)
- Named sessions via `--session` input
- Conversation persistence per session name
- Automatic timestamped backups
- History summarization on long contexts
- `/load <name>` now displays loaded conversation history (v2.16.0)
- Fuzzy search for session discovery

**No checkpointing, no rewind, no session branching, no resume-by-ID picker.**

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has session persistence and named sessions. Missing: checkpointing (snapshot before each edit), rewind/restore (code and conversation), session branching/forking, resume-by-ID picker, `--fork-session`, session export, session statistics/insights, `--from-pr` resume.

**Effort to close**:
- **High** (5–8 weeks):
  1. Checkpoint snapshots: store file state before each write/edit tool call (1–2 weeks)
  2. Rewind menu in TUI: Esc+Esc handler, show checkpoint list (1 week)
  3. Code-only / conversation-only restore (3–4 days each)
  4. Session branching (fork conversation at point) (1 week)
  5. Resume-by-ID picker in TUI (2–3 days)
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
- Session persistence
- Model switching
- YOLO mode toggle
- JWT authentication (guest + admin roles)
- SSL/TLS support
- Task browsing and execution
- REST API for programmatic access
- ChatGPT-like interface layout option (v2.16.0)

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
- Team/Enterprise plans only

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
- **`/install-github-app`**: set up Claude GitHub app
- **`--from-pr`**: resume sessions linked to GitHub PR
- **`/pr-comments`**: fetch and display GitHub PR comments
- **PR status footer**: shows open PR status in session footer
- **`/security-review`**: analyze pending changes for vulnerabilities
- **Slack integration**
- **`/batch`**: spawns parallel agents in git worktrees, each creates a PR

### Zrb

🔵 **Zrb-only**: Task automation system with Git utilities (`src/zrb/builtin/`):
- `git` group: git-related built-in tasks
- `run_shell_command` tool can run `gh`, `git` commands
- RAG tools for code analysis

No native GitHub app, no CI/CD pipeline integration, no PR comment triggers, no Slack integration.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**:
- **High** (4–8 weeks):
  1. GitHub Actions workflow template calling `zrb llm chat -p` (1–2 days)
  2. GitLab CI template (1 day)
  3. PR status footer via `gh` CLI in TUI (1–2 days)
  4. `/pr-comments` command (2–3 days)
  5. `/security-review` built-in skill (1–2 days, uses existing tools)
  6. GitHub webhook → Zrb trigger (2–3 weeks)

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
- Remote control from claude.ai, Claude app, Telegram, Discord, iMessage
- Cloud sessions shared across devices
- Channels: MCP servers with notification channels

### Zrb

🔵 **Zrb-only**: Built-in web server:
- `zrb server start` → local web UI
- REST API for external access
- JWT authentication
- SSL/TLS support

No cloud sessions, no remote control protocol, no multi-device sync.

**Status**: 🟡 **Different approach** — Zrb has a local web server; Claude Code has cloud infrastructure

**Gap**: True cloud sessions require cloud infrastructure that Zrb doesn't have by design (self-hosted). The remote control protocol (Telegram, Discord) is entirely absent.

**Effort to close**:
- **Low–Medium** for remote API (existing web server already provides this)
- **Very High** for true cloud sessions
- **Medium** (2–3 weeks) for simple remote control:
  1. Session sharing via URL (2–3 days)
  2. WebSocket-based remote control in web UI (1 week)
  3. Telegram/Discord bot integration (2 weeks, separate projects)

---

## 20. Plugins System

### Claude Code

Plugin architecture:
- Install from marketplace or local directory
- `--plugin-dir` for session-only plugins
- Plugin structure: `hooks/hooks.json`, `agents/`, `skills/`, `mcp.json`
- Plugin scopes for hooks, agents, skills, MCP servers
- `claude plugin` CLI command
- `/plugin` interactive management
- `/reload-plugins` without restart

### Zrb

**Skill system** (closest analog):
- Skills from multiple directories act as mini-plugins
- `CFG.LLM_PLUGIN_DIRS` for user plugin directories
- MCP config from multiple locations

No formal plugin packaging/marketplace, no `claude plugin` command, no plugin lifecycle management, no plugin-scoped hooks/agents/MCP bundling.

**Status**: 🟡 **Partially supported** (via skills + MCP, but no plugin packaging)

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

Missing: per-session budget cap (`--max-budget-usd`), `/cost` command, cumulative spend tracking, fallback model on overload.

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
- **Windows**: Native (WSL), PowerShell install, WinGet, Desktop app
- **iOS/Android**: Claude mobile app (cloud sessions)
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

Zrb has a **two-layer** auto-summarization system (`src/zrb/llm/summarizer/`):

**Layer 1 — Per-message summarization** (`message_processor.py`):
- Individual tool results exceeding threshold are summarized in-place
- Truncates "insanely large" results first, then LLM-summarizes

**Layer 2 — Conversational history summarization** (`history_summarizer.py`):
- Triggers when `len(messages) > LLM_HISTORY_SUMMARIZATION_WINDOW` OR total tokens > threshold
- Intelligent split: respects tool call/return pairs, prefers turn boundaries
- Chunk-and-summarize with `<state_snapshot>` consolidation
- Summary prepended as `SYSTEM: Automated Context Restoration` user message

**Manual compaction**: `/compress` / `/compact` commands (fixed in v2.16.0)

**Status**: 🟡 **Partially supported**

**Gap**: Core auto-compaction is robustly implemented. Missing: `PreCompact`/`PostCompact` hook events, focus instructions for manual compact, original transcript preservation in `.jsonl`.

**Effort to close**:
- **Low** (3–5 days):
  1. Add `PreCompact`/`PostCompact` hook events around summarization calls (2 days)
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

### Zrb

No Vim mode. Standard `prompt_toolkit` input only.

**Status**: ❌ **Not supported**

**Effort to close**:
- **Medium** (2–3 weeks): Implement Vim mode as a `prompt_toolkit` key binding layer. `prompt_toolkit` has partial Vi mode support via `vi_mode=True` in `KeyBindings`; full text object support requires custom implementation.

---

## 26. Voice Input

### Claude Code

- Push-to-talk: hold Space for dictation
- Requires voice dictation enabled in system
- Rebindable key binding
- `/voice` command to toggle

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
- **Low–Medium** (1–2 weeks): Implement `/diff` command using `unified_diff` or `rich` library. Checkpoint-based diffs need checkpoint system first (§14).

---

## 28. Task / Todo System

### Claude Code

**TaskCreate/Update/Get/List/Stop tools** (for background bash tasks):
- Background tasks with unique IDs
- Auto-cleaned on exit
- `Ctrl+T` to toggle task list UI
- Auto-terminated if output exceeds 5GB
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

### Zrb

🔵 **Zrb advantage**: Full `Scheduler` task type for cron-based automation (separate from LLM tools). `CmdTask` with cron-like scheduling.

No `CronCreate`/`CronDelete`/`CronList` as LLM-callable tools within a chat session.

**Status**: 🟡 **Partially supported** (scheduling at task level; not as in-session LLM tools)

**Effort to close**:
- **Low** (2–3 days): Wrap Zrb's `Scheduler` as `CronCreate`/`CronDelete`/`CronList` LLM tools usable during chat sessions.

---

## 30. Worktree Isolation

### Claude Code

Git worktree isolation is a first-class feature for safe parallel work:

**CLI**:
- `--worktree` flag: run Claude in an isolated git worktree (auto-creates, auto-cleans if no changes)

**Agent definitions**:
- `isolation: worktree` in `AGENT.md` frontmatter — each subagent gets its own worktree
- Worktree branch auto-named from agent name + ULID
- Returns worktree path and branch name if changes made

**Built-in tools**:
- `EnterWorktree` — create and enter a new git worktree
- `ExitWorktree` — exit and optionally clean up the worktree

**Hook events**:
- `WorktreeCreate` — fires when a worktree is created
- `WorktreeRemove` — fires when a worktree is destroyed

**`/batch` command**:
- Spawns multiple agents in parallel worktrees, each working on a separate feature/fix
- Each agent creates its own PR upon completion

**Use cases**:
- Run code changes without affecting main working tree
- Parallel agent work on the same repository without conflicts
- Safe experimentation with automatic cleanup

### Zrb

No worktree support in any form:
- No `--worktree` flag
- No `isolation: worktree` in agent definitions
- No `EnterWorktree`/`ExitWorktree` tools
- No `WorktreeCreate`/`WorktreeRemove` hook events
- No `/batch` parallel worktree command
- Git utilities in `src/zrb/llm/util/git.py` exist but are for mandate extraction only

**Status**: ❌ **Not supported**

**Gap**: Worktree isolation is critical for safe parallel agent execution. Without it, multiple agents working on the same repo will conflict. The `/batch` pattern (one PR per agent per worktree) is entirely absent.

**Effort to close**:
- **Medium-High** (3–5 weeks):
  1. `git worktree` wrapper utility in `src/zrb/llm/util/git.py` (2–3 days)
  2. `EnterWorktree` / `ExitWorktree` tools (2–3 days)
  3. `--worktree` CLI flag for `zrb llm chat` (1–2 days)
  4. `isolation: worktree` support in subagent definitions (1 week)
  5. `WorktreeCreate` / `WorktreeRemove` hook events (2 days)
  6. Auto-cleanup of empty worktrees on session end (2 days)
  7. `/batch` command (2–3 weeks, requires worktree + parallel delegation + PR creation)

---

## 31. Side Questions (`/btw`)

### Claude Code

`/btw <question>` — ask a side question that does NOT get added to the conversation history:
- Claude answers the question but the Q&A pair is dropped from the transcript
- Useful for quick clarifications ("btw what does this function do?") without polluting the main task context
- The answer is shown in the terminal but not stored in history
- Does not interrupt in-progress agent work
- Implemented as a special input prefix: typing `/btw what is X?` sends X to the model in an ephemeral context

### Zrb

No `/btw` equivalent. Every user message and model response is recorded in the session history. There is no mechanism to ask ephemeral questions outside the conversation thread.

Closest approximations:
- `create_delegate_to_agent_tool()` — delegates to a sub-agent, which has its own blank-slate context, but this is an LLM-initiated action, not a user-initiated side question
- Opening a second `zrb llm chat` session manually

**Status**: ❌ **Not supported**

**Gap**: `/btw` is a productivity feature for maintaining focused context. Without it, every clarifying question bloats the conversation history and can distort the model's sense of the current task.

**Effort to close**:
- **Low** (3–4 days):
  1. Detect `/btw <question>` prefix in `base_ui.py` command handlers (1 day)
  2. Send question to model in a temporary context (not appended to `_history_manager`) (1 day)
  3. Display answer without writing to session history (1 day)
  4. Optionally: allow `/btw` during active agent thinking (requires queuing or interruption logic, +2 days)

---

## 32. Summary & Roadmap

### Overall Coverage Assessment

| Category | Status | Priority |
|----------|--------|----------|
| CLI Flags | 🟡 ~30% coverage | High |
| Interactive TUI | 🟡 ~60% coverage (`!`, `@`, `/` all present; missing vim/voice/themes) | Medium |
| Slash Commands | 🟡 ~40% built-in (core set present; ~50 management cmds missing) | Medium |
| Memory/CLAUDE.md | 🟡 ~75% (auto-loading ✅, @import/rules/lazy-load missing) | Low-Medium |
| Hooks | 🟡 ~50% (14/27 events; missing http handler, worktree events) | High |
| MCP | 🟡 ~60% | High |
| Subagents | 🟡 ~50% | High |
| Agent Teams | ❌ 0% | Low |
| Skills | ✅ ~85% | Low |
| Permission Modes | 🟡 ~30% | High |
| Settings System | 🟡 ~30% | Medium |
| Built-in Tools | 🟡 ~70% | Medium |
| IDE Integrations | ❌ 0% | Medium |
| Session/Checkpoint | 🟡 ~45% (load+display ✅ v2.16.0; no checkpoint/rewind) | High |
| Web UI | 🔵 Zrb advantage (ChatGPT UI v2.16.0) | — |
| Auto Mode | ❌ 0% | Low |
| GitHub/CI Integration | ❌ 0% | Medium |
| Sandboxing | ❌ 0% | Low |
| Remote/Cloud | 🟡 Different approach | Low |
| Plugins | 🟡 ~40% | Medium |
| Rate Limiting | 🟡 ~70% (Zrb better on rate limits; missing budget) | Low |
| Platform Support | 🟡 ~80% | Low |
| LSP | ✅ Zrb advantage | — |
| Context Compaction | 🟡 ~85% (two-layer ✅; PreCompact hooks + focus args missing) | Low |
| Vim Mode | ❌ 0% | Low |
| Voice Input | ❌ 0% | Low |
| Diff Viewer | ❌ 0% | Low |
| Task/Todo | ✅ Zrb advantage | — |
| Scheduling | 🟡 Zrb advantage at task level; missing in-session LLM tools | Low |
| **Worktree Isolation** | ❌ 0% | **High** |
| **Side Questions (`/btw`)** | ❌ 0% | **Medium** |

### Zrb Unique Advantages (Superset Features)

These are features Zrb has that Claude Code does not:

1. 🔵 **Local Web UI**: Full browser-based interface with auth, streaming, task management, ChatGPT-like layout (v2.16.0)
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
14. 🔵 **Flexible web search**: SearXNG with page/safe_search/language params (v2.16.0); also supports Brave + SerpAPI backends
15. 🔵 **Multiplex approval channels**: route tool approvals to terminal + Telegram simultaneously

### Notable Changes in v2.16.0

- **`/load` now displays conversation history**: when loading a session, the full conversation is rendered so the user can see context immediately
- **Fixed `/compress` and `/compact` commands**: bug fix for manual summarization
- **Flexible web search**: `search_internet` (SearXNG backend) now accepts `page`, `safe_search`, and `language` parameters
- **ChatGPT-like interface**: new alternate UI layout in the web UI

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. **`/btw` side questions** — ephemeral Q&A outside history (3–4 days) — **new, high UX impact**
2. **Worktree isolation basics** — `EnterWorktree`/`ExitWorktree` tools + `--worktree` flag (1 week) — **new, critical for safe parallel work**
3. **Extended CLI flags**: `--permission-mode`, `--max-turns`, `--system-prompt`, `--resume`, `--output-format json` (1 week)
4. **Named permission modes**: add `plan`, `acceptEdits`, `dontAsk` to existing YOLO/non-YOLO (1 week)
5. **Shift+Tab mode cycling** (1 day)
6. **Additional built-in slash commands**: `/clear`, `/config`, `/cost`, `/export`, `/permissions`, `/diff` (1 week)
7. **`PreCompact`/`PostCompact` hook events + `/compress [focus]` argument** (3–5 days)
8. **JSON settings files** with scope hierarchy (1 week)
9. **MCP prompts as slash commands** (3 days)

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

10. **Checkpoint system** + `/rewind` (2–3 weeks)
11. **Full worktree isolation** — `isolation: worktree` in subagent definitions + `/batch` command (2–3 weeks)
12. **File-based agent definitions** (`.zrb/agents/`) + `@-mention` invocation (2–3 weeks)
13. **GitHub CI/CD templates** (1 week)
14. **Plugin packaging format** (1–2 weeks)
15. **Missing built-in tools**: `AskUserQuestion`, `NotebookEdit`, `CronCreate/Delete/List` (2 weeks)
16. **MCP `http`/`ws` transports** + OAuth + resources tools (2–3 weeks)
17. **Permission rules config syntax** (1 week)
18. **`/diff` command** (1 week)

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

19. **Auto mode safety classifier** (4–6 weeks)
20. **IDE integrations** (VS Code extension, JetBrains plugin) — separate major projects (3–4 months)
21. **Vim mode** in TUI (2–3 weeks)
22. **Agent Teams** — persistent coordinated agents (2–3 months)
23. **OS-level sandboxing** (3–5 weeks)
24. **Voice input** (2–3 weeks)
25. **Desktop app** (Electron/Tauri wrapper) (4–6 weeks)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~6–8 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~7–10 months with 2–3 developers

Zrb's architecture is well-suited for most of these additions — the plugin system, hook infrastructure, tool system, and TUI are all extensible. The largest new gaps (worktree isolation, `/btw`) are actually among the easier ones to implement. The truly hard items remain IDE integrations, agent teams, and the auto mode classifier.

---

*Analysis updated: 2026-04-03 | Claude Code docs: code.claude.com/docs/en | Zrb version: 2.16.0*
