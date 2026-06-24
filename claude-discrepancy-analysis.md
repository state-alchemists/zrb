# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs) and the public CHANGELOG, fetched June 2026. Zrb features sourced from full codebase exploration of `src/zrb/` plus the changelog (`docs/changelog.md`, `docs/changelog-v2/`).
>
> **Zrb version**: 2.40.1 (June 23, 2026)
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
24. [Context Compaction](#24-context-compaction)
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

Comprehensive CLI with 70+ flags across 30+ subcommands. Highlights (May 2026):
- `claude "query"`, `-p`/`--print`, `-c`/`--continue`, `-r`/`--resume`, `-n`/`--name`
- `--model`, `--permission-mode`, `--dangerously-skip-permissions`, `--enable-auto-mode`
- `--max-turns`, `--max-budget-usd`, `--output-format` (`text`/`json`/`stream-json`), `--input-format`
- `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`
- `--mcp-config`, `--strict-mcp-config`, `--agent`, `--agents`
- `--worktree`/`-w`, `--tmux`, `--effort` (low/medium/high/xhigh/max), `--fork-session`, `--fallback-model`
- `--bare`, `--no-session-persistence`, `--json-schema`, `--include-partial-messages`, `--include-hook-events`
- `--channels`, `--chrome`/`--no-chrome`, `--remote`, `--remote-control`/`--rc`, `--teleport`, `--teammate-mode`
- `--plugin-dir` (now accepts `.zip`), **`--plugin-url`** (fetch plugins from archives), `--from-pr`
- **`--safe-mode`** / `CLAUDE_CODE_SAFE_MODE` (v2.1.169 — start with ALL customizations disabled: CLAUDE.md, plugins, skills, hooks, MCP), `--fallback-model` now applies to interactive sessions too
- Subcommands: `claude agents` (now `--json --all`, `id`/`state`/`waitingFor` fields, `--agent <name>`, `--cwd`), `claude auto-mode defaults`, `claude auth`, `claude mcp`, `claude plugin` (now `init`/`validate`/`list`), `claude setup-token`, `claude update`, `claude ultrareview` (non-interactive code review for CI), `claude remote-control`

### Zrb

`zrb llm chat` with 6 CLI inputs (`src/zrb/builtin/llm/chat.py`):
- `--message` / `-m`
- `--model`
- `--session` — conversation session name
- `--yolo` — bypass confirmations; full (`true`) or selective (`--yolo "Write,Edit"`)
- `--attach` — file attachments (now multimodal-aware, §31)
- `--interactive` — toggle interactive mode

**Status**: 🟡 **Partially supported**

**Gap**: Still 6 inputs against Claude Code's 70+ flags. Critical missing: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--plugin-dir`, `--remote-control`, `--channels`, `--safe-mode`. The underlying infra (rate limiting, session management, YOLO, snapshots, permission policies, sandbox) exists and is now reachable programmatically (`LLMChatTask(permissions=…, sandbox=…)`, `ZRB_LLM_SANDBOX_ENABLED`, Shift+Tab plan mode) and inspectable (`zrb config explain`) — but there is still no per-invocation CLI switch for plan/permission-mode or sandbox toggles.

**Effort to close**: **Medium** (2–3 weeks) — map each flag to existing Zrb config and expose as CLI inputs on `LLMChatTask`.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich interactive TUI:
- Vim mode with NORMAL/INSERT/navigation; **visual mode (`v`/`V`) with operators** (new); `/vim` or `editorMode`
- Voice input (push-to-talk)
- `!` bash prefix, `@` file mention with autocomplete, `/` command palette
- Multiline input (Shift+Enter, Option+Enter, `\`+Enter, Ctrl+J)
- Shortcuts: Ctrl+C/D/L/O/R, Ctrl+B (background bash), Ctrl+T (task list), Esc+Esc (rewind menu), Shift+Tab/Alt+M (permission modes), Option+P/T/O (model / thinking / fast mode)
- `/btw` side questions, image paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11 — new)
- Prompt suggestions from git history, transcript viewer, color themes (custom theme editing — new), configurable status line
- Terminal progress bar, spinner tips, reduced motion, deep links, **`/scroll-speed`** (new), `CLAUDE_CODE_HIDE_CWD` (new)
- **`/cd`** — change working directory mid-session without breaking prompt cache (v2.1.169); autocomplete click-to-fill; Remote Control footer pill (v2.1.162)

### Zrb

`prompt_toolkit`-based TUI (`src/zrb/llm/ui/`):
- Multi-line input (trailing `\` continuation, Ctrl+J newline)
- Command history with reverse search
- **`!` bash prefix** — `! cmd` / `/exec cmd` runs shell and injects output
- **`@` file mention** with autocomplete (`completion.py`)
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach`, `/model` (with `small <name>` / `multimodal <name>` subcommands + tab-completion), `/yolo` (full + selective), `/plan` (toggle plan mode), `/save` / `/load`, `/compress` / `/compact`, `>` / `/redirect` (bare → clipboard), `/copy` (transcript → clipboard or file, OSC 52 fallback for SSH/tmux), `/btw`, `/rewind`
- **Image clipboard paste** — Ctrl+V and **Alt+V** ✅
- **Arrow-key selection UI for `AskUserQuestion`** ✅ (ADR-0064): ↑/↓ + Enter, Space toggle for multi-select, synthetic "Type my own answer…" row; in-layout `Float` widget; non-terminal UIs fall back to numbered text via the optional `ask_user_choice` protocol method
- **Shift+Tab interaction-mode cycling** ✅ **(ADR-0075)**: `normal → auto-accept-edits → plan → normal`, mirroring Claude Code; status-bar **mode badge** (`normal`/`accept-edits`/`plan`, plus `yolo`/`custom-yolo`) + `shift+tab to cycle` hint. `Tab` also cycles (Termux can't distinguish the two bytes). Auto-accept-edits = selective YOLO over `Write`/`Edit` (file writes auto-approve; shell/delegation/fetch still prompt)
- **Configurable color themes** ✅ **(ADR-0077)**: a semantic CLI color layer (`stylize_warning`/`error`/`muted`/…) + TUI styles (mode badges, info-bar indicators, choice-widget bg) are all `ZRB_CLI_COLOR_*` / `ZRB_CLI_STYLE_*` / `ZRB_LLM_UI_STYLE_*` env-backed and take effect without restart; `examples/themes/` ships dark/light/high-contrast scripts
- **MultiUI** — broadcast to multiple channels (terminal + Telegram + web), first-response-wins
- **Animated thinking / confirmation indicators** ✅: adaptive refresh loop, debounced invalidation (33–100× fewer redraws); the tool-arg spinner is throttled to ~10×/sec
- **Todo progress cards** ✅ (ADR-0057): styled progress card pushed to the active UI (TUI, StdUI, web SSE) after every todo change
- **`/help` keyboard-shortcut reference + width-guarded welcome banner** ✅
- Git branch + dirty status, active worktree, pending todos, recent commits all surfaced via the per-turn `<live-context>` block (ADR-0065)

**Status**: 🟡 **Partially supported**

**Gap**: Zrb now has `!`, `@`, `/`, `/btw`, image paste (incl. Alt+V), MultiUI, animated status, arrow-key question widgets, todo cards, transcript copy/export, **Shift+Tab mode cycling**, and **configurable color themes** — three formerly-missing items now closed. Background shell exists via `Shell`/`Bash` `background=True` (§12) but there is no Ctrl+B-style UI affordance. Still missing: Vim mode, voice input, extended-thinking toggle, task-list toggle (Ctrl+T), Esc+Esc rewind shortcut, git-history prompt suggestions, transcript viewer, configurable status line content, session branching, `/cd` mid-session cwd change.

**Effort to close**: **Medium** (3–5 weeks): prompt suggestions (~1wk), Vim mode (2–3wk), voice (2–3wk).

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~57+): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw` (now with "c to copy" raw markdown), `/tasks`, `/permissions`, `/security-review`, `/theme`, `/voice`, `/agents`, `/rename`, `/schedule`, `/effort`, `/desktop`, `/fast`, `/statusline`, `/goal` (work until conditions met), `/usage` (merged `/cost`+`/stats`), `/code-review` (was `/simplify`; `--fix` applies findings), `/reload-skills`, `/scroll-speed`, **`/cd`** (mid-session cwd change — new v2.1.169), **`/plugin list`** (with `--enabled`/`--disabled` — new v2.1.163), `/workflows`.

Bundled skills as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`→`/code-review`. Custom skills become slash commands automatically. MCP prompts become `/mcp__<server>__<prompt>`. Argument interpolation (`$ARGUMENTS`, `$N`), dynamic context (`` !`command` ``), `--disable-slash-commands`.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1`; literal-`$` guard removed (v2.27.0) so regex/price prompts pass args correctly
- Skill-based commands via `get_skill_custom_command()`; skills become slash commands from `name` metadata
- Skill slash-command stubs delegate to core-skill companion files (`/debug`, `/testing`, `/review`, `/refactor`, `/research`)

Built-in slash commands: `/compress` / `/compact`, `/attach`, `/q` `/bye` `/quit` `/exit`, `/info` `/help`, `/save` `/load`, `/yolo [tools]`, `/plan` ✅ **NEW (v2.32.0)**, `>` `/redirect` (bare → clipboard), `/copy [file]` ✅ **NEW (v2.33.2)**, `!` `/exec`, `/model [small|multimodal] <name>`, `/btw`, `/rewind`. Command names are configurable via `ZRB_LLM_UI_COMMAND_*` env vars.

**`PRE_COMMAND` / `POST_COMMAND` hooks** ✅ **NEW (v2.31.0)**: hooks fire before/after slash-command dispatch; can block a command, and can **rewrite command arguments on-the-fly** (e.g. `/model opus` → `/model sonnet`) via the hook result's `command_args` (`commands_mixin.py::_command_arg_override`).

**Status**: 🟡 **Partially supported**

**Gap**: Core command infra plus skill-derived commands and command hooks; `/plan` and `/copy` (≈`/export`) newly closed. Missing: ~38 built-in management commands (`/clear`, `/config`, `/diff`, `/branch`, `/usage`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/effort`, `/goal`, `/rename`, `/statusline`, `/cd`), MCP prompts as commands, bundled utility skills (`/batch`, `/loop`).

**Effort to close**: **Medium** (3–5 weeks). Most built-in commands wrap existing functionality.

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
- **Per-`(path, mtime)` read caching** ✅ (v2.28.0) — per-turn re-reads cost only a stat; `break`→`continue` bug fixed so all doc files load
- **RTK.md added to search filenames** ✅ (v2.27.0)

**Journal system** (analog to auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`); injected via `journal_mandate` section; read/write/search tools; `SearchJournal` tool (v2.24.0); auto-approved for journal dir
- **Bidirectional journal graph** ✅: backlinks protocol, every forward link needs a backlink
- **Two-write-kind system** ✅ (v2.27.0): Insight vs Activity entries; `core-journaling` skill with activity-log template + `journal-lint.py` (backlink validation / orphan detection)
- **Granular control** ✅: `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` (system-prompt section) and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` (end-of-session reminder, default `off`) independent

**Status**: 🟡 **Partially supported**

**Gap**: CLAUDE.md auto-loading + a rich journal system. Missing: `CLAUDE.local.md`, `@import` chaining, `.claude/rules/` path-scoped YAML rules, `claudeMdExcludes`, `<!-- comments -->` stripping, subdirectory lazy-load, `/memory` interactive command, configurable char limit.

**Effort to close**: **Low–Medium** (1–2 weeks): `CLAUDE.local.md` (1d), comment stripping (1d), `@import` (2–3d), `.claude/rules/` (3–5d), `/memory` command (2–3d).

---

## 5. Hooks System

### Claude Code

**30 hook events** (May 2026, up from 27): `SessionStart`, `Setup`, `UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `MessageDisplay`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `Stop`, `StopFailure`, `TeammateIdle`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `PreCompact`, `PostCompact`, `Elicitation`, `ElicitationResult`, `SessionEnd`.

**5 handler types**: `command`, `http`, `mcp_tool`, `prompt`, `agent`.

**Capabilities**: universal `continue`/`stopReason`/`suppressOutput`/`systemMessage`/`terminalSequence`; `additionalContext` injection; `decision: block`; PreToolUse `permissionDecision` (allow/deny/ask/defer) + `updatedInput`; PermissionRequest `behavior` + `permissionRule`; PermissionDenied `retry`; MessageDisplay `displayContent`; SessionStart `reloadSkills`/`sessionTitle`/`watchPaths`/`initialUserMessage`; **Stop/SubagentStop can return `hookSpecificOutput.additionalContext`** to feed Claude feedback and keep the turn going (new v2.1.163). Conditional `if`, `async`, `once`, `statusMessage`, `CLAUDE_ENV_FILE`, `allowedHttpHookUrls`, `disableAllHooks`, `/hooks` UI, plugin `monitors`; self-hosted runner `post-session` lifecycle hook (v2.1.169).

### Zrb

**16 hook events** (`src/zrb/llm/hook/types.py`):
- `SESSION_START` (carries `source` = startup/resume), `SESSION_END` (now **terminal** — fires once at chat teardown, ADR-0074), `USER_PROMPT_SUBMIT` (carries `prompt`; can block the turn)
- `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE` (all carry Claude-standard `tool_name`/`tool_input`/`tool_response`)
- `PERMISSION_REQUEST` (auto-resolve via `decision.behavior`), `NOTIFICATION` (matches on `notification_type`)
- `STOP` (block-to-continue + turn-extension point, capped at 8 consecutive blocks), `STOP_FAILURE` (observe-only; `error_type` matcher token)
- `PRE_COMPACT` (can **block** compaction; injects `additionalContext`), `POST_COMPACT`
- `SUBAGENT_START`, `SUBAGENT_STOP` (fire around delegation with `agent_type`/`agent_id`; SubagentStop observe-only)
- `PRE_COMMAND`, `POST_COMMAND` — slash-command bracketing (Zrb-specific; closest Claude analog `UserPromptExpansion`)

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent). No `http`, no `mcp_tool`.

**7 matcher operators**: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`.

**Claude-protocol parity** ✅ (ADR-0066/0074): every tool call flows through one chokepoint (`SafeToolsetWrapper.call_tool`), so hooks fire reliably and honor the Claude wire protocol:
- **PreToolUse**: `permissionDecision` `deny`/`ask`/`defer`, `exit 2` block (reason read from **stderr**), `updatedInput` arg rewrite
- **PostToolUse**: `decision: block`, `updatedToolOutput`, `additionalContext` (appended to the model-facing result)
- **Turn control**: `UserPromptSubmit` / `Stop` can end or extend the turn; `continue:false` halts the `run_agent` loop; raw stdout from `SessionStart`/`UserPromptSubmit` becomes `additionalContext`
- **Claude-shaped IO**: event payload written to the hook subprocess' **stdin** as `to_claude_json()`; reads `.claude/settings.json` / `settings.local.json` as hook sources; Claude-style env vars; **tool-name aliases** (`Shell`→`Bash`, `DelegateToAgent`→`Task`) so Claude matchers register; `ZRB_HOOKS_ENABLED` global kill-switch
- Async hooks are true fire-and-forget (semaphore + backlog ceiling); skill-frontmatter hook definitions; `add_hook_factory()` on both `LLMChatTask` and `LLMTask` (ADR-0076)

**Status**: 🟡 **Partially supported**

**Gap**: 16 of ~30 Claude Code events (~53%). Missing events: `Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `CwdChanged`, `FileChanged`, `ConfigChange`, `Elicitation`/`ElicitationResult`, `WorktreeCreate`/`WorktreeRemove`, `TaskCreated`/`TaskCompleted`, `TeammateIdle`, `PermissionDenied`. Missing handler types: `http`, `mcp_tool`. Missing features: `CLAUDE_ENV_FILE`, `once`, `statusMessage`, `/hooks` UI, conditional `if`, `allowedHttpHookUrls`, `terminalSequence`.

**Behavioral divergences** (documented in `docs/advanced-topics/hooks.md`): Zrb runs hooks **sequentially by priority** (not parallel + most-restrictive-wins); only the first `additionalContext` is used; a blocked `PostToolUse` discards the result; `ask` degrades to proceed on the execution-time path; `SubagentStop` is observe-only; `Notification` fires only for elicitation.

**Effort to close**: **Medium** (3–4 weeks): `http` handler (2–3d), `mcp_tool` handler (2–3d), remaining lifecycle events + fire points (~1wk), `if`/`once`/`statusMessage` (2–3d), `/hooks` UI (2–3d).

---

## 6. MCP (Model Context Protocol)

### Claude Code

Transports: `stdio`, `http` (a.k.a. `streamable-http`, recommended), `sse` (deprecated), `ws`. Config scopes (priority): managed → user `~/.claude.json` → local project → `.mcp.json` → `--mcp-config`. `claude mcp add`, **`claude mcp login`/`logout`** (v2.1.186), OAuth, MCP prompts as `/mcp__…` commands, MCP tool search (deferred tools), MCP resources tools (`ListMcpResourcesTool`/`ReadMcpResourceTool`), **dynamic tool updates via `list_changed`** (v2.1.172), **per-tool idle timeout** (5-min default, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` — v2.1.187), subagent-scoped servers, `allowManagedMcpServersOnly`/`deniedMcpServers`, `--strict-mcp-config`, `/mcp` UI, registry/marketplace, Channels notifications.

### Zrb

- **Transports**: `stdio` + **`http`/URL** ✅ (now via `fastmcp`; the prior `sse`-only assessment is outdated)
- Config: `mcp-config.json` (configurable via `MCP_CONFIG_FILE`), searched home → CWD hierarchy
- **Env var expansion** with `${VAR}` / `${VAR:-default}` (recursive over command/args/env)
- Retry via `LLM_MCP_MAX_RETRIES` (default 3)
- Loaded via `load_mcp_config()` in `LLMChatTask`

**Status**: 🟡 **Partially supported**

**Gap**: `stdio` + `http` work. Missing: `ws` transport, `zrb mcp add`/`login`/`logout` CLI, OAuth, MCP prompts → slash commands, MCP tool search / deferred loading, MCP resources tools, dynamic `list_changed` updates, per-tool idle timeout, subagent-scoped MCP, `/mcp` UI, managed-only policy, registry/marketplace.

**Effort to close**: **Medium** (3–4 weeks): `ws`/`sse` (3–5d), `zrb mcp add` (2d), prompts→commands (3–4d), resources tools (2–3d), `/mcp` UI (2–3d), OAuth (1–2wk), deferred loading (1wk).

---

## 7. Subagents / Multi-Agent Orchestration

### Claude Code

Declarative subagents via markdown + YAML frontmatter (`.claude/agents/`, `~/.claude/agents/`, plugin `agents/`, `--agents`). Frontmatter: `name`, `description`, `prompt`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `initialPrompt`, `color`. Invocation: natural language, `@-mention`, `--agent`, `/agents`. Foreground/background (Ctrl+B), subagent compaction, tool allow/deny, `isolation: worktree`, persistent agent memory, auto-delegation, `/agents` UI, managed subagents, forked subagents (`CLAUDE_CODE_FORK_SUBAGENT=1`). Built-ins: Explore, Plan, general-purpose, Bash, statusline-setup, Claude Code Guide.

### Zrb

**File-based agents** (`.agent.md` / `AGENT.md` / `.agent.py` / plain `.md` in `agents/`):
- Frontmatter: `name`, `description`, `model`, `tools`, **`inherit_sections`** (🔵 Zrb-specific — sub-agent inherits named PromptManager sections from the main agent)
- Discovery from search dirs (home → project → plugins → builtin); `.md`-only filter (v2.22.3)
- Built-in agents (`src/zrb/llm_plugin/agents/`): `generalist`, `researcher`, `code-reviewer`

**Delegation tools**:
- `create_delegate_to_agent_tool()` → `DelegateToAgent(agent_name, deliverable, task, non_goals, additional_context, tasks=[])` — single sub-agent scope-clamped via a DELIVERABLE/NON-GOALS/TASK/CONTEXT envelope; passing a non-empty `tasks` list runs every entry **concurrently** (ADR-0070 folded the former standalone `DelegateToAgentsParallel` into this one argument)
- **`DelegateToAgentBackground` + `GetDelegationResult`** ✅ (ADR-0054) — background sub-agents as detached `asyncio` tasks; inherit the parent's permission policy / YOLO / agent mode via ContextVar copy; approvals route to the parent UI's confirmation queue (interrupt-to-ask, no silent auto-approve); `BufferedUI` holds output until flush; `GetDelegationResult` accepts `wait=` (block up to `LLM_BACKGROUND_WAIT_MAX`, default 300s) and `kill=` (ADR-0072); multiple can run concurrently — parity with Claude Code's foreground/background subagents (minus the Ctrl+B UI)
- **`SubagentStart`/`SubagentStop` hooks** ✅ (ADR-0074) fire around delegation on the parent run's hook manager (`agent_type`/`agent_id`)
- **Permission-filtered roster** ✅ (ADR-0053): `DelegateToAgent`'s agent roster is filtered by the active permission policy at render time; delegation is tagged `DELEGATE` and denied in plan mode
- `SubAgentManager` (nested `manager/` package) with lazy filesystem loading; uses `LLMConfig.resolve_model()` so sub-agents respect the global model pipeline; built-in agents gated by `LLM_ENABLE_BUILTIN_AGENTS` (ADR-0069)
- **YOLO inheritance** ✅: full and selective YOLO propagate to sub-agents
- **Tool-guidance propagation** ✅: sub-agents receive the same `# Tool Usage Guide`

**Status**: 🟡 **Partially supported**

**Gap**: File-based definitions, foreground/parallel/background delegation, and permission inheritance all work, but invocation is via the `DelegateToAgent` tool — no `@-mention`, no natural-language auto-delegation, no `/agents` UI. Frontmatter lacks `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `initialPrompt`, `color`, `disallowedTools`. No persistent agent memory directory, no managed subagents.

**Effort to close**: **Medium-High** (4–6 weeks): `@-mention` + typeahead (3–4d), auto-delegation (3–4d), per-agent permissionMode/maxTurns/memory (~1wk), subagent-scoped MCP (~1wk), worktree isolation (1–2wk), `/agents` UI (3–4d).

---

## 8. Agent Teams & Dynamic Workflows

### Claude Code

- **Agent Teams**: multiple Claude Code instances cooperating; **implicit team per session** with direct `Agent(name=…)` spawning (v2.1.178 removed the explicit `TeamCreate`/`TeamDelete` tools); shared task list with self-coordination; inter-agent `SendMessage`; display modes (in-process or split tmux via `--teammate-mode`/`teamMateMode`); file locking; task dependencies; hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`); storage `~/.claude/teams/`, `~/.claude/tasks/`.
- **Dynamic Workflows** (the `Workflow` tool, v2.1.154): orchestrate "tens to hundreds of agents in the background"; deterministic JS scripts that fan out/pipeline subagents; structured-output schemas; budget-aware loops; `/workflows` viewer; trigger keyword `ultracode`; **nested subagents up to 5 levels deep** (v2.1.172).

