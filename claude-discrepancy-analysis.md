# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs) and the public CHANGELOG, surveyed June 2026. Zrb features sourced from full codebase exploration of `src/zrb/` at v2.34.3 plus the changelog (`docs/changelog.md`, `docs/changelog-v2.md`) and ADRs 0049–0065.
>
> **Zrb version**: 2.34.3 (June 12, 2026)
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
8. [Agent Teams & Dynamic Workflows](#8-agent-teams--dynamic-workflows)
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
24. [Context Compaction & Prompt Caching](#24-context-compaction--prompt-caching)
25. [Vim Mode & Editor Features](#25-vim-mode--editor-features)
26. [Voice Input](#26-voice-input)
27. [Diff Viewer](#27-diff-viewer)
28. [Task / Todo System](#28-task--todo-system)
29. [Scheduling](#29-scheduling)
30. [Worktree Isolation](#30-worktree-isolation)
31. [Multimodal & Attachments](#31-multimodal--attachments)
32. [Provider Resilience & Multi-Model](#32-provider-resilience--multi-model)
33. [Side Questions (`/btw`)](#33-side-questions-btw)
34. [Channels & Remote Control](#34-channels--remote-control)
35. [Summary & Roadmap](#35-summary--roadmap)

---

## 1. CLI Interface & Flags

### Claude Code

Comprehensive CLI with 70+ flags across 30+ subcommands. Highlights (June 2026):
- `claude "query"`, `-p`/`--print`, `-c`/`--continue`, `-r`/`--resume`, `-n`/`--name`
- `--model`, `--permission-mode` (`ask`/`auto`/`acceptEdits`/`bypassPermissions`/`plan`), `--dangerously-skip-permissions`
- `--max-turns`, `--max-budget-usd`, `--output-format` (`text`/`json`/`stream-json`), `--input-format`
- `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`, `--settings` (JSON override), `--safe-mode`
- `--mcp-config`, `--strict-mcp-config`, `--agent`, `--agents`, `--allowedTools`/`--disallowedTools`
- `--worktree`/`-w`, `--tmux`, `--effort` (`low`/`medium`/`high`/`xhigh`/`max`/**`ultracode`**), `--fork-session`, `--fallback-model` (chain, up to 3)
- `--bare`, `--no-session-persistence`, `--json-schema`, `--include-partial-messages`, `--include-hook-events`
- `--channels`, `--chrome`/`--no-chrome`, `--remote`, `--remote-control`/`--rc`, `--teleport`, `--teammate-mode` (`auto`/`in-process`/`tmux`)
- `--plugin-dir` (accepts `.zip`), `--plugin-url`, `--from-pr`
- Subcommands: `claude agents` (background-session dashboard), `claude auto-mode defaults`, `claude auth`, `claude mcp` (`add`/`list`/`remove`/`get`), `claude plugin` (`init`/`validate`), `claude setup-token`, `claude update`, `claude ultrareview`, `claude remote-control`

### Zrb

`zrb llm chat` with **6 CLI inputs** (`src/zrb/builtin/llm/chat.py`) — structurally unchanged since v2.22.6:
- `--message` / `-m`
- `--model`
- `--session` — conversation session name
- `--yolo` — bypass confirmations; full (`true`) or selective (`--yolo "Write,Edit"`)
- `--attach` — file attachments (multimodal-aware, §31)
- `--interactive` — toggle interactive mode (default `true`)

**Status**: 🟡 **Partially supported**

**Gap**: Still 6 inputs against Claude Code's 70+ flags. The *underlying infra* has grown substantially (permission policy + plan mode, sandbox, background delegation, prompt caching, rate limiting, snapshots) — but very little of it is exposed as CLI flags. Critical missing surface: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--plugin-dir`, `--remote-control`, `--channels`. Notably, plan mode and sandbox now exist (toggled in-session / via env vars) but have **no CLI flag**.

**Effort to close**: **Medium** (2–3 weeks) — map each flag to existing Zrb config and expose as CLI inputs on `LLMChatTask`. Most backing functionality now exists; this is surface wiring.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich interactive TUI:
- Vim mode with NORMAL/INSERT/navigation; visual mode (`v`/`V`) with operators; `/vim` or `editorMode`
- Voice input (push-to-talk)
- `!` bash prefix, `@` file mention with autocomplete, `/` command palette
- Multiline input (Shift+Enter, Option+Enter, `\`+Enter, Ctrl+J)
- Shortcuts: Ctrl+C/D/L/O/R, Ctrl+B (background bash), Ctrl+T (task list), Esc+Esc (rewind menu), Shift+Tab/Alt+M (permission-mode cycling), Option+P/T/O (model / thinking / fast mode)
- `/btw` side questions, image paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11)
- Prompt suggestions from git history, transcript viewer, color themes (custom theme editing), configurable status line
- Terminal progress bar, spinner tips, reduced motion, deep links, `/scroll-speed`, `CLAUDE_CODE_HIDE_CWD`

### Zrb

`prompt_toolkit`-based TUI (`src/zrb/llm/ui/`):
- Multi-line input (trailing `\` continuation, Ctrl+J newline)
- Command history with reverse search
- **`!` bash prefix** — `! cmd` / `/exec cmd` runs shell and injects output
- **`@` file mention** with autocomplete (`completion.py`)
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach`, `/model` (+ `small`/`multimodal` subcommands), `/yolo` (full + selective), `/plan` (toggle read-only mode), `/save` / `/load`, `/compress` / `/compact`, `>` / `/redirect`, `/copy`, `/btw`, `/rewind`
- **`/copy` + clipboard `/redirect`** ✅ **NEW (v2.33.2)**: `/copy` copies the full transcript to clipboard (or a file with an arg); bare `/redirect` copies the last AI response to clipboard. Uses `pyperclip` with an **OSC 52** terminal-escape fallback (works over SSH/tmux/screen)
- **Arrow-key selection UI for `AskUserQuestion`** ✅ **NEW (v2.34.0)**: ↑/↓ to move, Enter to confirm, Space to toggle in multi-select, plus a synthetic "✎ Type my own answer…" row. Rendered as an in-layout `Float` (`SelectionMixin`); web/`SimpleUI`/`MultiUI` fall back to type-a-number
- **Image clipboard paste** — Ctrl+V and Alt+V ✅
- **MultiUI** — broadcast to multiple channels (terminal + Telegram + web), first-response-wins
- **Animated thinking / confirmation indicators** ✅: adaptive refresh loop, debounced invalidation
- Git branch + dirty status, active worktree, pending todos, recent commits shown in (live) context

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has `!`, `@`, `/`, `/btw`, `/copy`, `/plan`, image paste (incl. Alt+V), arrow-key choice UI, MultiUI, animated status. Still missing: Vim mode, voice input, **Shift+Tab permission-mode cycling** (the policy engine now exists — only the cycling shortcut and named-mode UI are missing), extended-thinking toggle, background bash shortcut (Ctrl+B — though `ShellBackground` tool exists), task-list toggle (Ctrl+T), Esc+Esc rewind shortcut, git-history prompt suggestions, transcript viewer, color themes (configurable via `ZRB_LLM_UI_STYLE_*` env vars but no in-TUI theme editor), session branching.

**Effort to close**: **Medium** (3–5 weeks): Shift+Tab cycling over the existing plan/build/yolo policies (~2–3d now that modes exist), background bash shortcut (~2–3d), prompt suggestions (~1wk), Vim mode (2–3wk), in-TUI theme editor (1–2d), voice (2–3wk).

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~55+): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw`, `/tasks`, `/permissions`, `/security-review`, `/theme`, `/voice`, `/agents`, `/rename`, `/schedule`, `/effort`, `/desktop`, `/fast`, `/statusline`, `/goal` (work until conditions met), `/usage` (merged cost+stats), `/code-review` (was `/simplify`; `--fix` applies findings), `/reload-skills`, `/scroll-speed`, `/sandbox` (configure Bash sandboxing), `/workflows` (monitor dynamic workflows), `/deep-research`, `/verify`, `/design-sync`.

Bundled skills as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/deep-research`. Custom skills become slash commands automatically. MCP prompts become `/mcp__<server>__<prompt>`. Argument interpolation (`$ARGUMENTS`, `$N`), dynamic context (`` !`command` ``), `--disable-slash-commands`.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1`; literal-`$` guard removed (v2.27.0)
- Skill-based commands via `get_skill_custom_command()`; skills become slash commands from `name` metadata
- Skill slash-command stubs delegate to core-skill companion files (`/debug`, `/testing`, `/review`, `/refactor`, `/research`)

Built-in slash commands (dispatched via mixins in `src/zrb/llm/ui/base/`): `/compress` / `/compact`, `/attach`, `/exit` `/info` `/help`, `/save` `/load`, `/yolo [tools]`, `/plan`, `>` `/redirect`, `/copy`, `!` `/exec`, `/model` (+ `small` / `multimodal`), `/btw`, `/rewind`. All command tokens configurable via `ZRB_LLM_UI_COMMAND_*` env vars.

**`PRE_COMMAND` / `POST_COMMAND` hooks** ✅ (v2.31.0): hooks fire before/after slash-command dispatch; can block a command and **rewrite command arguments on-the-fly** via the hook result's `command_args`.

**Status**: 🟡 **Partially supported**

**Gap**: Core command infra plus skill-derived commands and command hooks. Newly added since the prior baseline: `/copy`, `/plan`, `/model small|multimodal`. Still missing: ~40 built-in management commands (`/clear`, `/config`, `/diff`, `/branch`, `/export`, `/usage`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/effort`, `/goal`, `/rename`, `/statusline`, `/sandbox`, `/workflows`), MCP prompts as commands, bundled utility skills (`/batch`, `/loop`).

**Effort to close**: **Medium** (3–5 weeks). Most built-in commands wrap functionality that now exists (plan mode, sandbox, snapshots, todos).

---

## 4. Memory System

### Claude Code

**CLAUDE.md files** (human-authored): managed/enterprise, user (`~/.claude/CLAUDE.md`), project (`./CLAUDE.md` / `./.claude/CLAUDE.md`), `CLAUDE.local.md` (gitignored), subdirectory lazy-load, `@import` (max 5 hops), `claudeMdExcludes`, `.claude/rules/` path-scoped (YAML `paths:`), `<!-- comments -->` stripping.

**Auto memory** (Claude-authored): notes in `~/.claude/projects/<project>/memory/MEMORY.md` + topic files; first 200 lines / 25KB loaded at start; `/memory` command, `autoMemoryEnabled` / `autoMemoryDirectory`.

### Zrb

**CLAUDE.md / AGENTS.md / GEMINI.md / README.md / RTK.md auto-loading** (`src/zrb/llm/prompt/claude.py`):
- `project_context` section, default-on
- Search path: `~/.claude/` → filesystem root → … → CWD (all parents + CWD)
- Most-specific occurrence loaded up to `MAX_PROJECT_DOC_CHARS`; others listed for on-demand `Read`
- Per-`(path, mtime)` read caching ✅; RTK.md in search filenames ✅

**Journal system** (analog to auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`); injected via `journal_mandate` section; read/write/search tools; `SearchJournal` tool; auto-approved for journal dir
- **Bidirectional journal graph** ✅: backlinks protocol; **file-relative** link convention (v2.33.1 fixed the doc/lint mismatch — links resolve relative to the containing file, not the journal root)
- **Two-write-kind system** ✅: Insight vs Activity entries; `core-journaling` skill with activity-log template + `journal-lint.py`
- **Granular control** ✅: `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` independent

**Status**: 🟡 **Partially supported**

**Gap**: CLAUDE.md auto-loading + a rich journal system. Missing: `CLAUDE.local.md`, `@import` chaining, `.claude/rules/` path-scoped YAML rules, `claudeMdExcludes`, `<!-- comments -->` stripping, subdirectory lazy-load, `/memory` interactive command, configurable char limit.

**Effort to close**: **Low–Medium** (1–2 weeks): `CLAUDE.local.md` (1d), comment stripping (1d), `@import` (2–3d), `.claude/rules/` (3–5d), `/memory` command (2–3d).

---

## 5. Hooks System

### Claude Code

**~31 hook events** (June 2026, up from 30): `SessionStart`, `Setup`, `SessionEnd`, `UserPromptSubmit`, `UserPromptExpansion`, `Stop`, `StopFailure`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`, `ExitPlanMode`, `SubagentStart`, `SubagentStop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `Notification`, `MessageDisplay`, `PreCompact`, `PostCompact`, `Elicitation`, `ElicitationResult`. (`PermissionDenied` folded into `PostToolUseFailure`.)

**5 handler types**: `command`, `http`, `mcp_tool`, `prompt`, `agent`.

**Capabilities**: universal `continue`/`stopReason`/`suppressOutput`/`systemMessage`/`terminalSequence`; `additionalContext` injection (now also from `Stop`/`SubagentStop`); `decision: block`; PreToolUse `permissionDecision` (allow/deny/ask/defer) + `updatedInput`; PostToolUse `continueOnBlock`; `exec`-form `args: string[]`; conditional `if`, `async`, `once`, `statusMessage`, `CLAUDE_ENV_FILE`, `allowedHttpHookUrls`, `disableAllHooks`, `/hooks` UI, plugin `monitors`.

### Zrb

**11 hook events** (`src/zrb/llm/hook/types.py`) — **unchanged since v2.31.0**:
- `SESSION_START`, `SESSION_END`, `USER_PROMPT_SUBMIT`
- `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE`
- `NOTIFICATION`, `STOP`, `PRE_COMPACT`
- `PRE_COMMAND`, `POST_COMMAND` (Zrb-specific slash-command bracketing; closest CC analog is `UserPromptExpansion`)

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent). No `http`, no `mcp_tool`.

**7 matcher operators**: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`.

**Capabilities**:
- `HookResult` factories: `block`, `allow`, `ask`, `deny`, `with_system_message(replace_response=…)`, `with_additional_context`
- **Tool-input mutation** ✅: `allow(updated_input=…)` merges into `hookSpecificOutput.updatedInput`
- **Command-arg mutation** ✅: `command_args` rewriting for slash commands
- Async/sync with timeouts (`HOOKS_TIMEOUT`, default 30000ms); `ZRB_HOOKS_DEBUG`
- Config tiers (high→low): plugins → user-home (`~/.claude/`, `~/.zrb/`) → project dirs → `CFG.HOOKS_DIRS`; formats JSON / YAML / `.hook.py` (`register(manager)`); Claude-style env vars (`CLAUDE_HOOK_EVENT`, `CLAUDE_CWD`, `CLAUDE_PERMISSION_MODE`, …)
- Skill-frontmatter hook definitions; `add_hook_factory()`; built-in journaling hook fires reminder at `SESSION_END`

**Status**: 🟡 **Partially supported**

**Gap**: 11 of ~31 Claude Code events (~35%). No new events added since v2.31.0, while CC grew. Missing events include: `Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `StopFailure`, `CwdChanged`, `FileChanged`, `ConfigChange`, `PostCompact`, `ExitPlanMode`, `Elicitation`/`ElicitationResult`, `WorktreeCreate`/`WorktreeRemove`, `SubagentStart`/`SubagentStop`, `TaskCreated`/`TaskCompleted`, `TeammateIdle`, `PermissionRequest`. Missing handler types: `http`, `mcp_tool`. Missing features: `CLAUDE_ENV_FILE`, `once`, `statusMessage`, `/hooks` UI, conditional `if`, `allowedHttpHookUrls`, `terminalSequence`.

**Note**: tool-input and command-arg mutation (the most powerful PreToolUse capability) are at parity. The remaining gap is breadth of lifecycle coverage. Several missing events now have natural fire points (`ExitPlanMode`, `WorktreeCreate/Remove`, `SubagentStart/Stop`) since the underlying features exist.

**Effort to close**: **Medium-High** (4–5 weeks): add missing events + fire points (~1.5wk), `http` handler (2–3d), `mcp_tool` handler (2–3d), `if`/`once`/`statusMessage` (2–3d), security settings (2d), `/hooks` UI (2–3d).

---

## 6. MCP (Model Context Protocol)

### Claude Code

Transports: `stdio`, `http`, `sse`. Config scopes (priority): managed → user `~/.claude.json` → local project → `.mcp.json` → `--mcp-config`. `claude mcp add/list/remove/get`, auto-load from `.mcp.json`, live reconnect in `/mcp`, pagination, OAuth refresh-token persistence, MCP prompts as `/mcp__…` commands, MCP tool search (`ToolSearch`, deferred tools), MCP resource tools (`ListMcpResourcesTool`/`ReadMcpResourceTool`), subagent-scoped servers, `allowManagedMcpServersOnly`/`deniedMcpServers`/`enableAllProjectMcpServers`/`allowAllClaudeAiMcps`, `--strict-mcp-config`, `/mcp` UI, registry/marketplace, Channels notifications.

### Zrb

- **Transports**: `stdio` + **`http`/URL** ✅ (via `fastmcp` / `pydantic_ai.mcp.MCPToolset`). No `sse`/`ws`.
- Config: `mcp-config.json` (configurable via `MCP_CONFIG_FILE`), searched home → CWD hierarchy, all matching files merged
- **Env var expansion** with `${VAR}` / `${VAR:-default}` (recursive over command/args/env)
- Retry via `LLM_MCP_MAX_RETRIES` (default 3)
- Loaded via `load_mcp_config()` as a toolset factory in `LLMChatTask`

**Status**: 🟡 **Partially supported**

**Gap**: `stdio` + `http` work. Missing: `sse` transport, `zrb mcp add` CLI, OAuth, MCP prompts → slash commands, MCP tool search / deferred loading (`ToolSearch`), MCP resource tools, subagent-scoped MCP, `/mcp` UI, managed-only policy, registry/marketplace.

**Effort to close**: **Medium** (3–4 weeks): `sse` (3–5d), `zrb mcp add` (2d), prompts→commands (3–4d), resource tools (2–3d), `/mcp` UI (2–3d), OAuth (1–2wk), deferred loading (1wk).

---

## 7. Subagents / Multi-Agent Orchestration

### Claude Code

Declarative subagents via markdown + YAML frontmatter (`.claude/agents/`, `~/.claude/agents/`, plugin `agents/`, `--agents`). Frontmatter: `type`, `description`, `prompt`, `tools`, `disallowedTools`, `model`, `effort`, `maxTurns`, `skills`, `mcpServers`, `isolation` (`worktree`/`none`), `hooks`, `memory`, `background`, `permissionMode`, `color`. Invocation: natural-language auto-delegation, `@-mention`, `--agent`, `/agents`. Foreground/background (Ctrl+B), background dashboard (`claude agents`), subagent compaction, tool allow/deny, `isolation: worktree`, persistent agent memory, `/agents` UI, managed subagents, forked subagents (`CLAUDE_CODE_FORK_SUBAGENT=1`). Built-ins: Explore, Plan, general-purpose, Bash, statusline-setup, Claude Code Guide.

### Zrb

**File-based agents** (`.agent.md` / `AGENT.md` / `.agent.py` / plain `.md` in `agents/`):
- Frontmatter: `name`, `description`, `model`, `tools`, **`inherit_sections`** (🔵 Zrb-specific — sub-agent inherits named PromptManager sections from the main agent)
- Discovery from search dirs (home → project → plugins → builtin); `.md`-only filter
- Built-in agents (`src/zrb/llm_plugin/agents/`): `generalist`, `researcher`, `code-reviewer`

**Delegation tools**:
- `create_delegate_to_agent_tool()` → `DelegateToAgent(agent_name, deliverable, task, non_goals, additional_context)` — single sub-agent, scope-clamped via DELIVERABLE/NON-GOALS/TASK/CONTEXT envelope
- `create_parallel_delegate_tool()` → `DelegateToAgentsParallel(tasks)` — concurrent multi-agent, shared UI lock
- **Background delegation** ✅ **NEW (v2.32.0)**: `DelegateToAgentBackground` + `GetDelegationResult` (`tool/delegate_background.py`) — fire-and-forget detached `asyncio` tasks via a process-lifetime `_BackgroundRegistry`; inherit parent context (UI, yolo, policy, approval channel, agent mode) via ContextVar snapshot; approvals route through the parent UI's confirmation queue (no deadlocks). `BufferedUI` buffers/prefixes background output. Plan-mode parents cannot start one (DELEGATE is denied by the policy gate).
- `SubAgentManager` (nested `manager/` package) with lazy filesystem loading; uses `LLMConfig.resolve_model()`
- **YOLO inheritance** ✅; **tool-guidance propagation** ✅; **permission-policy + sandbox-policy inheritance** ✅ (sub-agents inherit the parent's `current_permission_policy` and `current_sandbox_policy` via ContextVar)

**Status**: 🟡 **Partially supported**

**Gap**: File-based definitions and delegation work, and now include **foreground, parallel, and background** modes with full policy/sandbox inheritance. Still no `@-mention`, no natural-language auto-delegation, no `/agents` UI, no background-session dashboard. Frontmatter lacks `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `effort`, `color`, `disallowedTools`. No persistent agent memory directory, no managed subagents.

**Effort to close**: **High** (4–6 weeks): `@-mention` + typeahead (3–4d), auto-delegation (3–4d), per-agent permissionMode/maxTurns/memory (~1wk — per-agent policy is now expressible via the policy engine), subagent-scoped MCP (~1wk), worktree isolation (1–2wk), `/agents` UI (3–4d).

---

## 8. Agent Teams & Dynamic Workflows

### Claude Code

- **Agent Teams** (now enabled, gated by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`): multiple Claude Code instances cooperating; shared task list with self-coordination; inter-agent `SendMessage`; display modes (in-process cycle or split tmux/iTerm2 via `--teammate-mode`); `TeamCreate`/`TeamDelete`; file locking; task dependencies; hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`); storage `~/.claude/teams/`, `~/.claude/tasks/`.
- **Dynamic Workflows** (v2.1.154+): orchestrate "tens to hundreds of agents in the background"; deterministic JS scripts that fan out / pipeline subagents; structured-output schemas; budget-aware loops; `/workflows` monitoring UI (pause/resume/stop/restart); bundled `/deep-research`; saveable run scripts; up to 16 concurrent / 1000 total agents; triggered by `ultracode` keyword or `/effort ultracode`.

### Zrb

`create_parallel_delegate_tool()` (concurrent multi-agent, aggregated results, shared rate limiter + UI lock, per-agent error handling) plus `DelegateToAgentBackground` / `GetDelegationResult` (fire-and-forget background sub-agents with polling). No persistent team lifecycle, no inter-agent messaging, no shared task list with dependencies, no script-orchestrated fan-out to hundreds of agents, no workflow-monitoring UI.

**Status**: ❌ **Not supported** (parallel + background delegation exist, but not teams or scripted dynamic workflows)

**Gap**: Zrb's delegation is single tool calls returning aggregated/polled results — not persistent coordinated agents nor a deterministic orchestration runtime. Background delegation is a partial building block toward the dynamic-workflow side. Missing: team lifecycle, inter-agent messaging, shared task list with dependencies, tmux display, file locking, `TeamCreate`/`TeamDelete`, JS dynamic-workflow scripting + `/workflows` UI.

**Effort to close**: **Very High** (8–12 weeks) — fundamentally different architecture. Zrb's DAG task engine + parallel/background delegate are partial building blocks for the dynamic-workflow side.

---

## 9. Skills System

### Claude Code

File-based skills (`.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md`). Scopes: managed > personal > project > plugin. Frontmatter: `name`, `description`, `argument-hint`, `invoke` (`user`/`auto`/`never`) / `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context` (fork), `agent`/`subagent`, `hooks`, `paths`, `shell` (`bash`/`powershell`), `hide-from-history`. Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`, `${CLAUDE_EFFORT}`, `{PROJECT_ROOT}`/`{GIT_BRANCH}`/etc. Dynamic context `` !`command` ``, forked subagent context, `paths:` glob activation, monorepo auto-discovery, `disableSkillShellExecution`, plugins auto-load from `.claude/skills/`, `/reload-skills`. Bundled: `/batch`, `/claude-api`, `/debug`, `/loop`, `/code-review`, `/deep-research`. Follows the [Agent Skills](https://agentskills.io) standard.

### Zrb

Comprehensive skill system (`src/zrb/llm/skill/`):
- File types: `.skill.md`, `.skill.py`, `SKILL.md`, `SKILL.py`
- Scopes: default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`)
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, **`hooks`** ✅
- **Companion-file discovery** ✅: `ActivateSkill` returns the skill directory path + grouped companion-file listing
- Lazy scan + content caching; factory-function skills; `get_skill_custom_command()`

**Built-in skills** (`src/zrb/llm_plugin/skills/`, 13 total) — 5-core architecture:
- Core hubs: `core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`
- `core-coding` companions: `languages/` (python, typescript, go, rust, java, ruby, php) + `workflows/` (testing, debug, refactor, review)
- Others: `debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`
- Skill activation policy lives in the centralized Operating Rules section (moved out of the skills catalogue in v2.34.1); domain → core skill mapping (auto-approved, silent, once per session/domain)

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` / `${CLAUDE_EFFORT}` (Zrb has no effort concept), `disallowed-tools`, `paths:` glob activation, `shell` field, `` !`command` `` dynamic injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitutions, `hide-from-history`, bundled utility skills (`/batch`, `/loop`).

**Effort to close**: **Low** (1–2 weeks): `paths`/`shell`/`disallowed-tools` frontmatter (2–3d), `` !`command` `` preprocessing (1–2d), `$CLAUDE_SESSION_ID`/`$CLAUDE_SKILL_DIR` (1d), `/loop` bundled skill (2–3d).

---

## 10. Permission Modes & Tool Approval

### Claude Code

**Permission modes**: `ask` (default), `acceptEdits`, `plan`, `auto` (background safety classifier; now on Bedrock/Vertex/Foundry for Opus 4.7/4.8), `bypassPermissions` (`dontAsk`). Shift+Tab cycling; `--permission-mode`; `defaultMode`. Permission rules `Tool`/`Tool(specifier)`/globs/domains/MCP patterns (`Bash(npm run *)`, `Read(//path/**)`, `WebFetch(domain:…)`, `Agent(Type)`, `Skill(name *)`); evaluation deny > ask > allow; config managed > CLI > local > project > user; **`hard_deny`** unconditional rules; `PermissionRequest` hook.

### Zrb

**Permission policy engine** ✅ **NEW (v2.32.0, ADR-0049–0057)** — `src/zrb/llm/permission/`:
- **Capability tags** (`capability.py`): `READ`, `EDIT`, `EXECUTE`, `NETWORK`, `DELEGATE`, `META`, `UNKNOWN` (safe-by-default). Tools tagged centrally in `common_tools.py`.
- **Rules** (`policy.py`): ordered, **first-match-wins** `Rule(key, action, arg_pattern)` where `key` ∈ {tool name, capability value, `"*"`}, `action` ∈ {`allow`, `ask`, `deny`}, and `arg_pattern` is an `fnmatch` glob over salient args (`path`/`file_path`/`command`/`url`/`agent_name`/…). `PermissionPolicy.decide(tool, capability, args)` resolves: exact tool → capability → `"*"` → None.
- **Plan mode** ✅: `AgentMode` enum (`BUILD`/`PLAN`); `EnterPlanMode`/`ExitPlanMode` tools (tagged `META`); `/plan` toggle command. The preset **`PLAN_MODE_POLICY`** allows READ/META/NETWORK, denies EDIT/EXECUTE/DELEGATE, and asks before `ExitPlanMode` — enforced by `_permission_gate` in `agent/common.py`. `AgentModeState` is a mutable ContextVar-held holder so per-tool asyncio tasks all observe mode changes; `enter/exit_agent_mode_scope` isolates concurrent runs and propagates the final mode back for UI stickiness (v2.33.3 fixed concurrent-run clobbering).
- **YOLO re-expressed as a policy** (`from_yolo`): `True` → `Rule("*", allow)`; `False` → `Rule("*", ask)`; tool-name set → per-tool `allow` + `"*"` ask fallback. Full + selective YOLO propagate to sub-agents.
- **Approval precedence chain** (`permission_policy → tool_policy → yolo`): `deny` stops at the gate; `allow` bypasses lower checks. `DelegateToAgent`'s roster is filtered by the active policy at render time.
- **Auto-approve predicates** (`tool_call/tool_policy/`): `approve_if_path_inside_cwd`, `…inside_journal_dir`, `…inside_skill_or_plugin_dir`, `approve_if_mv_inside_journal_dir`; per-tool validation (`replace_in_file_validation_policy`, `read_file_validation_policy`); **`bash_safe_command_policy`** auto-approves read-only commands and rejects dangerous metacharacters (now including bare `&`, newlines/CR, and `env`-prefixed commands — v2.33.3); denial reasons truncated to 500 chars (v2.34.1).
- `ApprovalChannel` + `MultiplexApprovalChannel` (first-response-wins across channels); override tool args at approval time (`ApprovalResult.override_args`).

**Status**: 🟡 **Partially supported** (major upgrade from the prior baseline's ~35%)

**Gap**: Zrb now has a **real named-mode + rule engine** — `PLAN` (read-only preset), `BUILD`, and YOLO (full/selective) all expressed as `PermissionPolicy`, with capability tags, arg-glob rules, first-match precedence, and a single approval chain. This closes most of the prior "no named permission modes / no rule engine" gap. Still missing vs Claude Code: dedicated `acceptEdits` / `dontAsk` presets, **Shift+Tab cycling** (the modes exist; the cycling shortcut/UI does not), `--permission-mode` CLI flag, domain-pattern rules for web tools (`WebFetch(domain:…)`), `hard_deny` unconditional tier, `PermissionRequest` hook, and admin-managed policy layer.

**Effort to close**: **Low–Medium** (2–3 weeks): `acceptEdits` preset (1d — it's an EDIT-allow policy), `dontAsk` (1d), Shift+Tab cycling over existing policies (2–3d), `--permission-mode` flag (1–2d), domain-pattern arg matching (2–3d), `hard_deny` tier (2d), `PermissionRequest` hook (2d), managed policy layer (depends on §11 JSON settings).

---

## 11. Settings & Configuration System

### Claude Code

4 scopes: managed > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`). JSON schema for autocomplete. `/config` tabbed UI. Global `~/.claude.json`. `--settings` JSON override, `--safe-mode`. Server-managed settings (claude.ai admin, MDM/OS policies, `managed-settings.json` + `managed-settings.d/`).

### Zrb

**Single config source**: `CFG` singleton (`src/zrb/config/`), env vars (prefix `ZRB_`), composed from **16 mixins** under `mixins/`: `foundation`, `web`, `llm_core`, `llm_ui` (+ `llm_ui_commands`/`llm_ui_runtime`/`llm_ui_styles`), `llm_limits`, `llm_content`, `llm_prompt`, `llm_search`, **`llm_sandbox`** (new), `rag`, `internet_search`, `hooks`, `task_runtime`. `CFG.FOO` access stays flat regardless of owning mixin.

- **`EnvField` data descriptor** (v2.32.0): replaced 700+ lines of getter/setter/cast boilerplate; empty env var treated as unset (v2.33.3); `contextvars.py` is the canonical ContextVar index; mixins gained `TYPE_CHECKING` `Protocol` host-classes for static attribute checking
- All magic numbers configurable (timeouts/intervals/sizes/retries)
- **Tool Guidance System**: `ToolGuidance` dataclass, `add_tool_guidance()` / `add_tool_guidance_factory()`; consolidated into `apply_common_tools()` shared across `LLMChatTask`/`LLMTask`/`SubAgentManager`
- **Config-positioned custom prompt sections** (v2.33.0, ADR-0061): a non-built-in name in `include_sections` resolves as a custom section (built-in > registered provider > markdown file); `register_section(name, provider)`; empty/misspelled names log a warning at compose time (v2.34.1)
- **Consolidated model pipeline**: `LLMConfig.resolve_model()` single entry point
- **Per-model capability registry**: `model_capabilities.register("pattern", supports_parallel_tool_calls=…, supports_image_input=…)`

**Status**: 🟡 **Partially supported**

**Gap**: Env-var only — no JSON settings files, no layered scopes, no `/config` UI, no JSON schema, no managed/enterprise policy layer. (The `EnvField` refactor cleaned up the internals but did not add file-based settings.)

**Effort to close**: **Medium** (2–3 weeks): JSON settings loader + scope hierarchy (1wk), merge with env vars (2d), JSON schema (2–3d), `/config` UI (1wk).

---

## 12. Built-in Tools

### Claude Code (~44 tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` |
| `Write` | ✅ `write_file` (post-write LSP/static diagnostics) |
| `Edit` | ✅ `replace_in_file` (fuzzy match + post-edit diagnostics; rejects empty `old_text` — v2.33.3) |
| `Bash` | ✅ `run_bash_command` (actually runs bash now — v2.33.2) + `run_shell_command` (`Shell`, uses `CFG.SHELL`) |
| `PowerShell` | 🟡 `Shell` resolves to `pwsh`/`powershell` on Windows; no dedicated PowerShell tool |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` (ripgrep acceleration) |
| `Agent` (spawn subagent) | 🟡 `DelegateToAgent` / `DelegateToAgentsParallel` / `DelegateToAgentBackground` + `GetDelegationResult` |
| `WebFetch` | ✅ `open_web_page` (`OpenWebPage`) |
| `WebSearch` | ✅ `search_internet` (Google News RSS default, SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | ✅ `AskUserQuestion` — intrinsic auto-approval (v2.33.4, ADR-0062); arrow-key selection UI (v2.34.0) |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full suite incl. `LspRenameSymbol` (8 tools) |
| `Monitor` (stream background events) | 🟡 `MonitorProcess` (poll/kill background shell) — process-scoped, not a general event stream |
| `EnterPlanMode` / `ExitPlanMode` | ✅ **NEW (v2.32.0)** — real plan-mode enforcement via the policy engine (§10) |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking) |
| `TaskCreate/Get/List/Update/Stop` | ✅ `write_todos`/`get_todos`/`update_todo`/`clear_todos` (system-context integration) |
| `CronCreate/Delete/List` | ❌ Not LLM tools (Zrb `Scheduler` exists at task level) |
| `ToolSearch` (deferred MCP tools) | ❌ Not implemented |
| `ListMcpResourcesTool` / `ReadMcpResourceTool` | ❌ Not implemented |
| `SendMessage` / `TeamCreate` / `TeamDelete` | ❌ Teams not implemented |
| `Workflow` (dynamic workflows) | ❌ Not implemented |
| `RemoteTrigger` / `PushNotification` / `ScheduleWakeup` | ❌ Not implemented |
| `Skill` (invoke skills) | ✅ `ActivateSkill` (returns companion files) |

**Background execution** ✅ **NEW (v2.32.0)**: `ShellBackground` (`create_shell_background_tool`) starts a detached process and returns a handle; `MonitorProcess` polls/kills it. Cross-platform via `start_new_session=True` + `psutil` teardown (v2.33.2).

**Additional Zrb tools not in Claude Code** 🔵:
- `RM` (`remove_file`), `MV` (`move_file`)
- `SearchJournal`
- `AnalyzeFile` (AST-based), `AnalyzeCode` (LLM sub-agent analysis)
- `create_rag_from_directory` (ChromaDB embeddings, semantic search)
- `List{Root}Tasks` / `Run{Root}Task` (discover + run any Zrb task as a tool)
- Tool Guidance System (per-tool hints into the system prompt)

**Tool-output truncation backstop** ✅ (v2.32.0): global `LLM_MAX_TOOL_RESULT_CHARS` (default 100k) truncates model-facing `content` (head+tail with re-fetch hint) while preserving structured `return_value` (`agent/truncate.py`).

**Post-write/edit diagnostics** ✅ (`tool/post_write_check.py`): after `write_file`/`replace_in_file`, runs LSP `get_diagnostics()` + static checks (Python `ast.parse` + `pyflakes`); appends a `[DIAGNOSTIC]` block.

**Tool-output truncation backstop** ✅ **NEW (v2.32.0, ADR-0052)**: global `LLM_MAX_TOOL_RESULT_CHARS` cap (default 100k) truncates model-facing content head+tail with a re-fetch hint, preserving structured `return_value`.

**Gap**: Core file/shell/web/worktree/LSP/todo/plan-mode/background tools well-covered. Missing: `NotebookEdit`, `CronCreate/Delete/List`, general `Monitor` event stream, `ToolSearch`, MCP resource tools, `SendMessage`/`TeamCreate`/`TeamDelete`, `Workflow`, `RemoteTrigger`/`PushNotification`/`ScheduleWakeup`, dedicated `PowerShell` tool.

**Effort to close**: **Medium** (2–3 weeks): `NotebookEdit` (3–4d), Cron tools (3–4d, reuse `Scheduler`), `ToolSearch` deferred loading (1wk), MCP resource tools (2–3d).

---

## 13. IDE Integrations

### Claude Code

VS Code extension (panel/sidebar/tab, inline diff accept/reject, `@`-mention, selection context, drag attachments, multi-conversation tabs, plugin UI, auto-install). JetBrains plugin (IntelliJ/PyCharm/WebStorm, interactive diff, Shift+Tab cycling). Desktop app (macOS/Windows, visual diff, side-by-side sessions, computer use, Dispatch, scheduled tasks, `/desktop` handoff, `/design-sync`). `/terminal-setup` GPU toggle.

### Zrb

**Web UI** (FastAPI-based) — browser chat at `http://localhost:21213`, session persistence, model switching, YOLO toggle, JWT auth, SSE streaming, ChatGPT-like layout, browser tool approval (edit args on the fly), HTTP Chat API, Jinja2 templates + local mermaid.js. No VS Code / JetBrains / Desktop integration.

**Status**: ❌ **Not supported** (IDE integrations); 🟡 Web UI is a different paradigm.

**Effort to close**: **Very High** (3–6 months for full parity).

---

## 14. Session Management & Checkpointing

### Claude Code

Checkpointing: auto checkpoint before every edit and per prompt; 30-day retention (`cleanupPeriodDays`); Esc+Esc rewind menu (code+conv / conv-only / code-only); `/rewind`; `/branch`/`/fork`. Sessions per cwd; `--continue`/`-c`, `--resume`/`-r` (by id/name/picker), `--name`/`-n`, `/rename`, `--fork-session`, `--from-pr`, `--no-session-persistence`, `/export`, `/usage` stats, resumable background sessions.

### Zrb

- `FileHistoryManager` → JSON history (`~/.zrb/history/{name}.json`); named sessions via `--session`
- **In-RAM cache with LRU cap** ✅ (v2.34.1): `_MAX_CACHED_CONVERSATIONS = 8` with dirty-entry tracking (fixed an unbounded-memory leak)
- **Backup rotation** ✅: `LLM_HISTORY_BACKUP_RETAIN` (default 3); excludes the live file from rotation (v2.33.3); lexicographic sort
- `NoSaveHistoryManager` for ephemeral sessions; `/load` shows history with icons; fuzzy session search
- **SQLite-backed sessions** via `ChatSessionManager` for the web UI
- **Snapshot / rewind** ✅: `SnapshotManager` (shadow git repos); `/rewind` picker; 3 restore modes; incremental sync + `DEFAULT_IGNORE_DIRS`; `LLM_ENABLE_REWIND`, `LLM_SNAPSHOT_DIR`
- **Escape preserves history** ✅: interrupting a response saves the user message + `[SYSTEM: Response was interrupted]`
- **`/copy` transcript export** ✅ (v2.33.2): clipboard or file; full (untruncated) export mode; `extract_last_response_text()` recovers the last response from replayed history

**Status**: 🟡 **Partially supported**

**Gap**: Rewind/snapshot + ephemeral sessions + interrupt-preserving history + transcript copy/export. Missing: rewind is opt-in (not automatic); no Esc+Esc shortcut; no session branching/forking; no resume-by-id picker; no startup `--name`; no `/export` (but `/copy <file>` partially covers it); no session stats / `/usage`; no `--from-pr`.

**Effort to close**: **Medium** (3–4 weeks): enable rewind by default (1d), Esc+Esc (1–2d), branching (1wk), resume picker (2–3d), `--name` (1d), stats (2–3d).

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, subscription).

### Zrb

🔵 **Zrb-only feature**: FastAPI web UI — browser chat (`http://localhost:21213`), SSE streaming (incl. `todo_progress` events), SQLite session persistence, model switching, YOLO toggle, JWT auth (guest + admin), SSL/TLS, task browsing/execution, REST API (`/api/v1/chat/`), ChatGPT-like layout, `HTTPChatApprovalChannel` (browser tool approval with edit-args), Jinja2 templates + local mermaid.js.

- **Security hardening** ✅ (v2.32.0): JWT `type == "access"` claim enforced; `Secure`+`SameSite=Lax`+`HttpOnly` cookies; constant-time `is_password_match`; `shlex.quote` on task args
- **Chat-API authorization fix** ✅ (v2.33.3): all chat API routes now enforce the `can_access_task` gate (previously authenticated but unauthorized users could reach tool/shell execution)
- **Concurrent-session isolation** ✅: `ChatSessionManager.task_lock`; per-run mode/policy ContextVar isolation (v2.33.3)

**Status**: 🔵 **Zrb advantage** — local web UI not present in the Claude Code CLI.

---

## 16. Auto Mode (Safety Classifier)

### Claude Code

Background classifier reviews each action before execution; sees user messages + tool calls (not Claude's text — anti-injection); default block (download+execute, prod deploys, mass deletes, IAM) / allow (local file ops, deps, read-only HTTP); fallback to prompting after consecutive/total blocks; `autoMode.environment`/`allow`/`soft_deny`/`hard_deny`; `disableAutoMode`; `useAutoModeDuringPlan`; `claude auto-mode defaults`. Now on Bedrock/Vertex/Foundry for Opus 4.7/4.8; detects data exfiltration / bulk repo transfers.

### Zrb

No equivalent LLM-based safety classifier. The **permission policy engine** (§10) + `bash_safe_command_policy` metacharacter rejection + the **sandbox** (§18) provide rule-based and OS-level containment, but there is no model-in-the-loop pre-action classifier that reasons about intent.

**Status**: ❌ **Not supported** (rule-based + sandbox containment exist; no classifier)

**Effort to close**: **High** (4–6 weeks): pre-action classification hook (1wk), default block/allow rules (1wk), configurable rules layered onto the existing policy engine (1wk), fallback counter (2d), integration with permission modes (1wk). The policy engine and sandbox now provide natural enforcement hooks for a classifier's verdicts.

---

## 17. GitHub / CI/CD Integration

### Claude Code

GitHub Actions (`@claude` mention triggers), GitLab CI, GitHub Code Review bot, `/install-github-app`, `--from-pr`, `/pr-comments`, PR status footer, `/security-review`, Slack integration, `/batch` (parallel worktree agents each opening a PR), `claude ultrareview` (non-interactive CI review), `/code-review --fix`.

### Zrb

🔵 **Zrb-only**: task-automation system with Git utilities (`src/zrb/builtin/git`), `run_shell_command` can drive `gh`/`git`, RAG tools, `review` built-in skill (structured code + security review), `git-summary` skill (drafts only; commit/PR on explicit request — v2.34.1). A CI workflow exists for Zrb's own tests (`.github/workflows/test.yml`) but there is no native GitHub app, CI triggers, PR-comment triggers, Slack, or Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**: **High** (4–8 weeks): GitHub Actions template calling `zrb llm chat -p` (1–2d), GitLab template (1d), PR footer via `gh` (1–2d), `/pr-comments` (2–3d), `/security-review` adapt from `review` skill (1d), GitHub webhook → Zrb trigger (2–3wk), Slack bot (2–3wk).

---

## 18. Sandboxing

### Claude Code

OS-level Bash sandboxing (macOS Seatbelt, Linux/WSL bubblewrap+socat): `sandbox.enabled`, `failIfUnavailable`, `excludedCommands`, `allowUnsandboxedCommands`, `filesystem.allowWrite/allowRead/denyWrite/denyRead`, `network.allowedDomains/deniedDomains/httpProxyPort/socksProxyPort/enableWeakerNetworkIsolation`, `bwrapPath`/`socatPath`, `allowManagedReadPathsOnly`/`allowManagedDomainsOnly`, `enableWeakerNestedSandbox`. `/sandbox` command. PowerShell tool default-on for Windows.

### Zrb

🔵 **Opt-in filesystem + OS sandbox** ✅ **NEW (v2.34.0, ADR-0063)** — `src/zrb/llm/sandbox/`:
- **`SandboxPolicy`** (frozen dataclass): `enabled`, `writable_paths` (empty = auto: cwd + `/tmp`), `deny_read_paths` (defaults to credential stores — `~/.ssh`, `~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.gnupg`, `~/.netrc`, `~/.npmrc`, `~/.git-credentials`, `~/Library/Keychains`, …), `os_shell` (`auto`/`off`), `fallback` (`warn`/`deny`), `allow_escape`.
- **Two enforcement layers**:
  1. **Python-level FS gate** (`_sandbox_gate` in `agent/common.py`, right after `_permission_gate`): blocks writes outside writable roots (EDIT/UNKNOWN tools) and reads of credential dirs (all tools) via `check_read()`/`check_write()` (`fs_policy.py`). Windows `normcase` + cross-drive blocking.
  2. **OS-level shell wrapper** for `Shell`/`Bash`/`ShellBackground` (`os_sandbox.py`): macOS `sandbox-exec` + generated SBPL (`seatbelt.py`, last-match-wins: allow-default → deny-write → re-allow writable subpaths → deny-read credential subpaths); Linux `bwrap` (`bwrap.py`, ro-bind root → writable binds → tmpfs/`/dev/null` deny-read masks). Network stays open in v1.
- **Config** (`LLMSandboxMixin`): `ZRB_LLM_SANDBOX_ENABLED` (default `false`), `_OS_SHELL`, `_WRITABLE_PATHS`, `_DENY_READ_PATHS`, `_FALLBACK`, `_ALLOW_ESCAPE`. Where no OS mechanism exists (Windows, Linux without bwrap), `fallback=warn` runs unsandboxed with a visible warning, `deny` refuses — never silent.
- **Escape hatch**: `dangerously_skip_sandbox` arg on shell tools — never auto-approved (always routed to a human), blockable via `ALLOW_ESCAPE=false`, blocked at both layers, emits a `[NOTE]` to the model.
- **Plumbing mirrors permissions**: `LLMTask(sandbox=…)`, `run_agent(sandbox_policy=…)`, `current_sandbox_policy` ContextVar (sub-agent inheritance). Default-off invariant: with no policy set, legacy behavior is reproduced exactly.

**Status**: 🟡 **Partially supported** (major upgrade from the prior baseline's 0%)

**Gap**: Zrb now has FS-level (read+write) sandboxing on macOS (Seatbelt) and Linux (bwrap) plus credential-read denial, with a safe fallback on unsupported platforms. Missing vs Claude Code: **network sandboxing** (allowed/denied domains, HTTP/SOCKS proxy — Zrb keeps network open in v1), `excludedCommands`/`allowUnsandboxedCommands` granularity, managed-read/domain-only enforcement, weaker-isolation toggles for nested/Docker, a `/sandbox` UI command, and a dedicated Windows mechanism.

**Effort to close**: **Medium-High** (3–4 weeks): network isolation via proxy (1–2wk), `excludedCommands` (2–3d), managed policy layer (depends on §11), `/sandbox` command (2–3d), Windows mechanism (1–2wk, platform-dependent).

---

## 19. Remote & Cloud Sessions

### Claude Code

`--remote` (new web session), `--teleport`, `--remote-control`/`--rc`, `claude remote-control`. Control from claude.ai/app; Channels (Telegram/Discord/iMessage/webhooks via MCP channel plugins); Dispatch (phone → Desktop); cloud sessions across devices; Remote Control MCP connectors with OAuth; session color syncs to claude.ai.

### Zrb

🔵 **Zrb-only**: built-in web server (`zrb server start`), REST API, JWT, SSL/TLS. **MultiUI** (broadcast to terminal + Telegram + web; first-response-wins). **MultiplexApprovalChannel** (route approvals to multiple channels). No cloud sessions, Remote Control protocol, Channels plugin system, Dispatch, or multi-device sync.

**Status**: 🟡 **Different approach** — local web server + multi-channel vs cloud infra.

**Gap**: True cloud sessions need cloud infra. Channels partially bridged by MultiUI/MultiplexApprovalChannel + HTTP API but no drop-in Channels system.

**Effort to close**: **Low–Medium** for remote API (web server already provides this); **Medium** (2–3 weeks) for WebSocket remote control + channel plugins; **Very High** for true cloud sessions.

---

## 20. Plugins System

### Claude Code

Install from marketplace or local dir; `--plugin-dir` (`.zip`), `--plugin-url` (archives). Structure: `hooks/hooks.json`, `agents/`, `skills/`, `mcp.json`, `monitors`. `.claude-plugin/plugin.json` manifest; `defaultEnabled`; dependency enforcement. `claude plugin` (incl. `init`/`validate`), `/plugin` UI, `/reload-plugins`. Plugins auto-load from `.claude/skills/`. Marketplaces, `pluginTrustMessage`, channel plugins.

### Zrb

**Skill/Agent/Hook plugin dirs** (closest analog): skills/agents/hooks loaded from multiple dirs; `CFG.LLM_PLUGIN_DIRS` (tilde-expanded); plugin dirs discovered via `.claude-plugin/plugin.json` manifest (`scan_plugin_dirs`); MCP config from multiple locations; `add_hook_factory()`. No formal packaging/marketplace, no `zrb plugin` command, no lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (skills + agents + hooks + MCP, but no packaging/marketplace)

**Effort to close**: **Medium** (3–4 weeks): plugin package format (3–4d), installer `zrb plugin add` (1wk), full plugin-dir scanning (1wk), `/reload-plugins` (2d).

---

## 21. Rate Limiting & Budget Control

### Claude Code

`--max-budget-usd`, `/usage` (merged cost+stats; category breakdown; per-skill/agent/plugin/MCP tracking), rate-limit status in footer, `--fallback-model` (chain up to 3), per-turn token usage.

### Zrb

🔵 **Zrb advantage**: sophisticated rate limiting + retry:
- `LLMLimiter`: requests/min + tokens/min (`ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`); shared across sub-agents; a configured limiter of `0` now blocks correctly (v2.32.0)
- **`fit_context_window` O(n)**: ~46× faster at 320 turns
- **Transient provider error retry**: exponential backoff for HTTP 429/5xx, honors `Retry-After`, caps at `LLM_API_MAX_WAIT`, `LLM_API_MAX_RETRIES`
- Summarizer threshold accounts for system-prompt tokens

Missing: per-session budget cap, `/usage`/`/cost`, cumulative spend, fallback model on overload.

**Status**: 🟡 **Partially supported** (rate limiting + retry exceed Claude Code; budget/cost UI missing)

**Effort to close**: **Low** (3–5 days): cumulative token/cost tracking (2d), `--max-budget` input (1d), `/cost` command (1d), fallback model in CFG (1d).

---

## 22. Platform Support

### Claude Code

macOS (Intel + Apple Silicon, Homebrew, Desktop), Linux (native, Docker), Windows (WSL + native, PowerShell/WinGet, Desktop; WSL image/screenshot paste), iOS/Android (mobile app, Dispatch), browser (claude.ai/code).

### Zrb

- macOS: ✅ Full (incl. Seatbelt sandbox)
- Linux: ✅ Full (incl. bwrap sandbox)
- Windows: 🟡 **Improved** (v2.33.2): cross-platform shell execution — `Shell`/`Bash`/`ShellBackground` converge on shared primitives (`start_new_session=True`, `psutil` teardown, `resolve_shell()`); `get_current_shell()` existence-checks candidates (`pwsh`→`powershell`→`cmd` on Windows); `ShellBackground` no longer crashes on Windows. Caveat: Windows paths are unit-tested with mocks and reasoned from documented behavior but **not yet verified on a real Windows host**. No native installer; sandbox falls back to warn/deny (no Windows OS mechanism).
- Docker: 🔵 images available
- Android/Termux: 🔵 documented (cold-import optimized)
- Browser: 🔵 web UI via `zrb server start`

**Status**: 🟡 Partial for Windows (improved but unverified on hardware); ✅ excellent for macOS/Linux.

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool: post-edit type errors/warnings; `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`; requires language plugin.

### Zrb

🔵 **Zrb advantage**: `LSPManager` singleton (lazy startup, idle timeout); symbol-based API; full suite (`find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, **`rename_symbol`** with dry-run + honest `applied` flag, `list_available_servers`); auto-detect servers (pyright, gopls, tsserver, rust-analyzer…); **`ZRB_LLM_LSP_PREFERRED_SERVERS`** (ordered preference when several match — v2.32.0); per-file project-root cache bounded at 4096 entries (v2.34.1); all LSP tools auto-approved. Post-write/edit diagnostics feed LSP results back into tool results (§12).

**Status**: ✅ **Fully supported** (Zrb arguably broader — `rename_symbol`, workspace symbols, preferred-server ordering).

---

## 24. Context Compaction & Prompt Caching

### Claude Code

Auto-compaction at ~95%; `/compact [instructions]`; `PreCompact`/`PostCompact` hooks (matcher `manual`/`auto`); `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`; original transcript preserved in `.jsonl`. **Prompt caching** on by default (5-min TTL); `DISABLE_PROMPT_CACHING` + per-model toggles; caches CLAUDE.md / project context / long instructions.

### Zrb

Two-layer auto-summarization:
- **Layer 1** — per-message: large tool results summarized in-place
- **Layer 2** — conversational: triggers on message/token thresholds (system-prompt-aware); respects tool call/return pairs; chunk-and-summarize with `<state_snapshot>` consolidation; **parallel chunk summarization** (`asyncio.gather`); `<active_skills>` tracked + restored; summarizers use `LLMConfig.resolve_model()`; retry transient 5xx/429
- Manual: `/compress` / `/compact`
- **`PRE_COMPACT` hook fires** ✅

**Prompt caching** ✅ **NEW (v2.34.2, ADR-0065)**:
- The system prompt is now **byte-stable across turns** so any provider's prefix cache hits. The old `system_context` opened with a second-resolution `- Time:` line + git status / todos / worktree — diverging the prefix every turn (`prompt_cache_hit_tokens: 0`).
- `system_context` was split by lifecycle: it renders only **session-invariant** facts (OS, CWD, project markers, tools, model identity) into the cached system prompt; volatile per-turn state moved to a new **`render_live_context()`** wrapped as `<live-context>…</live-context>` and **appended to the end of the current user turn** (`_append_live_context`) — append-only and frozen into history, so the system-prompt-plus-history prefix stays stable and caches across turns.
- Sub-agents are single-turn, so the block folds back into their inherited system prompt.

**Status**: 🟡 **Partially supported** (compaction) / ✅ **at parity** (prompt caching)

**Gap**: Robust auto-compaction with parallel chunks + skill tracking + `PreCompact`, **plus** byte-stable prompt caching. Missing: `PostCompact` hook, focus instructions for manual compact (`/compress [instructions]`), original transcript preservation in `.jsonl`, per-model cache toggles.

**Effort to close**: **Low** (3–5 days): `PostCompact` event (2d), focus-instructions argument (1–2d).

---

## 25. Vim Mode & Editor Features

### Claude Code

Full Vim mode: NORMAL/INSERT, complete navigation/editing/text-objects, visual mode (`v`/`V`) with operators; `/vim` or `editorMode: "vim"`.

### Zrb

No Vim mode. Standard `prompt_toolkit` input only.

**Status**: ❌ **Not supported**

**Effort to close**: **Medium** (2–3 weeks) — `prompt_toolkit` key-binding layer.

---

## 26. Voice Input

### Claude Code

Push-to-talk dictation (Claude.ai account); `voiceEnabled`, `/voice`, `language`.

### Zrb

No voice input.

**Status**: ❌ **Not supported**

**Effort to close**: **Medium** (2–3 weeks) — `speech_recognition`/`whisper` push-to-talk in TUI.

---

## 27. Diff Viewer

### Claude Code

`/diff` interactive viewer (uncommitted + per-turn; keyboard scrolling, GFM task-list rendering); IDE accept/reject hunks; checkpoint-based diff.

### Zrb

No interactive diff viewer. Changes applied directly; git diff via `run_shell_command`. Tool-approval dialogs show formatted edits.

**Status**: ❌ **Not supported** (in TUI; available via shell)

**Effort to close**: **Low–Medium** (1–2 weeks) — `/diff` via `unified_diff`/`rich`.

---

## 28. Task / Todo System

### Claude Code

`TaskCreate/Update/Get/List/Stop` (background bash tasks, unique IDs, auto-clean, Ctrl+T list); `TodoWrite` (session checklist, disabled by default as of recent versions).

### Zrb

🔵 **Zrb advantage**: `TodoManager` with persistent JSON (`~/.zrb/todos/{session}.json`); states `pending`/`in_progress`/`completed`/`cancelled`; auto IDs, timestamps, progress; `write_todos`/`get_todos`/`update_todo`/`clear_todos`; session isolation + ContextVar wiring; **todo progress card pushed to the active UI** (TUI/StdUI/web SSE `todo_progress`) after every change (v2.32.0, ADR-0057); **pending todos rendered into the live context every turn**. Plus 🔵 the full task-automation framework (`CmdTask`, `LLMTask`, DAG, dependencies, retries, scheduling — with cycle detection added v2.33.3).

**Status**: ✅ **Fully supported** (Zrb advantage on persistence + system-context integration + progress visualization).

---

## 29. Scheduling

### Claude Code

`CronCreate/Delete/List` tools (in-session recurring/one-shot prompts); `ScheduleWakeup` (`/loop` interval); `/schedule` (cloud routines, Pro+); `/loop [interval] <prompt>`; Desktop scheduled tasks; cloud scheduled tasks (persist when machine off).

### Zrb

🔵 **Zrb advantage** at the task level: full `Scheduler` task type (cron-based, with the weekday/day-of-month semantics fixed in v2.33.3) + `CmdTask` scheduling. No `CronCreate/Delete/List` as in-session LLM tools; no `/loop`; no cloud scheduling.

**Status**: 🟡 **Partially supported** (task-level scheduling; not in-session LLM tools; no cloud).

**Effort to close**: **Low** for in-session (2–3d): wrap `Scheduler` as `CronCreate/Delete/List`. **Very High** for cloud scheduling.

---

## 30. Worktree Isolation

### Claude Code

First-class: `--worktree`/`-w`, `--tmux`; `isolation: worktree` in agent frontmatter; `EnterWorktree` (can switch between managed worktrees mid-session) / `ExitWorktree`; `WorktreeCreate`/`WorktreeRemove` hooks; `/batch`; `worktree.symlinkDirectories`/`sparsePaths`/`bgIsolation`/`baseRef`; `.worktreeinclude`.

### Zrb

**Worktree tools** ✅ (`src/zrb/llm/tool/worktree.py`): `enter_worktree(branch_name)`, `exit_worktree(worktree_path, keep_branch)`, `list_worktrees()`; all wrapped in `tool_wrapper`.
- **ContextVar tracking** ✅: `EnterWorktree` sets `active_worktree`; injected into the live context + delegate messages; auto-adds `.zrb/worktree/` to `.gitignore`; **stale-worktree guard** clears the var if the path no longer exists
- Storage: `{git_root}/.zrb/worktree/{branch_name}`

**Status**: 🟡 **Partially supported**

**Gap**: Core tools + ContextVar tracking + stale guard. Missing: `--worktree`/`-w` CLI flag, `--tmux`, `isolation: worktree` in agent defs, `WorktreeCreate`/`WorktreeRemove` hooks, `/batch`, worktree settings (`symlinkDirectories`/`sparsePaths`/`baseRef`), auto-cleanup on session end, `.worktreeinclude`.

**Effort to close**: **Medium** (2–3 weeks): `--worktree` flag (1–2d), `isolation: worktree` in agent defs (~1wk after agent-frontmatter work), worktree hooks (2d), auto-cleanup (2d), `/batch` (2–3wk).

---

## 31. Multimodal & Attachments

### Claude Code

Native image input on vision models; clipboard paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11); drag-as-attachment in IDE; `@`-mention files.

### Zrb

🔵 **Multimodal attachment pipeline** ✅ (`src/zrb/llm/util/`):
- `LLM_MULTIMODAL_MODEL` — designate a vision model to describe attachments when the main model is text-only
- `LLM_MAX_IMAGE_DIMENSION` (1568) + `LLM_IMAGE_JPEG_QUALITY` (85): pasted/`/attach`-ed images auto-scaled; opaque→JPEG, alpha→PNG
- `runner._apply_multimodal_fallback`: if the main model can't consume an image/audio, the multimodal model describes it and substitutes text; otherwise dropped with a `⚠️ Dropped <modality>` warning (never silently sent to a rejecting provider)
- Audio: describe/transcribe fallback. Video: kept for Gemini-class, dropped-with-warning otherwise
- Per-model capability registry (`model_capabilities`) drives support detection
- Clipboard paste via Ctrl+V and Alt+V; `/model multimodal <name>` sets the vision model at runtime (v2.32.0)

**Status**: ✅ **Fully supported / 🔵 advantage** — the text-only-model fallback (describe-then-substitute) and explicit drop-with-warning are beyond Claude Code's image handling, important for Zrb's multi-provider story.

---

## 32. Provider Resilience & Multi-Model

### Claude Code

Single primary provider (Anthropic) with `--fallback-model` chain on overload; Bedrock/Vertex/Foundry deployments; opaque-error handling abstracted by the platform.

### Zrb

🔵 **Major Zrb advantage** — multi-provider robustness:
- Any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock, …)
- **4-stage history sanitization** (`sanitize_history`): filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles
- **Provider-specific 400 recovery**: DeepSeek `reasoning_content` rejection → `strip_thinking_parts` retry; GLM empty `ValidationException` retry; **generic opaque-400** → `strip_to_text_only()` collapse + single retry (provider-agnostic); Bedrock nil-content → `"."` placeholder; invalid-tool-call detection requires entity + problem keyword
- **Empty-completion guard** (v2.32.0, ADR-0059): regenerates blank / leaked `"(tool call)"` completions instead of surfacing them; `filter_nil_content` no longer injects the placeholder into tool-call-only turns
- **Deferred-tool summarizer death-spiral fix** (ADR-0058); `create_agent(resolve_model=False)` stops model-callback double-firing; OpenAI `content:null` patch verifies its target and warns on pydantic-ai drift
- **Parallel-tool-call guard**: `model_capabilities` injects `parallel_tool_calls=False` for known-malforming models
- `request_limit=None` overrides pydantic-ai's 50-request tool-loop cap; `create_agent` uses `tool_retries`

**Status**: 🔵 **Zrb advantage** — far broader provider coverage and resilience than the Claude Code CLI exposes.

---

## 33. Side Questions (`/btw`)

### Claude Code

`/btw <question>` — answered but the Q&A pair is dropped from the transcript; doesn't interrupt in-progress work.

### Zrb

✅ **Fully implemented** (`_handle_btw_command`): `/btw <question>` answered in a temporary context (runs in parallel), not appended to history; shares conversation context for relevant answers.

**Status**: ✅ **Fully supported**

---

## 34. Channels & Remote Control

### Claude Code

Remote Control (control a session from claude.ai/app; `--remote-control`/`--rc`, `claude remote-control`; MCP connectors with OAuth). Channels (push external events via MCP channel plugins: Telegram/Discord/iMessage/webhooks; `--channels`, `channelsEnabled`, `allowedChannelPlugins`). Dispatch (phone → Desktop). `CLAUDE_CODE_REMOTE` env var.

### Zrb

🔵 **Zrb-only existing**: MultiUI (CLI + Telegram + web simultaneously; broadcast output; first-response-wins input); MultiplexApprovalChannel (route approvals to multiple channels); HTTP Chat API (external POST to `/api/v1/chat/sessions/{id}/messages` pushes messages into an active session — now authorization-gated, v2.33.3). No Remote Control protocol, native Channels plugin system, or Dispatch.

**Status**: 🟡 **Partially covered** (MultiUI + HTTP API cover core use cases; no standardized protocol).

**Effort to close**: **Medium** (2–3 weeks): WebSocket remote control (1wk), webhook endpoint refinement (partial via HTTP API), Telegram/Discord channel plugins (2wk).

---

## 35. Summary & Roadmap

### Changes Since v2.31.0 (the prior analysis baseline)

#### Zrb improvements (v2.32.0 → v2.34.3)

| Feature | Old Status | New Status | Details |
|---------|-----------|-----------|---------|
| Permission policy engine | 🟡 ~35% (YOLO only) | 🟡 strong | Capability tags + first-match rules + arg globs + single approval chain (v2.32.0, ADR-0049–0057) |
| Plan mode | ❌ | ✅ | `EnterPlanMode`/`ExitPlanMode`, `PLAN`/`BUILD`, `PLAN_MODE_POLICY`, `/plan` toggle, gate-enforced (v2.32.0) |
| Filesystem/OS sandbox | ❌ 0% | 🟡 | Python FS gate + Seatbelt/bwrap OS wrapper + credential deny-read + escape hatch (v2.34.0, ADR-0063) |
| Prompt caching | ❌ | ✅ | Byte-stable system prompt + `<live-context>` split (v2.34.2, ADR-0065) |
| Background delegation | ❌ | ✅ | `DelegateToAgentBackground` + `GetDelegationResult` (v2.32.0) |
| Background shell | ❌ | ✅ | `ShellBackground` + `MonitorProcess`, cross-platform (v2.32.0, v2.33.2) |
| Tool-output truncation backstop | ❌ | ✅ | `LLM_MAX_TOOL_RESULT_CHARS` (v2.32.0) |
| `/copy` + clipboard `/redirect` | ❌ | ✅ | Transcript/response to clipboard (OSC 52) or file (v2.33.2) |
| Arrow-key `AskUserQuestion` UI | type-a-number | ✅ | In-layout Float selection widget (v2.34.0); intrinsic auto-approval (v2.33.4) |
| `/model small`/`multimodal` | ❌ | ✅ | Set summarizer / vision model at runtime (v2.32.0) |
| Cross-platform shell | POSIX-only | 🟡 | Windows-safe `Shell`/`Bash`/`ShellBackground` (v2.33.2; unverified on real Windows) |
| Config-positioned custom sections | per-section | ✅ | `register_section`, markdown-file fallback (v2.33.0, ADR-0061) |
| `EnvField` config descriptor | boilerplate | ✅ | −700 lines; empty-env-as-unset (v2.32.0) |
| ULID tasks | ❌ | 🔵 | `zrb ulid generate/validate` (v2.33.1) |
| Memory-leak / cache-bound fixes | — | ✅ | History LRU (8), LSP root cache (4096) (v2.34.1) |
| Web auth + chat-API authz hardening | partial | ✅ | JWT access-claim, secure cookies, `can_access_task` gate (v2.32.0, v2.33.3) |
| Bug-fix sweep | — | ✅ | bash-injection vectors, empty `old_text`, cron weekday, circular task deps, SSH injection, concurrent-mode clobbering (v2.33.3) |

#### New Claude Code features since the prior baseline

| Feature | Impact on Gap |
|---------|--------------|
| Hook events 30 → ~31 (`MessageDisplay`, `ExitPlanMode`, …) | Gap widened (§5 — Zrb stayed at 11) |
| Dynamic Workflows (orchestrate 100s of agents) + `/workflows` + `/deep-research` | Large gap persists (§8) |
| Agent Teams enabled (`SendMessage`, shared tasks, tmux) | Large gap persists (§8) |
| `/goal`, `/usage`, `/fast`, `/sandbox`, `ultracode` effort | Gaps (§3, §21, §18, §13) |
| Fable 5, Opus 4.8 default, fast mode, fallback chains | Minor (§21, §32) |
| Network sandboxing + managed sandbox policies | Gap remains within §18 |
| Prompt caching default-on | Zrb reached parity (§24) |

### Overall Coverage Assessment

| Category | Status | Change vs v2.31.0 |
|----------|--------|-----------------|
| CLI Flags | 🟡 ~20% | = (infra grew, surface didn't; CC added more) |
| Interactive TUI | 🟡 ~70% | ↑ (/copy, arrow-key choice, /plan) |
| Slash Commands | 🟡 ~47% | ↑ (/copy, /plan, /model subcommands) |
| Memory/CLAUDE.md | 🟡 ~72% | = |
| Hooks | 🟡 ~35% (11/~31) | ↓ (Zrb flat, CC grew) |
| MCP | 🟡 ~55% | = |
| Subagents | 🟡 ~55% | ↑ (background delegation, policy/sandbox inheritance) |
| Agent Teams & Dynamic Workflows | ❌ ~5% | ↓ (CC shipped both; Zrb only background delegate) |
| Skills | ✅ ~85% | = |
| Permission Modes | 🟡 ~65% | ↑↑ (full policy engine + plan mode) |
| Settings System | 🟡 ~35% | ↑ (EnvField, custom sections) |
| Built-in Tools | 🟡 ~78% | ↑ (plan-mode/background tools) |
| IDE Integrations | ❌ 0% | = |
| Session/Checkpoint | 🟡 ~62% | ↑ (/copy export, LRU cache, backup fix) |
| Web UI | 🔵 advantage | ↑ (security hardening) |
| Auto Mode | ❌ ~10% | ↑ (policy + sandbox provide enforcement substrate) |
| GitHub/CI Integration | ❌ ~5% | = |
| Sandboxing | 🟡 ~55% | ↑↑ (FS+OS sandbox from 0%) |
| Remote/Cloud | 🟡 different | = |
| Plugins | 🟡 ~38% | = |
| Rate Limiting | 🟡 ~78% | = |
| Platform Support | 🟡 ~84% | ↑ (cross-platform shell) |
| LSP | ✅ advantage | = |
| Context Compaction & Prompt Caching | ✅ ~90% | ↑↑ (prompt caching parity) |
| Vim Mode | ❌ 0% | = |
| Voice Input | ❌ 0% | = |
| Diff Viewer | ❌ 0% | = |
| Task/Todo | ✅ advantage | ↑ (progress visualization) |
| Scheduling | 🟡 ~40% | = |
| Worktree Isolation | 🟡 ~65% | = |
| Multimodal & Attachments | ✅ / 🔵 advantage | = |
| Provider Resilience & Multi-Model | 🔵 advantage | ↑ (empty-completion guard, summarizer fixes) |
| Side Questions (`/btw`) | ✅ 100% | = |
| Channels & Remote Control | 🟡 ~25% | = |

### Zrb Unique Advantages (Superset Features)

1. 🔵 **Multi-model / any provider** via Pydantic AI
2. 🔵 **Provider resilience layer**: 4-stage sanitization, provider-agnostic opaque-400 recovery, empty-completion guard, per-model parallel-tool-call guard
3. 🔵 **Multimodal fallback pipeline**: describe-then-substitute for text-only models, image auto-scaling, audio transcribe, explicit drop-with-warning
4. 🔵 **Local Web UI** with hardened auth, streaming, task management, browser tool approval (edit-args)
5. 🔵 **HTTP Chat API** (`/api/v1/chat/`, authorization-gated) for programmatic sessions/messages
6. 🔵 **MultiUI + MultiplexApprovalChannel**: broadcast to terminal + Telegram + web; first-response-wins
7. 🔵 **Task Automation Framework**: CmdTask, LLMTask, Scaffolder, Scheduler, HttpCheck, TcpCheck — a DAG engine (with cycle detection)
8. 🔵 **Run Zrb tasks as LLM tools**: the agent can discover and execute any project task
9. 🔵 **AST analysis + RAG**: `AnalyzeFile`/`AnalyzeCode`, `create_rag_from_directory`
10. 🔵 **Richer LSP**: `rename_symbol` (dry-run), workspace symbols, preferred-server ordering, post-write diagnostics
11. 🔵 **Persistent todos with live-context injection + progress cards**
12. 🔵 **Bidirectional journal graph**: backlinks protocol (file-relative), two-write-kind system, `journal-lint.py`
13. 🔵 **Tool Guidance System**: declarative per-tool hints; propagated to sub-agents
14. 🔵 **Per-model capability registry**: user-extensible image/audio/video/parallel-tool flags
15. 🔵 **Consolidated model pipeline**: single `LLMConfig.resolve_model()`
16. 🔵 **Capability-tagged permission engine + plan mode**: READ/EDIT/EXECUTE/NETWORK/DELEGATE/META tags with first-match rules, expressible per-tool and per-arg
17. 🔵 **Byte-stable prompt + `<live-context>` split** for cross-turn prefix caching (ADR-0065)
18. 🔵 **Fully configurable limits**: all timeouts/intervals/retries/sizes as env vars
19. 🔵 **Rate limiting + transient retry**: req/min + tok/min, O(n) context fit, backoff + `Retry-After`
20. 🔵 **Self-hosted, no subscription**: bring your own API key
21. 🔵 **Android/Termux support** with cold-import optimization
22. 🔵 **Flexible web search**: Google News RSS (zero-setup) + SearXNG/Brave/SerpAPI
23. 🔵 **White-labeling**: build custom CLIs via Zrb's framework
24. 🔵 **Selective YOLO** with sub-agent inheritance
25. 🔵 **Inherit-sections sub-agents**

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (3–5 weeks)

1. **Surface named permission modes** — `acceptEdits` / `dontAsk` presets + Shift+Tab cycling over the existing policy engine + `--permission-mode` flag (1–1.5wk; the engine already exists)
2. **Extended CLI flags**: `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--worktree`, `--sandbox` toggle (1wk)
3. **JSON settings files** with scope hierarchy (user/project/local) (1wk)
4. **`/usage`/`/cost` + budget tracking** (3–5d)
5. **More hook events**: `PostCompact`, `ExitPlanMode`, `SubagentStart/Stop`, `WorktreeCreate/Remove` (fire points now exist) (3–4d)
6. **Additional built-in slash commands**: `/clear`, `/config`, `/export`, `/permissions`, `/diff`, `/sandbox` (1wk)
7. **`/compress [focus]`** focus instructions (1–2d)
8. **MCP prompts as slash commands** (3d)
9. **CLAUDE.local.md** + `@import` (3–4d)
10. **Cron tools** (`CronCreate/Delete/List`) wrapping `Scheduler` (3d)

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

11. **Network sandboxing** (proxy-based allowed/denied domains) + `excludedCommands` (2–3wk)
12. **Full worktree isolation** — `isolation: worktree` in agent defs + `/batch` (2–3wk)
13. **`@-mention` + auto-delegation** for file-based agents + `/agents` UI (2–3wk)
14. **Per-agent frontmatter**: `permissionMode` (via policy engine), `maxTurns`, `mcpServers`, `hooks`, `memory` (1–2wk)
15. **GitHub CI/CD templates** + `/security-review` from `review` skill (1wk)
16. **Plugin packaging format** + `zrb plugin add` (1–2wk)
17. **MCP `sse` + OAuth + resource tools + `ToolSearch`** (2–3wk)
18. **`http` + `mcp_tool` hook handler types** (1wk)
19. **Skill enhancements**: `paths`, `shell`, `disallowed-tools`, `` !`command` `` injection (1wk)
20. **`NotebookEdit` tool** (3–4d)

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

21. **Auto mode safety classifier** layered onto the policy engine + sandbox (4–6wk)
22. **Dynamic workflows runtime** (script-orchestrated fan-out; background delegation is a building block) (6–10wk)
23. **Agent Teams** — persistent coordinated agents + `SendMessage` (2–3mo)
24. **IDE integrations** (VS Code, JetBrains) (3–4mo)
25. **Vim mode** in TUI (2–3wk)
26. **Voice input** (2–3wk)
27. **Desktop app** (Electron/Tauri) (4–6wk)
28. **Cloud scheduled tasks / sessions** (requires cloud infra)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~4–6 weeks, 1–2 developers (shorter than the prior estimate — permission modes and sandbox, previously Phase-3 net-new architecture, now exist)
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~7–11 months with 2–3 developers

> **Net assessment**: From v2.31.0 → v2.34.3 Zrb closed two of its largest structural gaps. **Permission modes** went from "YOLO only, no named modes" to a full capability-tagged policy engine with a read-only **plan mode**, first-match arg-glob rules, and a single approval-precedence chain (ADR-0049–0057). **Sandboxing** went from 0% to an opt-in two-layer FS+OS sandbox (Python gate + Seatbelt/bwrap) with credential-read denial and a safe fallback (ADR-0063). Zrb also reached **prompt-caching parity** by splitting the byte-stable system prompt from a per-turn `<live-context>` block (ADR-0065), gained **background delegation and background shell**, `/copy` transcript export, an arrow-key `AskUserQuestion` UI, cross-platform shell execution, and a substantial security/bug-fix sweep. Meanwhile Claude Code widened its lead on **orchestration breadth** — Agent Teams are now enabled and Dynamic Workflows orchestrate hundreds of agents with a `/workflows` monitoring UI and bundled `/deep-research`; it also added `/goal`, `/usage`, `/fast`, `/sandbox`, the `ultracode` effort tier, Fable 5 / Opus 4.8, and network-level sandbox isolation. The remaining structural gaps are now concentrated in: agent teams / dynamic workflows, IDE & desktop integration, the auto-mode classifier, cloud sessions, network sandboxing, and the (large but mostly mechanical) CLI-flag and built-in-command surface. Zrb's 25 unique advantages — multi-model, provider resilience, local web UI, multi-channel, task automation, RAG, richer LSP, the policy engine, prompt caching — keep it a genuine superset in the self-hosted / multi-provider / automation dimensions, while Claude Code remains ahead on managed-cloud orchestration and IDE depth.

---

*Analysis updated: 2026-06-13 | Claude Code docs: code.claude.com/docs (surveyed June 2026) | Zrb version: 2.34.3*