### Zrb

`DelegateToAgent(tasks=[…])`: concurrent multi-agent execution, aggregated results, shared rate limiter + UI lock, per-agent error handling. **Background subagents**: `DelegateToAgentBackground` spawns detached agents that run while the main conversation continues, now with `wait=`/`kill=` collection (ADR-0072) and `SubagentStart`/`SubagentStop` lifecycle hooks (ADR-0074) — real building blocks toward background orchestration. Still no persistent team lifecycle, no inter-agent messaging, no shared task list with dependencies, no script-orchestrated fan-out to hundreds of agents.

**Status**: ❌ **Not supported** (parallel + background delegation exist, but not teams or scripted dynamic workflows)

**Gap**: Zrb's delegation returns results to one parent — not persistent coordinated agents nor a deterministic orchestration runtime. Missing: team lifecycle / implicit-team coordination, inter-agent messaging, shared task list with dependencies, tmux display, file locking, the `Workflow` dynamic-orchestration runtime, nested subagents.

**Effort to close**: **Very High** (8–12 weeks) — fundamentally different architecture. Zrb's existing DAG task engine + parallel delegate are partial building blocks for the dynamic-workflow side.

---

## 9. Skills System

### Claude Code

File-based skills (`.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md`). Scopes: managed > personal > project > plugin. Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, **`disallowed-tools`** (new), `model`, `effort`, `context` (fork), `agent`, `hooks`, `paths`, `shell`. Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`, **`${CLAUDE_EFFORT}`** (new). Dynamic context `` !`command` ``, forked subagent context, `paths:` glob activation, monorepo auto-discovery, `--add-dir` skills, `disableSkillShellExecution`, plugins auto-load from `.claude/skills/`, `/reload-skills`. Bundled: `/batch`, `/claude-api`, `/debug`, `/loop`, `/code-review`. Follows the [Agent Skills](https://agentskills.io) standard.

### Zrb

Comprehensive skill system (`src/zrb/llm/skill/`):
- File types: `.skill.md`, `.skill.py`, `SKILL.md`, `SKILL.py`
- Scopes: default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`)
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, **`hooks`** ✅ (skill-defined hooks supported)
- **Companion-file discovery** ✅: `ActivateSkill` returns the skill directory path + grouped companion-file listing; `discover_companion_files()` + `format_companion_file_lines()`
- Lazy scan + content caching; factory-function skills; `get_skill_custom_command()`

**Built-in skills** — split into governable categories (ADR-0069):
- `core_skills/` — five always-on methodology hubs (`core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`); **no toggle** (disabling would break the utility skills that delegate into them)
- `skills/` — eight utility skills (`debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`), gated by `LLM_ENABLE_BUILTIN_SKILLS` (default on)
- `agents/` — sub-agents gated by `LLM_ENABLE_BUILTIN_AGENTS` (default on)
- `core-coding` companions: `languages/` (python, typescript, go, rust, java, ruby, php) + `workflows/` (testing, debug, refactor, review, **observability** — core/heap dumps, `kubectl` triage, PromQL, Kibana, with read-only helper tools)
- Both toggles suppress **only built-in content** — user/project/plugin/extra skills always load; this is Zrb's analog of Claude Code's `disableBundledSkills`. Skill activation table in the Operating Rules maps domain → core skill (auto-approved, silent, once per session/domain)

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close, and the built-in-content toggles now match `disableBundledSkills`. Missing: `effort` and `${CLAUDE_EFFORT}` (Zrb has no effort concept), `disallowed-tools`, `paths:` glob activation, `shell` field, `` !`command` `` dynamic injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitutions, bundled utility skills (`/batch`, `/loop`).

**Effort to close**: **Low** (1–2 weeks): `paths`/`shell`/`disallowed-tools` frontmatter (2–3d), `` !`command` `` preprocessing (1–2d), `$CLAUDE_SESSION_ID`/`$CLAUDE_SKILL_DIR` (1d), `/loop` bundled skill (2–3d).

---

## 10. Permission Modes & Tool Approval

### Claude Code

**6 permission modes**: `default`, `acceptEdits` (auto-approves edits + common FS commands), `plan`, `auto` (background safety classifier; now blocks destructive `git reset --hard`/`clean -fd`/`stash drop`/`commit --amend` and `terraform`/`pulumi`/`cdk destroy` unless explicitly requested — v2.1.183), `bypassPermissions`, `dontAsk`. Shift+Tab cycling; `--permission-mode` (incl. `dontAsk`); `defaultMode`. Permission rules `Tool`/`Tool(specifier)`/**`Tool(param:value)` input-parameter matching** (v2.1.178, e.g. `Agent(model:opus)`)/globs/domains/MCP patterns; evaluation deny > ask > allow; config managed > CLI > local > project > user; `hard_deny` unconditional rules; glob in the tool-name position of deny rules incl. `"*"`; `PermissionRequest`/`PermissionDenied` hooks.

### Zrb

**Permission policy system** ✅ **NEW (v2.32.0, ADR-0049–0055)** (`src/zrb/llm/permission/`):
- **Capability tags**: every tool is tagged `READ` / `EDIT` / `EXECUTE` / `NETWORK` / `DELEGATE` / `META` (untagged → conservative `UNKNOWN`) centrally in `common_tools.py`
- **`PermissionPolicy`**: ordered, first-match-wins `Rule`s with `allow` / `ask` / `deny` actions; rules match by tool name or capability tag, plus **`arg_pattern` fnmatch globs** over salient args (path, command, url, agent_name, …) — the analog of Claude Code's `Bash(npm run *)` specifier syntax, expressed in Python
- **Plan mode** ✅: `EnterPlanMode` / `ExitPlanMode` tools (tagged `META`) + `/plan` UI toggle; a preset read-only policy (READ/NETWORK/META allow; EDIT/EXECUTE/DELEGATE deny); enforced by the execution gate in `agent/common.py`; `ExitPlanMode` requires user approval; per-run `AgentModeState` isolation so concurrent sessions/sub-agents don't clobber each other's mode; non-interactive runs resolve the hard ASK deterministically (auto-approve `ExitPlanMode`, deny other gated tools) instead of hanging (ADR-0067)
- **Shift+Tab mode cycling + auto-accept-edits** ✅ (ADR-0075): `normal → auto-accept-edits → plan → normal` in the default TUI; **auto-accept-edits** (selective YOLO over `Write`/`Edit`) is the analog of Claude Code's `acceptEdits`. Status-bar mode badge; web UI / MultiUI reach the modes via `/plan` and `/yolo Write,Edit`
- **First-class `permissions=` / `sandbox=` on both `LLMChatTask` and `LLMTask`** ✅ (ADR-0078): constructor args + read/write properties; precedence explicit arg > `ZRB_LLM_PERMISSIONS` env > ambient ContextVar (sub-agent inheritance) > Plan Mode override
- **Approval precedence chain** (ADR-0055): intrinsic always-auto-approve (Priority 0, e.g. `AskUserQuestion`) → `permission_policy` → `tool_policy` → `yolo`; `deny` stops at the gate, `allow` bypasses lower checks; YOLO is re-expressed as a `PermissionPolicy` via `from_yolo()`
- **Policy inheritance**: `LLMTask(permission_policy=…)`, `current_permission_policy` ContextVar → sub-agents (incl. background) inherit automatically
- YOLO mode = full `bypassPermissions`; **selective YOLO** (`--yolo "Write,Edit"` / `/yolo Write,Edit`); propagates to sub-agents (v2.28.0)
- `auto_approve()` predicates: cwd / journal / skill+plugin dir scoping; `bash_validation` auto-approves read-only commands and rejects dangerous metacharacters — **hardened v2.33.3**: bare `&`, newlines/CR now rejected; `env` removed from safe prefixes
- `ApprovalChannel` + `MultiplexApprovalChannel` (first-response-wins across channels); override tool args at approval time (`ApprovalResult.override_args`)

**Status**: 🟡 **Mostly supported**

**Gap**: Zrb has a real rule engine (capability tags + ordered allow/ask/deny rules + arg globs), plan mode, **Shift+Tab cycling**, an **auto-accept-edits** mode (≈`acceptEdits`), a defined precedence chain, a `PermissionRequest` hook, and first-class task-level `permissions=`. Missing: `dontAsk` mode, the `auto` classifier mode (§16), `Tool(param:value)` input-parameter matching (Zrb's `arg_pattern` globs cover the path/command/url args but not arbitrary named params), *declarative* permission-rule config (rules are Python objects, not `settings.json` strings), deny>ask>allow cross-source evaluation with managed/enterprise layers, a `PermissionDenied` hook.

**Effort to close**: **Medium** (1–2 weeks): `dontAsk` preset (1–2d), declarative rule syntax parser → `PermissionPolicy` (1wk), `Tool(param:value)`-style matching over arbitrary args (2–3d).

---

## 11. Settings & Configuration System

### Claude Code

4 scopes: managed > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`). JSON schema for autocomplete. `/config` tabbed UI + **`/config key=value`** to set any key from the prompt (v2.1.181), `/config --help` lists settable keys. Global `~/.claude.json` (`editorMode`, `autoConnectIde`, `teammateMode`, …). Server-managed settings (claude.ai admin, MDM/OS policies, `managed-settings.json` + `managed-settings.d/`). `requiredMinimumVersion`/`requiredMaximumVersion`, `fallbackModel` (up to 3, ordered), `disableBundledSkills`, `enforceAvailableModels`, `attribution.sessionUrl`, `sandbox.credentials`/`allowAppleEvents`, `respondToBashCommands`.

### Zrb

**Single config source**: `CFG` singleton (`src/zrb/config/`), env vars (prefix `ZRB_`), composed from mixins under `mixins/`. `CFG.FOO` access stays flat regardless of owning mixin. **`EnvField` data descriptor** ✅ replaced 700+ lines of getter/cast boilerplate; mixins gained `TYPE_CHECKING` `Protocol` host-classes for static checking; empty env vars fall back to defaults instead of crashing typed casts; **`EnvField.fallback`** (degrade a garbage value to a fixed default) and **`EnvField.transform`** (post-read transform that can depend on sibling config, e.g. clamping a token threshold) added v2.40.1.

- **`zrb config explain`** ✅ **(v2.39.0)**: a built-in task that renders every `EnvField`-backed knob as a markdown table (env var, current value in env-var format, `doc` string), optional `--keyword` filter — a discovery surface analogous to `/config --help`
- **Boolean naming convention codified** (ADR-0073): `<NAMESPACE>_ENABLED` (state-last) for a namespace master switch; verb-first (`ENABLE_`/`SHOW_`/`SEARCH_`/…) for standalone toggles; renames preserve old env keys via `EnvField(aliases=…)`
- Reads `.claude/settings.json` / `settings.local.json` as **hook sources** (ADR-0066) — partial settings-file ingestion, but not a general layered settings store
- All magic numbers configurable (timeouts/intervals/sizes/retries)
- **Tool Guidance System** (v2.21.0): `ToolGuidance` dataclass, `add_tool_guidance()` / `add_tool_guidance_factory()`, `CFG.LLM_INCLUDE_TOOL_GUIDANCE`; consolidated into `apply_common_tools()` (v2.28.6) shared across `LLMChatTask`/`LLMTask`/`SubAgentManager`
- **Consolidated model pipeline** (v2.23.0): `LLMConfig.resolve_model()` is the single model-resolution entry point (replaced the task-level getter/renderer of v2.22.0)
- **Per-model capability registry** (v2.28.2): `model_capabilities.register("pattern", supports_parallel_tool_calls=…, supports_image_input=…)`; `create_agent()` injects `parallel_tool_calls=False` for known-malforming models
- Retry config: `LLM_API_MAX_RETRIES`, `LLM_API_MAX_WAIT`; history backup retention `LLM_HISTORY_BACKUP_RETAIN`

**Status**: 🟡 **Partially supported**

**Gap**: Primarily env-var driven, with `zrb config explain` for discovery and `.claude/settings.json` read only for hooks. Missing: a general JSON settings store with layered scopes (user/project/local), JSON schema, a `/config` UI, `/config key=value` runtime set, and a managed/enterprise policy layer.

**Effort to close**: **Medium** (2–3 weeks): JSON settings loader + scope hierarchy (1wk), merge with env vars (2d), JSON schema (2–3d), `/config` UI (1wk).

---

## 12. Built-in Tools

### Claude Code (38+ tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` |
| `Write` | ✅ `write_file` (post-write LSP/static diagnostics v2.30) |
| `Edit` | ✅ `replace_in_file` (fuzzy match + post-edit diagnostics) |
| `Bash` | ✅ `Shell` (primary, runs configured shell) + `Bash` (always real bash — matches Claude Code semantics, v2.33.2) — streaming, cross-platform (`psutil` tree teardown, `start_new_session`), stdin=DEVNULL fail-fast |
| `Bash` background (`run_in_background`) | ✅ `Shell`/`Bash` with `background=True` (ADR-0071 folded the former `ShellBackground` tool in) + **`MonitorProcess`** (poll / `wait=` / `kill=`) |
| `Glob` | ✅ `glob_files` (+ `include_hidden`, v2.32.2) |
| `Grep` | ✅ `search_files` (ripgrep acceleration) |
| `Agent` (spawn subagent; nested up to 5 levels — v2.1.172) | 🟡 `DelegateToAgent` (single or `tasks=[]` parallel) / **`DelegateToAgentBackground` + `GetDelegationResult`** (file-based defs, tool-invoked); sub-agents can themselves delegate |
| `WebFetch` | ✅ `open_web_page` (`OpenWebPage`) |
| `WebSearch` | ✅ `search_internet` (Google News RSS default, SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | ✅ `AskUserQuestion` — arrow-key selection UI + multi-select (v2.34.0); intrinsically auto-approved in every path (ADR-0062); short-circuits in non-interactive mode |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full suite incl. `LspRenameSymbol` (8 tools); `ZRB_LLM_LSP_PREFERRED_SERVERS` + per-server config (v2.32.0) |
| `TaskCreate/Get/List/Update/Stop` (background bash tasks) | ✅ `write_todos`/`get_todos` (a full `write_todos` replaces the list — `update_todo`/`clear_todos` removed as redundant, ADR-0068; system-context integration + UI progress cards, ADR-0057) |
| `CronCreate/Delete/List` | ❌ Not LLM tools (Zrb `Scheduler` exists at task level) |
| `EnterPlanMode` / `ExitPlanMode` | ✅ **`EnterPlanMode`/`ExitPlanMode` with enforced read-only policy** — **NEW (v2.32.0, ADR-0051)** |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking) |
| `Monitor` (stream background events) | 🟡 `MonitorProcess` polls background shell processes; no unified event stream across task types |
| `SendMessage` (agent teams) | ❌ Teams not implemented |
| `Workflow` (script-orchestrated fan-out — v2.1.154) | ❌ Not implemented (`DelegateToAgentBackground` is a partial building block) |
| `Artifact` (publish live web page to claude.ai) | ❌ Not implemented (Zrb has a local web UI instead) |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` / `ReadMcpResourceTool` | ❌ Not implemented |
| `PowerShell` | 🟡 No dedicated tool, but `Shell` resolves `pwsh` → `powershell` → `cmd` on Windows with correct flags (v2.33.2; unit-tested, not yet verified on real Windows) |
| `Skill` (invoke skills) | ✅ `ActivateSkill` (returns companion files) |
| `RemoteTrigger` / `PushNotification` | ❌ Not implemented |

**Additional Zrb tools not in Claude Code** 🔵:
- `RM` (`remove_file`), `MV` (`move_file`) — **NEW (v2.24.0)**
- `SearchJournal` — **NEW (v2.24.0)**
- `AnalyzeFile` (AST-based), `AnalyzeCode` (LLM sub-agent analysis)
- `create_rag_from_directory` (ChromaDB embeddings, semantic search)
- `List{Root}Tasks` / `Run{Root}Task` (discover + run any Zrb task as a tool)
- Tool Guidance System (`add_tool_guidance()` per-tool hints into the system prompt)

> **Removed (v2.28.0)**: `read_files`/`write_files` (ReadMany/WriteMany) — `Read`/`Write` now handle multiples via parallel calls.

**Post-write/edit diagnostics** ✅ (v2.30) (`src/zrb/llm/tool/post_write_check.py`): after `write_file`/`replace_in_file`, runs LSP `get_diagnostics()` + static checks (Python `ast.parse` + `pyflakes`); appends a `[DIAGNOSTIC]` block (up to 5 errors) to the tool result. Mirrors Claude Code's post-edit type-error reporting.

**Tool-output truncation backstop** ✅ **NEW (v2.32.0, ADR-0052)**: global `LLM_MAX_TOOL_RESULT_CHARS` cap (default 100k) truncates model-facing content head+tail with a re-fetch hint, preserving structured `return_value`.

**Status**: 🟡 **Mostly supported**

**Gap**: Core file/shell/web/worktree/LSP/todo tools well-covered; background shell, plan-mode tools, and background delegation all present. Missing: `NotebookEdit`, `CronCreate/Delete/List`/`ScheduleWakeup`, unified `Monitor` event stream, `SendMessage` (teams), the `Workflow` orchestration tool, `Artifact`, `ToolSearch` (deferred tools), MCP resource tools, `RemoteTrigger`/`PushNotification`.

**Effort to close**: **Medium** (2–3 weeks): `NotebookEdit` (3–4d), Cron tools (3–4d, reuse `Scheduler`), `ToolSearch` deferred loading (1wk), unified `Monitor` (2–3d).

---

## 13. IDE Integrations

### Claude Code

VS Code extension (panel/sidebar/tab, inline diff accept/reject, `@`-mention, selection context, drag attachments, multi-conversation tabs, plugin UI, auto-install). JetBrains plugin (IntelliJ/PyCharm/WebStorm, interactive diff, Shift+Tab cycling). Desktop app (macOS/Windows, visual diff, side-by-side sessions, computer use, Dispatch, scheduled tasks, `/desktop` handoff). `/terminal-setup` GPU toggle.

### Zrb

**Web UI** (FastAPI-based) — browser chat at `http://localhost:21213`, session persistence, model switching, YOLO toggle, JWT auth, SSE streaming, ChatGPT-like layout, browser tool approval (edit args on the fly), HTTP Chat API, Jinja2 templates + local mermaid.js (no external CDN). No VS Code / JetBrains / Desktop integration.

**Status**: ❌ **Not supported** (IDE integrations); 🟡 Web UI is a different paradigm.

**Effort to close**: **Very High** (3–6 months for full parity).

---

## 14. Session Management & Checkpointing

### Claude Code

Checkpointing: auto checkpoint before every edit and per prompt; 30-day retention (`cleanupPeriodDays`); Esc+Esc rewind menu (code+conv / conv-only / code-only); `/rewind`; `/branch`/`/fork`. Sessions per cwd; `--continue`/`-c`, `--resume`/`-r` (by id/name/picker), `--name`/`-n`, `/rename`, `--fork-session`, `--from-pr`, `--no-session-persistence`, `/export`, `/usage` stats.

### Zrb

- `FileHistoryManager` → JSON history (`~/.zrb/history/{name}.json`); named sessions via `--session`
- **Backup rotation** ✅ (v2.28.0): `LLM_HISTORY_BACKUP_RETAIN` (default 3; `-1` keep all, `0` disable); lexicographic (deterministic) sort
- `/load` shows history with icons; fuzzy session search
- **SQLite-backed sessions** via `ChatSessionManager` for the web UI
- **Snapshot / rewind** ✅: `SnapshotManager` (shadow git repos); `/rewind` picker; 3 restore modes; incremental sync + `DEFAULT_IGNORE_DIRS` (`.venv`, `node_modules`, …) for sub-second backup/restore (v2.26.8/2.28.0); `LLM_ENABLE_REWIND`, `LLM_SNAPSHOT_DIR`
- **Escape preserves history** ✅: interrupting a response saves the user message + `[SYSTEM: Response was interrupted]` so the next turn continues from context
- **Partial-run retry context** ✅ **(v2.38.0)**: when a turn is cancelled (Escape) or dies on an unrecoverable error, `PartialRunAccumulator` captures the tool calls/results streamed before the break and appends a `[SYSTEM: PREVIOUS ATTEMPT FAILED]` summary (completed tool calls + args + truncated results, whether text was cut off, the error) so the next turn continues from that work instead of repeating it
- **Transcript export** ✅ **NEW (v2.33.2)**: `/copy` copies the full transcript to clipboard (OSC 52 fallback over SSH/tmux) or writes it to a file (untruncated `full=True` mode); bare `/redirect` copies the last AI response; both work on freshly loaded sessions via `extract_last_response_text()`
- Backup rotation no longer deletes live history files with timestamp-suffixed names (v2.33.3)

**Status**: 🟡 **Partially supported**

**Gap**: Rewind/snapshot + ephemeral sessions + interrupt-preserving history + transcript export. Missing: rewind is opt-in (not automatic); no Esc+Esc shortcut; no session branching/forking; no resume-by-id picker; no startup `--name`; no session stats; no `--from-pr`.

**Effort to close**: **Medium** (2–3 weeks): enable rewind by default (1d), Esc+Esc (1–2d), branching (1wk), resume picker (2–3d), `--name` (1d), stats (2–3d).

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, subscription).

### Zrb

🔵 **Zrb-only feature**: FastAPI web UI — browser chat (`http://localhost:21213`), SSE streaming, SQLite session persistence, model switching, YOLO toggle, JWT auth (guest + admin), SSL/TLS, task browsing/execution, REST API (`/api/v1/chat/` — list/create/delete sessions, send messages, SSE stream), ChatGPT-like layout, `HTTPChatApprovalChannel` (browser tool approval with edit-args), Jinja2 templates + local mermaid.js, configurable shutdown timeout.

**Status**: 🔵 **Zrb advantage** — local web UI not present in the Claude Code CLI.

---

## 16. Auto Mode (Safety Classifier)

### Claude Code

Background classifier reviews each action before execution; sees user messages + tool calls (not Claude's text — anti-injection); default block (download+execute, prod deploys, mass deletes, IAM) / allow (local file ops, deps, read-only HTTP); fallback to prompting after 3 consecutive / 20 total blocks; `autoMode.environment`/`allow`/`soft_deny`, **`hard_deny`** unconditional; `disableAutoMode`; `useAutoModeDuringPlan`; `claude auto-mode defaults`. Now on Bedrock/Vertex/Foundry (`CLAUDE_CODE_ENABLE_AUTO_MODE=1`); classifier detects data exfiltration / bulk repo transfers; **blocks destructive `git reset --hard`/`clean -fd`/`stash drop`/`commit --amend` and `terraform`/`pulumi`/`cdk destroy` unless explicitly requested** (v2.1.183).

### Zrb

No equivalent safety classifier. YOLO bypasses all confirmations; non-YOLO requires approval (with the permission policies and auto-approve predicates of §10). Partial mitigations now exist — plan mode (read-only enforcement), the opt-in sandbox (§18), and hardened `bash_validation` (v2.33.3: bare `&`, newlines, `env` prefix all rejected) — but none is an LLM-based pre-action classifier.

**Status**: ❌ **Not supported**

**Effort to close**: **High** (4–6 weeks): pre-action classification hook (1wk), default block/allow rules (1wk), configurable rules (1wk), fallback counter (2d), integration with permission modes (1wk).

---

## 17. GitHub / CI/CD Integration

### Claude Code

GitHub Actions (`@claude` mention triggers), GitLab CI, GitHub Code Review bot, `/install-github-app`, `--from-pr`, `/pr-comments`, PR status footer, `/security-review`, Slack integration, `/batch` (parallel worktree agents each opening a PR), **`claude ultrareview`** (non-interactive CI review — new), `/code-review --fix`.

### Zrb

🔵 **Zrb-only**: task-automation system with Git utilities (`src/zrb/builtin/git`), `run_shell_command` can drive `gh`/`git`, RAG tools, `review` built-in skill (structured code + security review). No native GitHub app, CI triggers, PR-comment triggers, Slack, or Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**: **High** (4–8 weeks): GitHub Actions template calling `zrb llm chat -p` (1–2d), GitLab template (1d), PR footer via `gh` (1–2d), `/pr-comments` (2–3d), `/security-review` adapt from `review` skill (1d), GitHub webhook → Zrb trigger (2–3wk), Slack bot (2–3wk).

---

## 18. Sandboxing

### Claude Code

OS-level Bash sandboxing: `sandbox.enabled`, `failIfUnavailable`, `excludedCommands`, `filesystem.allowWrite/denyWrite/denyRead`, `network.allowedDomains/deniedDomains/allowUnixSockets`. PowerShell tool default-on for Windows third-party deployments. `worktree.bgIsolation`.

### Zrb

**Opt-in two-layer filesystem sandbox** ✅ **NEW (v2.34.0, ADR-0063)** (`src/zrb/llm/sandbox/`):
- One `SandboxPolicy` drives two enforcement layers: a **Python-level FS gate** (`_sandbox_gate` in `agent/common.py`, right after the permission gate) blocking writes outside writable roots (EDIT/UNKNOWN tools) and reads of credential dirs (all tools), and an **OS-level wrapper** for `Shell`/`Bash` (including `background=True` launches) — `sandbox-exec` + generated SBPL on macOS, `bwrap` on Linux
- Config: `ZRB_LLM_SANDBOX_ENABLED` (default **off**), `OS_SHELL` (auto/off), `WRITABLE_PATHS` (default cwd + temp), `DENY_READ_PATHS` (default credential dirs: `~/.ssh`, `~/.aws`, …), `FALLBACK` (`warn` runs unsandboxed with visible warning / `deny` refuses — never silent), `ALLOW_ESCAPE`
- Escape hatch: `dangerously_skip_sandbox` on shell tools — never auto-approved, always routed to a human; blockable via `ALLOW_ESCAPE=false`
- Plumbing mirrors permissions: `LLMTask(sandbox=…)`, `current_sandbox_policy` ContextVar → sub-agent inheritance
- Network stays **open** in v1

**Status**: 🟡 **Partially supported** (was ❌)

**Gap**: FS containment on macOS/Linux now real. Missing: network domain allow/deny lists (open in v1), Windows mechanism (falls back to warn/deny), `excludedCommands`-style granularity, default-on posture, `failIfUnavailable` per-command semantics.

**Effort to close**: **Medium** (2–3 weeks): network filtering via proxy or bwrap `--unshare-net` + allowlist (1–2wk), per-command exclusions (2–3d), Windows AppContainer/Job-object research (open-ended).

---

## 19. Remote & Cloud Sessions

### Claude Code

`--remote` (new web session), `--teleport`, `--remote-control`/`--rc`, `claude remote-control`. Control from claude.ai/app; Channels (Telegram/Discord/iMessage/webhooks via MCP channel plugins); Dispatch (phone → Desktop); cloud sessions across devices; Remote Control MCP connectors with OAuth (new); session color syncs to claude.ai.

### Zrb

🔵 **Zrb-only**: built-in web server (`zrb server start`), REST API, JWT, SSL/TLS. **MultiUI** (broadcast to terminal + Telegram + web; first-response-wins). **MultiplexApprovalChannel** (route approvals to multiple channels). No cloud sessions, Remote Control protocol, Channels plugin system, Dispatch, or multi-device sync.

**Status**: 🟡 **Different approach** — local web server + multi-channel vs cloud infra.

**Gap**: True cloud sessions need cloud infra. Channels (Telegram/Discord/iMessage/webhooks) partially bridged by MultiUI/MultiplexApprovalChannel + HTTP API but no drop-in Channels system.

**Effort to close**: **Low–Medium** for remote API (web server already provides this); **Medium** (2–3 weeks) for WebSocket remote control + channel plugins; **Very High** for true cloud sessions.

---

## 20. Plugins System

### Claude Code

Install from marketplace or local dir; `--plugin-dir` (now `.zip`), `--plugin-url` (archives). Structure: `hooks/hooks.json`, `agents/`, `skills/`, `mcp.json`, `monitors`. `.claude-plugin/plugin.json` manifest; `defaultEnabled`; dependency enforcement. `claude plugin` (incl. `init`/`validate`), `/plugin` UI (lists MCP/LSP/hooks/skills), `/reload-plugins`. Plugins auto-load from `.claude/skills/`. Marketplaces (`blockedMarketplaces`/`strictKnownMarketplaces`, `skipLfs`), `pluginTrustMessage`, channel plugins.

### Zrb

**Skill/Agent/Hook plugin dirs** (closest analog): skills/agents/hooks loaded from multiple dirs; `CFG.LLM_PLUGIN_DIRS` (tilde-expanded); plugin dirs discovered via `.claude-plugin/plugin.json` manifest (`scan_plugin_dirs`); MCP config from multiple locations; `add_hook_factory()` on both task types. Built-in content is independently toggleable (`LLM_ENABLE_BUILTIN_SKILLS` / `LLM_ENABLE_BUILTIN_AGENTS`, ADR-0069) while user/project/plugin content always loads. No formal packaging/marketplace, no `zrb plugin` command, no lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (skills + agents + hooks + MCP, but no packaging/marketplace)

**Effort to close**: **Medium** (3–4 weeks): plugin package format (3–4d), installer `zrb plugin add` (1wk), full plugin-dir scanning (1wk), `/reload-plugins` (2d).

---

## 21. Rate Limiting & Budget Control

### Claude Code

`--max-budget-usd`, `/usage` (merged cost+stats; category breakdown), rate-limit status in footer, `--fallback-model` (now interactive too; `fallbackModel` setting accepts up to 3 ordered fallbacks — v2.1.166), automatic one-time retry on fallback model for unexpected API errors, per-turn token usage.

### Zrb

🔵 **Zrb advantage**: sophisticated rate limiting + retry:
- `LLMLimiter`: requests/min + tokens/min (`ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`); shared across sub-agents
- **`fit_context_window` O(n²)→O(n)** (v2.24.1): ~46× faster at 320 turns
- **Transient provider error retry**: exponential backoff for HTTP 429/5xx, honors `Retry-After`, caps at `LLM_API_MAX_WAIT` (60s), `LLM_API_MAX_RETRIES` (3)
- Summarizer threshold now accounts for system-prompt tokens (v2.24.2)

Missing: per-session budget cap, `/usage`/`/cost`, cumulative spend, fallback model on overload.

**Status**: 🟡 **Partially supported** (rate limiting + retry exceed Claude Code; budget/cost UI missing)

**Effort to close**: **Low** (3–5 days): cumulative token/cost tracking (2d), `--max-budget` input (1d), `/cost` command (1d), fallback model in CFG (1d).

---

## 22. Platform Support

### Claude Code

macOS (Intel + Apple Silicon, Homebrew, Desktop), Linux (native, Docker), Windows (WSL + native, PowerShell/WinGet, Desktop; WSL image/screenshot paste — new), iOS/Android (mobile app, Dispatch), browser (claude.ai/code).

### Zrb

- macOS: ✅ Full
- Linux: ✅ Full
- Windows: 🟡 Partial, improved (pip works; PowerShell autocomplete + clipboard; cross-platform shell stack — `psutil` process teardown, `pwsh`/`powershell`/`cmd` resolution with correct flags; unit-tested but not yet verified on a real Windows host; no native installer)
- Docker: 🔵 images available
- Android/Termux: 🔵 documented (cold-import optimized — lazy `prompt_toolkit`, ~250ms saved on phone; Termux keybinding compatibility — `Ctrl+K` focus toggle, `Tab`/`Shift+Tab` both cycle modes since the two are indistinguishable bytes there, v2.39.0)
- Browser: 🔵 web UI via `zrb server start`

**Status**: 🟡 Partial for Windows; ✅ excellent for macOS/Linux.

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool: post-edit type errors/warnings; `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`; requires language plugin.

### Zrb

🔵 **Zrb advantage**: `LSPManager` singleton (lazy startup, 300s idle timeout); symbol-based API; full suite (`find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, **`rename_symbol`** with dry-run + honest `applied` flag, `list_available_servers`); per-server `initialization_options` + **`ZRB_LLM_LSP_PREFERRED_SERVERS`** ordered preference; project-root detection; all LSP tools auto-approved. **Post-write/edit diagnostics** feed LSP results back into tool results (§12). Clean shutdown: graceful in-loop teardown + `atexit` `force_kill_all()` backstop.
- **Verified end-to-end against real pyright, pylsp, gopls** ✅ **(v2.37.0)**: byte-accurate message framing (the prior `str`-sliced read loop mis-framed non-ASCII and hung), documents `didOpen`'d before file-scoped queries, `find_definition` via `textDocument/definition` (works without indexing), `SymbolInformation` position handling, graceful `workspace/symbol` degradation, drained stderr
- **User-extensible server registry** ✅ **(v2.38.0)**: `lsp_manager.register_lsp_server(name, LSPServerConfig(...))` from `zrb_init.py` adds or overrides a language; registered servers participate in auto-detection, extension matching, and preferred-server ordering

**Status**: ✅ **Fully supported** (Zrb arguably broader — `rename_symbol`, workspace symbols).

---

## 24. Context Compaction

### Claude Code

Auto-compaction at ~95%; `/compact [instructions]`; `PreCompact`/`PostCompact` hooks (matcher `manual`/`auto`); `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`; original transcript preserved in `.jsonl`.

### Zrb

Two-layer auto-summarization:
- **Layer 1** — per-message: large tool results summarized in-place
- **Layer 2** — conversational: triggers on message/token thresholds (now system-prompt-aware, v2.24.2); respects tool call/return pairs; chunk-and-summarize with `<state_snapshot>` consolidation; **parallel chunk summarization** (`asyncio.gather`); `<active_skills>` tracked + restored; all summarizer agents use `LLMConfig.resolve_model()`
- Manual: `/compress` / `/compact`
- **`PRE_COMPACT` and `POST_COMPACT` hooks fire** ✅: `PreCompact` carries `trigger="auto"`, injects `additionalContext`, and can **block** compaction (the hard context-window prune still runs as a safety net); `PostCompact` mirrors it after summarization

**Status**: 🟡 **Partially supported**

**Gap**: Robust auto-compaction with parallel chunks + skill tracking + `PreCompact`/`PostCompact` (both now present). Missing: focus instructions for manual compact (`/compress [instructions]`), original transcript preservation in `.jsonl`.

**Effort to close**: **Low** (1–2 days): focus-instructions argument.

---

## 25. Vim Mode & Editor Features

### Claude Code

Full Vim mode: NORMAL/INSERT, complete navigation/editing/text-objects, **visual mode (`v`/`V`) with operators** (new); `/vim` or `editorMode: "vim"`.

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

`/diff` interactive viewer (uncommitted + per-turn; **keyboard scrolling**, GFM task-list rendering — new); IDE accept/reject hunks; checkpoint-based diff.

### Zrb

No interactive diff viewer. Changes applied directly; git diff via `run_shell_command`. Tool-approval dialogs show formatted edits.

**Status**: ❌ **Not supported** (in TUI; available via shell)

**Effort to close**: **Low–Medium** (1–2 weeks) — `/diff` via `unified_diff`/`rich`.

---

## 28. Task / Todo System

### Claude Code

`TaskCreate/Update/Get/List/Stop` (background bash tasks, unique IDs, auto-clean, Ctrl+T list, `CLAUDE_CODE_TASK_LIST_ID`); `TodoWrite` (session checklist).

### Zrb

🔵 **Zrb advantage**: `TodoManager` with persistent JSON (`~/.zrb/todos/{session}.json`); states `pending`/`in_progress`/`completed`/`cancelled`; auto IDs, timestamps, progress; `write_todos` (a full write replaces the list) + `get_todos`; session isolation + ContextVar wiring (no explicit `session=`); archive on retention; **pending todos rendered into the per-turn `<live-context>`** (LLM never starts blind); **styled progress card pushed to the active UI after every change** (TUI/StdUI/web SSE, ADR-0057). Plus 🔵 the full task-automation framework (`CmdTask`, `LLMTask`, DAG, dependencies, retries, scheduling — with circular-dependency detection).

**Status**: ✅ **Fully supported** (Zrb advantage on persistence + system-context integration).

---

## 29. Scheduling

### Claude Code

`CronCreate/Delete/List` tools (in-session recurring/one-shot prompts); `/schedule` (cloud tasks); `/loop [interval] <prompt>`; Desktop scheduled tasks; cloud scheduled tasks (persist when machine off).

### Zrb

🔵 **Zrb advantage** at the task level: full `Scheduler` task type (cron-based) + `CmdTask` scheduling. No `CronCreate/Delete/List` as in-session LLM tools; no cloud scheduling.

**Status**: 🟡 **Partially supported** (task-level scheduling; not in-session LLM tools; no cloud).

**Effort to close**: **Low** for in-session (2–3d): wrap `Scheduler` as `CronCreate/Delete/List`. **Very High** for cloud scheduling.

---

## 30. Worktree Isolation

### Claude Code

First-class: `--worktree`/`-w`, `--tmux`; `isolation: worktree` in agent frontmatter; `EnterWorktree` (now can switch between managed worktrees mid-session) / `ExitWorktree`; `WorktreeCreate`/`WorktreeRemove` hooks; `/batch`; `worktree.symlinkDirectories`/`sparsePaths`/`bgIsolation`; `.worktreeinclude`.

### Zrb

**Worktree tools** ✅ (`src/zrb/llm/tool/worktree.py`): `enter_worktree(branch_name)`, `exit_worktree(worktree_path, keep_branch)`, `list_worktrees()`; all wrapped in `tool_wrapper` (structured `{"error": …}`).
- **ContextVar tracking** ✅: `EnterWorktree` sets `active_worktree`; injected into every system context + delegate messages; LLM reminded to pass `cwd`/absolute paths; auto-adds `.zrb/worktree/` to `.gitignore`; **stale-worktree guard** clears the var if the path no longer exists (v2.27.0)
- Storage: `{git_root}/.zrb/worktree/{branch_name}`

**Status**: 🟡 **Partially supported**

**Gap**: Core tools + ContextVar tracking + stale guard. Missing: `--worktree`/`-w` CLI flag, `--tmux`, `isolation: worktree` in agent defs, `WorktreeCreate`/`WorktreeRemove` hooks, `/batch`, worktree settings (`symlinkDirectories`/`sparsePaths`), auto-cleanup of empty worktrees on session end, `.worktreeinclude`.

**Effort to close**: **Medium** (2–3 weeks): `--worktree` flag (1–2d), `isolation: worktree` in agent defs (~1wk after agent-frontmatter work), worktree hooks (2d), auto-cleanup (2d), `/batch` (2–3wk).

---

## 31. Multimodal & Attachments

### Claude Code

Native image input on vision models; clipboard paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11); drag-as-attachment in IDE; `@`-mention files.

### Zrb

🔵 **Multimodal attachment pipeline** ✅ **NEW (v2.26.0)** (`src/zrb/llm/util/`):
- `LLM_MULTIMODAL_MODEL` — designate a vision model to describe attachments when the main model is text-only
- `LLM_MAX_IMAGE_DIMENSION` (1568, Anthropic no-extra-cost tier) + `LLM_IMAGE_JPEG_QUALITY` (85): pasted/`/attach`-ed images auto-scaled; opaque→JPEG, alpha→PNG
- `runner._apply_multimodal_fallback`: if the main model can't consume an image/audio, the multimodal model describes it and substitutes text; if none configured, the attachment is dropped with a `⚠️ Dropped <modality>` warning (never silently sent to a rejecting provider)
- Audio: describe/transcribe fallback. Video: kept for Gemini-class, dropped-with-warning otherwise
- Per-model capability registry (`model_capabilities`) drives image/audio/video support detection
- Clipboard paste via **Ctrl+V and Alt+V**

**Status**: ✅ **Fully supported / 🔵 advantage** — the text-only-model fallback (describe-then-substitute) and explicit drop-with-warning are beyond Claude Code's image handling, important for Zrb's multi-provider story.

---

## 32. Provider Resilience & Multi-Model

### Claude Code

Single primary provider (Anthropic) with `--fallback-model` on overload; Bedrock/Vertex/Foundry deployments; opaque-error handling abstracted by the platform.

### Zrb

🔵 **Major Zrb advantage** — multi-provider robustness (largely built v2.23–2.26):
- Any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock, …)
- **4-stage history sanitization** (`sanitize_history`): filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles
- **Provider-specific 400 recovery**:
  - DeepSeek `reasoning_content` rejection → `strip_thinking_parts` retry
  - GLM-5 / Bedrock empty `ValidationException` → detected and retried
  - **Generic opaque-400** → `strip_to_text_only()` collapse + single retry (provider-agnostic; works for unknown future providers)
  - Bedrock nil-content → `"."` placeholder (not `""`)
  - Invalid-tool-call detection requires entity + problem keyword (avoids false positives); body-message extraction from `e.body`
- **Parallel-tool-call guard**: `model_capabilities` injects `parallel_tool_calls=False` for known-malforming models (minimax, glm-4.7); mandate wording softened to cue-framing so weak models don't over-batch
- **Empty-completion guard** ✅ (v2.32.0, ADR-0059): blank / leaked `"(tool call)"` completions regenerated instead of surfaced; placeholder no longer injected into tool-call-only turns (weak models had learned to imitate it)
- **Summarizer hardening** ✅ (v2.32.0, ADR-0058): deferred-tool death-spiral fixed; summarization calls retry transient 5xx/429; targeted `strip_orphaned_returns`; no retry on too-long prompts
- `request_limit=None` overrides pydantic-ai's 50-request tool-loop cap; `create_agent` uses `tool_retries`

**Status**: 🔵 **Zrb advantage** — far broader provider coverage and resilience than the Claude Code CLI exposes.

---

## 33. Side Questions (`/btw`)

### Claude Code

`/btw <question>` — answered but the Q&A pair is dropped from the transcript; doesn't interrupt in-progress work.

### Zrb

✅ **Fully implemented** (`_handle_btw_command` in `base_ui.py`): `/btw <question>` answered in a temporary context, not appended to history; shares conversation context for relevant answers.

**Status**: ✅ **Fully supported**

---

## 34. Channels & Remote Control

### Claude Code

Remote Control (control a session from claude.ai/app; `--remote-control`/`--rc`, `claude remote-control`; MCP connectors with OAuth — new). Channels (push external events via MCP channel plugins: Telegram/Discord/iMessage/webhooks; `--channels`, `channelsEnabled`, `allowedChannelPlugins`; now works with API-key auth). Dispatch (phone → Desktop). `CLAUDE_CODE_REMOTE` env var.

### Zrb

🔵 **Zrb-only existing**: MultiUI (CLI + Telegram + web simultaneously; broadcast output; first-response-wins input); MultiplexApprovalChannel (route approvals to multiple channels); HTTP Chat API (external POST to `/api/v1/chat/sessions/{id}/messages` pushes messages into an active session). No Remote Control protocol, native Channels plugin system, or Dispatch.

**Status**: 🟡 **Partially covered** (MultiUI + HTTP API cover core use cases; no standardized protocol).

**Effort to close**: **Medium** (2–3 weeks): WebSocket remote control (1wk), webhook endpoint refinement (partial via HTTP API), Telegram/Discord channel plugins (2wk).

---

## 35. Summary & Roadmap

### Structural Capabilities Now Present in Zrb

The features that historically required net-new architecture and are now real implementations:

| Capability | Status | Implementation |
|---------|-------|---------|
| **Permission policy engine** | ✅ | Capability tags (READ/EDIT/EXECUTE/NETWORK/DELEGATE/META), ordered allow/ask/deny rules + `arg_pattern` globs, precedence chain permission_policy → tool_policy → yolo; first-class `permissions=` on both task types (ADR-0049/0050/0055/0078) |
| **Plan mode + Shift+Tab cycling** | ✅ | `EnterPlanMode`/`ExitPlanMode` + `/plan`; enforced read-only preset; `normal → auto-accept-edits → plan` cycle with status-bar badge (ADR-0051/0075) |
| **Auto-accept-edits mode** | ✅ | Selective YOLO over `Write`/`Edit` — the `acceptEdits` analog (ADR-0075) |
| **Filesystem sandbox** | 🟡 | Two-layer: Python FS gate + OS wrapper (`sandbox-exec`/`bwrap`); credential-dir read denial; never-auto-approved escape hatch; network still open (ADR-0063) |
| **Background execution** | ✅ | `Shell`/`Bash` `background=True` + `MonitorProcess`; `DelegateToAgentBackground` + `GetDelegationResult` with `wait=`/`kill=`, permission inheritance, interrupt-to-ask (ADR-0054/0071/0072) |
| **Claude-protocol hooks** | 🟡 | 16 events; tool gates fire for every call through one chokepoint; honors `permissionDecision`/exit-2/`updatedInput`/`block`/`updatedToolOutput`/`continue`; reads `.claude/settings.json`; tool-name aliases (ADR-0066/0074) |
| **Prompt caching** | ✅ | Byte-stable cached prefix + per-turn `<live-context>` block; programmable via `add_live_context()` (ADR-0065) |
| **`Shell`/`Bash` cross-platform** | ✅ | `Shell` (configured shell) + `Bash` (real bash, Claude semantics); `psutil` teardown; Windows `pwsh`/`powershell`/`cmd` (ADR-0056) |
| **Transcript export** | ✅ | `/copy` clipboard (OSC 52) / file; bare `/redirect` → clipboard |
| **Built-in-content toggles** | ✅ | `LLM_ENABLE_BUILTIN_SKILLS` / `LLM_ENABLE_BUILTIN_AGENTS` — the `disableBundledSkills` analog (ADR-0069) |
| **Configurable themes** | ✅ | Semantic CLI color layer + TUI styles, all `ZRB_*` env-backed, hot-reloaded; `examples/themes/` (ADR-0077) |
| **Config discovery** | ✅ | `zrb config explain` renders every `EnvField` knob; `EnvField.fallback`/`transform` (v2.39.0/2.40.1) |
| **Verified LSP** | ✅ | Byte-accurate framing, document-open, `textDocument/definition`; user-extensible server registry (v2.37.0/2.38.0) |

### New Claude Code features (current: v2.1.187)

| Feature | Impact on Gap |
|---------|--------------|
| **Claude Fable 5** flagship | Neutral — Zrb users get it via multi-provider API |
| `Workflow` dynamic-orchestration tool + `/workflows` viewer; nested subagents (5-deep, v2.1.172) | Widens §8 |
| Agent Teams revision: implicit team per session, `Agent(name=…)` spawning, `TeamCreate`/`Delete` removed (v2.1.178) | Reshapes §8 |
| `Tool(param:value)` permission-input matching (v2.1.178) | Minor (§10) |
| Auto mode blocks destructive git/IaC commands (v2.1.183) | Unchanged gap (§16) |
| `MessageDisplay` + `post-session` hook events (v2.1.152/169) | Minor (§5) |
| `claude mcp login`/`logout`; MCP `list_changed` updates; per-tool idle timeout (v2.1.172/186/187) | Minor (§6) |
| `/config key=value`; `enforceAvailableModels`, `sandbox.credentials`/`allowAppleEvents` settings | Minor (§11) |
| `--safe-mode`, `/cd`, multi-fallback models, `disableBundledSkills` | Mostly mirrored by Zrb |

### Overall Coverage Assessment

| Category | Status |
|----------|--------|
| CLI Flags | 🟡 ~20% |
| Interactive TUI | 🟡 ~78% |
| Slash Commands | 🟡 ~50% |
| Memory/CLAUDE.md | 🟡 ~72% |
| Hooks | 🟡 ~53% (16/30) |
| MCP | 🟡 ~55% |
| Subagents | 🟡 ~62% |
| Agent Teams & Dynamic Workflows | ❌ ~10% |
| Skills | ✅ ~88% |
| Permission Modes | 🟡 ~70% |
| Settings System | 🟡 ~40% |
| Built-in Tools | 🟡 ~85% |
| IDE Integrations | ❌ 0% |
| Session/Checkpoint | 🟡 ~68% |
| Web UI | 🔵 advantage |
| Auto Mode | ❌ 0% |
| GitHub/CI Integration | ❌ ~5% |
| Sandboxing | 🟡 ~55% |
| Remote/Cloud | 🟡 different |
| Plugins | 🟡 ~40% |
| Rate Limiting | 🟡 ~75% |
| Platform Support | 🟡 ~85% |
| LSP | ✅ advantage |
| Context Compaction | 🟡 ~88% |
| Vim Mode | ❌ 0% |
| Voice Input | ❌ 0% |
| Diff Viewer | ❌ 0% |
| Task/Todo | ✅ advantage |
| Scheduling | 🟡 ~40% |
| Worktree Isolation | 🟡 ~65% |
| Multimodal & Attachments | ✅ / 🔵 advantage |
| Provider Resilience & Multi-Model | 🔵 advantage |
| Side Questions (`/btw`) | ✅ 100% |
| Channels & Remote Control | 🟡 ~25% |

### Zrb Unique Advantages (Superset Features)

1. 🔵 **Multi-model / any provider** via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock…)
2. 🔵 **Provider resilience layer**: 4-stage history sanitization, provider-agnostic opaque-400 recovery, DeepSeek/GLM-5/Bedrock-specific handling, per-model parallel-tool-call guard
3. 🔵 **Multimodal fallback pipeline**: describe-then-substitute for text-only models, image auto-scaling, audio transcribe, explicit drop-with-warning
4. 🔵 **Local Web UI** with auth, streaming, task management, browser tool approval (edit-args), Jinja2 + local mermaid.js
5. 🔵 **HTTP Chat API** (`/api/v1/chat/`) for programmatic sessions/messages
6. 🔵 **MultiUI + MultiplexApprovalChannel**: broadcast to terminal + Telegram + web; first-response-wins input and approvals
7. 🔵 **Task Automation Framework**: CmdTask, LLMTask, Scaffolder, Scheduler, HttpCheck, TcpCheck — a DAG-based engine
8. 🔵 **Run Zrb tasks as LLM tools**: the agent can discover and execute any project task
9. 🔵 **AST analysis + RAG**: `AnalyzeFile`/`AnalyzeCode`, `create_rag_from_directory` (ChromaDB)
10. 🔵 **Richer LSP**: `rename_symbol` (dry-run), workspace symbols, post-write diagnostics
11. 🔵 **Persistent todos with system-context injection**: session-isolated, status-tracked, rendered every turn
12. 🔵 **Bidirectional journal graph**: backlinks protocol, two-write-kind system, `journal-lint.py`, `<active_skills>` restoration
13. 🔵 **Tool Guidance System**: declarative per-tool hints composited into the system prompt; propagated to sub-agents
14. 🔵 **Per-model capability registry**: user-extensible image/audio/video/parallel-tool flags
15. 🔵 **Consolidated model pipeline**: single `LLMConfig.resolve_model()` across agents, sub-agents, summarizers
16. 🔵 **Fully configurable limits**: all timeouts/intervals/retries/sizes as env vars; backup retention
17. 🔵 **Rate limiting + transient retry**: req/min + tok/min, O(n) context fit, exponential backoff + `Retry-After`
18. 🔵 **Self-hosted, no subscription**: bring your own API key
19. 🔵 **Android/Termux support** with cold-import optimization
20. 🔵 **Flexible web search**: Google News RSS (zero-setup default) + SearXNG/Brave/SerpAPI
21. 🔵 **White-labeling**: build custom CLIs via Zrb's framework
22. 🔵 **Selective YOLO** (`--yolo "Write,Edit"`) with sub-agent inheritance
23. 🔵 **Inherit-sections sub-agents**: sub-agents inherit named prompt sections from the main agent
24. 🔵 **Programmable permission policies**: capability-tagged tools + ordered Python `Rule` objects with arg globs — embeddable in any `LLMTask`, not just an interactive CLI (v2.32.0)
25. 🔵 **Config-positioned custom prompt sections**: `register_section()` dynamic providers or plain markdown files slotted anywhere in the system-prompt order (ADR-0061)
26. 🔵 **OSC 52 clipboard fallback**: `/copy` works over SSH and inside tmux/screen
27. 🔵 **Programming the Agent**: every extension point exposed as a Python hook — custom tools, lifecycle hooks, permission policies, approval channels, model routing, dynamic prompt + live-context providers, history processors, and the agent **as a pipeline node** (`examples/agent-in-pipeline/`); both task types share `add_hook_factory` (ADR-0076)
28. 🔵 **Programmable per-turn live context**: `add_live_context()` injects runtime state into the user turn each turn without invalidating the cached system prefix (ADR-0065)
29. 🔵 **`zrb config explain`**: self-documenting config — every `EnvField` knob rendered with its current value and description, filterable
30. 🔵 **Built-in developer-utility task groups**: `hash`/`time`/`url`/`json`/`case`/`cron`/`hex`/`number`/secure-`random` — stdlib-only Zrb tasks usable from CLI and as LLM tools
31. 🔵 **Partial-run retry context**: a cancelled/failed turn records what was already attempted so the next turn continues instead of repeating work

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. ~~Named permission modes (`plan`), `acceptEdits`, Shift+Tab cycling~~ ✅ **Done** — remaining: `dontAsk` preset (1–2d over the existing policy engine)
2. **Extended CLI flags**: `--permission-mode`, `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--effort`, sandbox toggles (1wk)
3. **JSON settings files** with scope hierarchy (user/project/local) (1wk)
4. **`/usage`/`/cost` + budget tracking** (3–5d)
5. ~~`PostCompact`, `SubagentStart/Stop`~~ ✅ **Done** — remaining hook events: `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `Setup`/`InstructionsLoaded` (3–4d)
6. **Additional built-in slash commands**: `/clear`, `/config`, `/permissions`, `/diff`, `/cd` (1wk) — ~~`/export`~~ ✅ done as `/copy`
7. **`/compress [focus]`** focus instructions (1–2d)
8. **MCP prompts as slash commands** (3d)
9. **`--worktree` CLI flag** (1–2d)
10. **CLAUDE.local.md** + `@import` (3–4d)
11. **Enable rewind by default** + Esc+Esc shortcut (2–3d)
12. **`NotebookEdit` tool** (3–4d) — ~~`Monitor`~~ 🟡 mostly done as `MonitorProcess`
13. **Declarative permission rules** — parse a `settings.json`-style rule list into `PermissionPolicy` (1wk); add `Tool(param:value)`-style matching

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

14. **Full worktree isolation** — `isolation: worktree` in agent defs + `/batch` (2–3wk)
15. **`@-mention` + auto-delegation** for file-based agents + `/agents` UI (2–3wk)
16. **Per-agent frontmatter**: `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory` (1–2wk)
17. **GitHub CI/CD templates** + `/security-review` from `review` skill (1wk)
18. **Plugin packaging format** + `zrb plugin add` (1–2wk)
19. **MCP `ws`/`sse` + OAuth + resources tools** (2–3wk)
20. **`http` + `mcp_tool` hook handler types** (1wk)
21. **Skill enhancements**: `paths`, `shell`, `disallowed-tools`, `` !`command` `` injection (1wk)
22. **Cron tools** (`CronCreate/Delete/List`) wrapping `Scheduler` (3d)
23. **Sandbox v2**: network domain allow/deny lists, per-command exclusions (1–2wk) — base sandbox ✅ done v2.34.0

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

24. **Auto mode safety classifier** (4–6wk)
25. **Dynamic workflows runtime** (script-orchestrated fan-out to many agents) (6–10wk) — `DelegateToAgentBackground` is now a building block
26. **Agent Teams** — persistent coordinated agents (2–3mo)
27. **IDE integrations** (VS Code, JetBrains) (3–4mo)
28. **Vim mode** in TUI (2–3wk)
29. **Voice input** (2–3wk)
30. **Desktop app** (Electron/Tauri) (4–6wk)
31. **Cloud scheduled tasks** (requires cloud infra)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~6–8 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~8–12 months with 2–3 developers

> **Net assessment**: Zrb has closed most of the depth-of-action gaps that historically separated it from Claude Code. The permission layer is now a real engine (capability tags + ordered rules + arg globs) with enforced **plan mode**, an **auto-accept-edits** mode, and **Shift+Tab cycling**; the hook layer reaches **Claude wire-protocol parity** across 16 events (every tool call gated through one chokepoint, honoring `permissionDecision`/`updatedInput`/`block`/`continue`, reading `.claude/settings.json`); the opt-in two-layer **sandbox** (Python FS gate + `sandbox-exec`/`bwrap`) contains the filesystem; **background execution** exists at both the shell and agent level; LSP is verified against real pyright/gopls/pylsp; prompt caching is restored via a byte-stable prefix; and built-in skills/agents/themes/config are all governable. The remaining gaps are now mostly **breadth, surface, and net-new product architecture**: the `Workflow` dynamic-orchestration runtime and agent teams (§8), IDE/desktop integration (§13), the auto-mode safety classifier (§16), cloud sessions (§19), and the perennial CLI-flag / JSON-settings / management-slash-command surface where the infrastructure exists but isn't exposed. Claude Code (v2.1.187) keeps moving on managed-cloud orchestration (`Workflow`, nested subagents, implicit agent teams), auto-mode safety (destructive-command blocking), and MCP lifecycle (`mcp login/logout`, `list_changed`, idle timeout). Zrb's 31 unique advantages (multi-model, provider resilience, multimodal fallback, local web UI, multi-channel, task automation, RAG, richer LSP, programmable permission policies, agent-as-pipeline-node) keep it a genuine superset in the self-hosted / multi-provider / automation dimensions, while Claude Code remains ahead on managed-cloud orchestration, IDE depth, and safety automation.

---

*Analysis updated: 2026-06-24 | Claude Code: code.claude.com/docs + CHANGELOG through v2.1.187 (June 23, 2026) | Zrb version: 2.40.1*
