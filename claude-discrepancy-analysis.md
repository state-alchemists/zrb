# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs) and the public CHANGELOG, surveyed June 2026. Zrb features sourced from full codebase exploration of `src/zrb/`, the changelog (`docs/changelog.md`, `docs/changelog-v2/`), and ADRs 0049–0080.
>
> **Zrb version**: 2.43.1
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

Comprehensive CLI with 70+ flags across 30+ subcommands. Highlights:
- `claude "query"`, `-p`/`--print`, `-c`/`--continue`, `-r`/`--resume`, `-n`/`--name`, `--session-id`
- `--model` (aliases `opus`/`sonnet`/`haiku`/`fable`/`best`), `--permission-mode` (`default`/`acceptEdits`/`plan`/`auto`/`dontAsk`/`bypassPermissions`), `--allow-dangerously-skip-permissions`
- `--max-turns`, `--max-budget-usd`, `--output-format` (`text`/`json`/`stream-json`), `--input-format`, `--json-schema`
- `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`, `--settings`, `--setting-sources`, `--safe-mode`, `--bare`
- `--mcp-config`, `--strict-mcp-config`, `--agent`, `--teams`, `--allowedTools`/`--disallowedTools`
- `--worktree`/`-w`, `--tmux`, `--effort` (`low`/`medium`/`high`/`xhigh`/`max`), `--fork-session`, `--fallback-model` (chain)
- `--bg`/`--background`, `--exec`, `--no-session-persistence`, `--exclude-dynamic-system-prompt-sections`, `--include-partial-messages`, `--include-hook-events`
- `--channels`, `--chrome`/`--no-chrome`, `--remote`, `--remote-control`/`--rc`, `--teleport`, `--teammate-mode` (`in-process`/`auto`/`tmux`/`iterm2`)
- `--plugin-dir`, `--plugin-url`, `--from-pr`, `--ide`
- Subcommands: `claude agents`, `attach`/`stop`/`kill`/`respawn`/`rm`/`logs` (background sessions), `claude daemon`, `claude auth`, `claude mcp` (incl. `login`/`logout`), `claude plugin`, `claude setup-token`, `claude update`/`install`, `claude ultrareview`, `claude remote-control`, `claude auto-mode`, `claude project purge`

### Zrb

`zrb llm chat` with **7 CLI inputs** (`src/zrb/builtin/llm/chat.py`):
- `--message` / `-m`
- `--model`
- `--session` — conversation session name
- `--yolo` — bypass confirmations; full (`true`) or selective (`--yolo "Write,Edit"`)
- `--attach` — file attachments (multimodal-aware, §31)
- `--interactive` — toggle interactive mode (default `true`)
- `--sandbox` — toggle the FS/OS sandbox (`true`/`false`, §18)

**Non-interactive robustness** ✅ (ADR-0067): with `--interactive false`, hard-ASK approval gates are resolved deterministically instead of hanging — `ExitPlanMode` auto-approves (no human to show a plan to), every other hard-ASK tool is denied with a "re-run with `--interactive true`" message. (This single hang previously dominated headless-benchmark timeouts.)

**Status**: 🟡 **Partially supported**

**Gap**: 7 inputs against Claude Code's 70+ flags. The *underlying infra* is now broad (permission policy + plan mode, sandbox, background delegation, prompt caching, rate limiting, snapshots, hooks) — but little of it is exposed as CLI flags. Only `--sandbox` has been added as a mode flag; plan mode and named permission modes are still toggled in-session / via env vars rather than a CLI flag. Critical missing surface: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--plugin-dir`, `--remote-control`, `--channels`.

**Effort to close**: **Medium** (2–3 weeks) — map each flag to existing Zrb config and expose as CLI inputs on `LLMChatTask`.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich interactive TUI:
- Vim mode with NORMAL/INSERT/navigation; `/` reverse-search in NORMAL; `editorMode: "vim"`
- Voice input (`/mic`, `voice: {enabled, mode: "hold"/"push"}`, Option+M toggle)
- `!` bash prefix, `@` file mention with autocomplete, `/` command palette
- Multiline input (Shift+Enter, Option+Enter, `\`+Enter, Ctrl+J)
- Shortcuts: Shift+Tab (cycle permission modes), Ctrl+B (background agents), Ctrl+T (task list), Esc+Esc (force stop / rewind), Cmd/Ctrl+Enter (submit), Cmd/Ctrl+Shift+Enter (submit in plan mode), Cmd/Ctrl+K (new session), Cmd/Ctrl+L (clear)
- `/btw` side questions, image paste/drag-drop, artifact previews
- Fullscreen vs classic TUI, configurable status line, effort slider ("Faster"/"Smarter"), model picker, live thinking counter, color themes, footer link badges, wheel-scroll control

### Zrb

`prompt_toolkit`-based TUI (`src/zrb/llm/ui/`):
- Multi-line input (trailing `\` continuation, Ctrl+J newline)
- Command history with reverse search
- **`!` bash prefix** — `! cmd` / `/exec cmd` runs shell and injects output
- **`@` file mention** with autocomplete (`completion.py`)
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach`, `/model` (+ `small`/`multimodal` subcommands), `/yolo` (full + selective), `/plan` (toggle read-only mode), `/save` / `/load`, `/compress` / `/compact`, `>` / `/redirect`, `/copy`, `/btw`, `/rewind`
- **Shift+Tab interaction-mode cycling** ✅ (ADR-0075): `normal → auto-accept-edits → plan → normal`, mirroring Claude Code, with a persistent status-bar mode badge and an on-screen `shift+tab to cycle` hint. The new **auto-accept-edits** mode is selective YOLO over `{Write, Edit}` (files auto-approve; shell/delegation/fetch still prompt). On Termux (auto-detected via `CFG.IS_TERMUX`), a plain-Tab fallback also cycles since Termux can't distinguish Tab from Shift+Tab; focus toggle moves to Ctrl+K there.
- **`/copy` + clipboard `/redirect`** ✅: `/copy` copies the full transcript to clipboard (or a file with an arg); bare `/redirect` copies the last AI response. Uses `pyperclip` with an **OSC 52** terminal-escape fallback (works over SSH/tmux/screen). Output-pane copy strips ANSI styling.
- **Arrow-key selection UI for `AskUserQuestion`** ✅: ↑/↓ to move, Enter to confirm, Space to toggle in multi-select, plus a synthetic "✎ Type my own answer…" row (in-layout `Float`); web/`SimpleUI`/`MultiUI` fall back to type-a-number
- **Output-pane scrolling** ✅: mouse-wheel scrolls the output cursor, pauses auto-follow when scrolling up, resumes at the bottom — regardless of focused pane
- **Image clipboard paste** — Ctrl+V and Alt+V ✅
- **MultiUI** — broadcast to multiple channels (terminal + Telegram + web), first-response-wins
- **Animated thinking / confirmation indicators** ✅: adaptive refresh loop, debounced invalidation
- **Configurable colors** ✅: TUI mode-badge / info-bar / choice-widget styles via `ZRB_LLM_UI_STYLE_*`, plus remappable semantic CLI colors (warning/error/muted/highlight/info/success/todo) via `ZRB_CLI_COLOR_*` / `ZRB_CLI_STYLE_*` (`CLIStyleMixin`, ADR-0077); live-reread each call, theme example scripts in `examples/themes/`
- Git branch + dirty status, active worktree, pending todos, recent commits shown in (live) context

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has `!`, `@`, `/`, `/btw`, `/copy`, `/plan`, **Shift+Tab mode cycling**, image paste (incl. Alt+V), arrow-key choice UI, output-pane scrolling, MultiUI, animated status, and configurable theming. Still missing: Vim mode, voice input, background-agents shortcut (Ctrl+B — though background shell/delegation tools exist), task-list toggle (Ctrl+T), Esc+Esc rewind shortcut, git-history prompt suggestions, transcript viewer, in-TUI theme editor (theming is env-var only), session branching.

**Effort to close**: **Medium** (3–5 weeks): background-agents shortcut (~2–3d), task-list toggle (~2–3d), prompt suggestions (~1wk), Vim mode (2–3wk), in-TUI theme editor (1–2d), voice (2–3wk).

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~60): `/clear`, `/compact`, `/config` (incl. `key=value`), `/model`, `/effort`, `/fast`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/review`, `/rewind`, `/rewind-all`, `/branch`, `/worktree`, `/commit`, `/cd`, `/export`, `/search`, `/context`, `/help`, `/status`, `/doctor`, `/ide`, `/init`, `/skills`, `/reload-skills`, `/btw`, `/tasks`, `/background`, `/resume`, `/agents`, `/permissions`, `/add-dir`, `/security-review`, `/theme`, `/voice` (`/mic`), `/rename`, `/schedule`, `/loop`, `/usage`, `/max-budget-usd`, `/statusline`, `/sandbox`, `/workflows`, `/plugin`, `/reload-plugins`, `/team-onboarding`, `/feedback`, `/ultrareview`.

Bundled skills as commands: `/batch`, `/code-review` (`--fix`; replaced `/simplify`), `/claude-api`, `/debug`, `/loop`, `/deep-research`, `/run`, `/verify`. Custom skills become slash commands automatically. MCP prompts become `/mcp__<server>__<prompt>`. Argument interpolation (`$ARGUMENTS`, `$N`), dynamic context (`` !`command` ``), `--disable-slash-commands`.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1`; literal-`$` guard handled
- Skill-based commands via `get_skill_custom_command()`; skills become slash commands from `name` metadata
- Skill slash-command stubs delegate to core-skill companion files

Built-in slash commands: `/compress` / `/compact`, `/attach`, `/q` `/bye` `/quit` `/exit`, `/info` `/help`, `/save` `/load`, `/yolo [tools]`, `/plan` ✅ **NEW (v2.32.0)**, `>` `/redirect` (bare → clipboard), `/copy [file]` ✅ **NEW (v2.33.2)**, `!` `/exec`, `/model [small|multimodal] <name>`, `/btw`, `/rewind`. Command names are configurable via `ZRB_LLM_UI_COMMAND_*` env vars.

**`PRE_COMMAND` / `POST_COMMAND` hooks** ✅: hooks fire before/after slash-command dispatch; can block a command and **rewrite command arguments on-the-fly** via the hook result's `command_args`.

**Status**: 🟡 **Partially supported**

**Gap**: Core command infra plus skill-derived commands and command hooks; mode switching is handled via Shift+Tab cycling rather than discrete commands. Still missing: ~40 built-in management commands (`/clear`, `/config`, `/diff`, `/branch`, `/export`, `/usage`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/loop`, `/effort`, `/goal`, `/rename`, `/statusline`, `/sandbox`, `/workflows`), a `/mode` command for web/MultiUI mode parity, MCP prompts as commands, and bundled utility skills (`/batch`, `/loop`, `/verify`).

**Effort to close**: **Medium** (3–5 weeks). Most built-in commands wrap functionality that now exists (plan/mode cycling, sandbox, snapshots, todos, config-explain).

---

## 4. Memory System

### Claude Code

**CLAUDE.md files** (human-authored): managed/enterprise, user (`~/.claude/CLAUDE.md`), user-local, project (`./CLAUDE.md` / `./.claude/CLAUDE.md`), `CLAUDE.local.md` (gitignored), subdirectory lazy-load, `@import` (max 5 hops), `claudeMdExcludes`, `.claude/rules/` path-scoped (YAML `paths:`), `<!-- comments -->` stripping.

**Auto memory** (Claude-authored): notes in `.claude/memory/MEMORY.md` + topic files; first 200 lines / 25KB loaded at start; `/memory` command, `autoMemoryEnabled` / `autoMemoryDirectory`.

### Zrb

**CLAUDE.md / AGENTS.md / GEMINI.md / README.md / RTK.md auto-loading** (`src/zrb/llm/prompt/claude.py`):
- `project_context` section, default-on
- Search path: `~/.claude/` → filesystem root → … → CWD (all parents + CWD)
- Most-specific occurrence loaded up to `MAX_PROJECT_DOC_CHARS`; others listed for on-demand `Read`
- Per-`(path, mtime)` read caching ✅; RTK.md in search filenames ✅
- **Mandatory full `Read`** ✅: the mandate requires the agent to `Read` AGENTS.md / CLAUDE.md / README.md in full on the first code-touching turn (grep does not satisfy it); stub-detection auto-inlining was removed to avoid double-counting content already in `project_context`

**Journal system** (analog to auto memory):
- `LLM_JOURNAL_DIR` (`~/.zrb/journal/`); injected via `journal_mandate` section; read/write/search tools; `SearchJournal` tool; auto-approved for journal dir
- **Bidirectional journal graph** ✅: backlinks protocol; **file-relative** link convention (links resolve relative to the containing file)
- **Two-write-kind system** ✅: Insight vs Activity entries; `core-journaling` skill with activity-log template + `journal-lint.py`; protocol is now a decision table with explicit verify-before-logging
- **Granular control** ✅: `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` independent; reminder fires at `Stop` (ADR-0074)

**Status**: 🟡 **Partially supported**

**Gap**: CLAUDE.md auto-loading + a rich journal system. Missing: `CLAUDE.local.md`, `@import` chaining, `.claude/rules/` path-scoped YAML rules, `claudeMdExcludes`, `<!-- comments -->` stripping, subdirectory lazy-load, `/memory` interactive command, configurable char limit.

**Effort to close**: **Low–Medium** (1–2 weeks): `CLAUDE.local.md` (1d), comment stripping (1d), `@import` (2–3d), `.claude/rules/` (3–5d), `/memory` command (2–3d).

---

## 5. Hooks System

### Claude Code

**~31 hook events**: `SessionStart`, `Setup`, `SessionEnd`, `UserPromptSubmit`, `UserPromptExpansion`, `Stop`, `StopFailure`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`, `PermissionDenied`, `ExitPlanMode`, `SubagentStart`, `SubagentStop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `Notification`, `MessageDisplay`, `PreCompact`, `PostCompact`, `Elicitation`, `ElicitationResult`.

**5 handler types**: `command`, `http`, `mcp_tool`, `prompt`, `agent`.

**Capabilities**: universal `continue`/`stopReason`/`suppressOutput`/`systemMessage`; `additionalContext` injection; `decision: block`; PreToolUse `permissionDecision` (allow/deny/ask/defer) + `updatedInput`; PostToolUse `updatedToolOutput`; `exec`-form `args`; conditional `if`, `async`, `once`, `statusMessage`, `allowedHttpHookUrls`, `disableAllHooks`, `/hooks` UI, plugin monitors.

### Zrb

**16 hook events** (`src/zrb/llm/hook/types.py`):
- `SESSION_START`, `SESSION_END`, `USER_PROMPT_SUBMIT`
- `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE`
- `PERMISSION_REQUEST`, `NOTIFICATION`
- `STOP`, `STOP_FAILURE`
- `PRE_COMPACT`, `POST_COMPACT`
- `SUBAGENT_START`, `SUBAGENT_STOP`
- `PRE_COMMAND`, `POST_COMMAND` (Zrb-specific slash-command bracketing; closest CC analog is `UserPromptExpansion`)

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent). No `http`, no `mcp_tool`.

**7 matcher operators**: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`.

**Capabilities** (substantially upgraded toward Claude-Code parity — ADR-0066, ADR-0074):
- **Drop-in compatibility with Claude Code command hooks** ✅: payload is written to the hook's **stdin** as Claude-shaped JSON (with `tool_name`/`tool_input`/`tool_response` tool-identity fields, so tool-name matchers like `{"matcher":"Bash"}` work); `.claude/settings.json` / `settings.local.json` (home + project) are read as a hook source. Unmodified CC command hooks (e.g. peon-ping) run as-is.
- **Single `SafeToolsetWrapper.call_tool` chokepoint** ✅: **PreToolUse** fires for *every* tool call and honors `permissionDecision: deny/ask/defer`, exit-2 (reason read from stderr, Claude convention), and `updatedInput` (arg rewrite). **PostToolUse** honors `decision: block`, `updatedToolOutput`, and `additionalContext`. **PostToolUseFailure** fires on tool raise.
- **Turn control** ✅: **UserPromptSubmit** can block a prompt; **Stop** is a block-to-continue / turn-extension point (re-runs the agent with `reason`, capped at 8 blocks); `continue: false` halts the turn loop; **PreCompact** injects `additionalContext` and can block compaction.
- **`StopFailure` error classification** ✅: maps API errors to matcher tokens (`rate_limit`/`overloaded`/`server_error`/`context_length`/`authentication_failed`/`invalid_request`/`model_not_found`/`unknown`).
- **Claude tool-name aliases** ✅ for matchers: `Shell` matches `Bash`; `DelegateToAgent`/`DelegateToAgentBackground` match `Task`.
- `HookResult` factories: `block`, `allow`, `ask`, `deny`, `with_system_message(replace_response=…)`, `with_additional_context`; command-arg mutation (`command_args`) for slash commands.
- Async (fire-and-forget with concurrency semaphore + backlog ceiling) / sync with timeouts (`HOOKS_TIMEOUT`, default 30000ms); `ZRB_HOOKS_ENABLED` global kill-switch; `ZRB_HOOKS_DEBUG`.
- Config tiers (high→low): plugins → user-home (`~/.claude/`, `~/.zrb/`) → project dirs → `CFG.HOOKS_DIRS`; formats JSON / YAML / `.hook.py` (`register(manager)`) / `.claude/settings.json`; Claude-style env vars.
- **Uniform `add_hook_factory()` on both `LLMChatTask` and `LLMTask`** ✅ (ADR-0076), with leak-free per-task isolation; skill-frontmatter hook definitions; built-in journaling hook fires the reminder at `Stop`.
- **Hooks docs state CC incompatibilities explicitly** (the "100% compatible" claim was dropped).

**Status**: 🟡 **Partially supported** (capability parity is now high; lifecycle breadth is the remaining gap)

**Gap**: 16 of ~31 Claude Code events (~52% of events, but the *control* capabilities — block, deny, arg-rewrite, output-rewrite, turn-extension, additionalContext, drop-in CC compat — are now near-parity for the events that exist). Missing events: `Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `CwdChanged`, `FileChanged`, `ConfigChange`, `ExitPlanMode`, `Elicitation`/`ElicitationResult`, `WorktreeCreate`/`WorktreeRemove`, `TaskCreated`/`TaskCompleted`, `TeammateIdle`, `PermissionDenied`. Missing handler types: `http`, `mcp_tool` (explicitly out of scope per ADR-0074). Missing features: parallel / most-restrictive-merge execution (Zrb is sequential-by-priority), `if`/`once`/`statusMessage`, `allowedHttpHookUrls`, `/hooks` UI.

**Effort to close**: **Medium** (2.5–4 weeks): remaining events + fire points (~1wk; `ExitPlanMode`, `WorktreeCreate/Remove` have natural fire points now), `http` handler (2–3d), `if`/`once`/`statusMessage` (2–3d), `/hooks` UI (2–3d).

---

## 6. MCP (Model Context Protocol)

### Claude Code

Transports: `stdio`, `http`, `sse` (deprecated), `ws`. Config scopes: managed → user `~/.claude.json` → local project → `.mcp.json` → `--mcp-config`. `claude mcp add/list/remove/get/login/logout/serve`, auto-load from `.mcp.json`, live reconnect with backoff, OAuth 2.0 (auto + pre-configured), MCP prompts as `/mcp__…` commands, MCP tool search (`ToolSearch`, deferred tools, `ENABLE_TOOL_SEARCH`), MCP resource tools (`ListMcpResourcesTool`/`ReadMcpResourceTool`, `@server:…` references), subagent-scoped servers, idle timeout, elicitation, `/mcp` UI, registry/marketplace, claude.ai connectors, Channels notifications.

### Zrb

- **Transports**: `stdio` + **`http`/URL** ✅ (now via `fastmcp`; the prior `sse`-only assessment is outdated)
- Config: `mcp-config.json` (configurable via `MCP_CONFIG_FILE`), searched home → CWD hierarchy
- **Env var expansion** with `${VAR}` / `${VAR:-default}` (recursive over command/args/env)
- Retry via `LLM_MCP_MAX_RETRIES` (default 3)
- Loaded via `load_mcp_config()` in `LLMChatTask`

**Status**: 🟡 **Partially supported**

**Gap**: `stdio` + `http` work. Missing: `sse`/`ws` transports, `zrb mcp add` CLI, OAuth, MCP prompts → slash commands, MCP tool search / deferred loading (`ToolSearch`), MCP resource tools, subagent-scoped MCP, idle timeout, elicitation, `/mcp` UI, managed-only policy, registry/marketplace.

**Effort to close**: **Medium** (3–4 weeks): `ws`/`sse` (3–5d), `zrb mcp add` (2d), prompts→commands (3–4d), resources tools (2–3d), `/mcp` UI (2–3d), OAuth (1–2wk), deferred loading (1wk).

---

## 7. Subagents / Multi-Agent Orchestration

### Claude Code

Declarative subagents via markdown + YAML frontmatter (`.claude/agents/`, `~/.claude/agents/`, plugin `agents/`, `--agent`, `--teams`). Frontmatter: `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `requiredTools`, `skills`, `isolation` (`worktree`), `context` (`fork`), `agent`, `foreground`/`background`. Invocation: natural-language auto-delegation, `/agents`, `Agent(...)` tool call, forked-skill context. Foreground/background, nested subagents (up to 5 levels), background-permission surfacing in the main session, `/agents` UI, pinned worktrees. Built-ins: Explore, Plan, general-purpose.

### Zrb

**File-based agents** (`.agent.md` / `AGENT.md` / `.agent.py` / plain `.md` in `agents/`):
- Frontmatter: `name`, `description`, `model`, `tools`, **`inherit_sections`** (🔵 Zrb-specific — sub-agent inherits named PromptManager sections from the main agent)
- Discovery from search dirs (home → project → plugins → builtin); built-in agents gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS` (ADR-0069)
- Built-in agents (`src/zrb/llm_plugin/agents/`): `generalist`, `researcher`, `code-reviewer`

**Delegation tools**:
- `create_delegate_to_agent_tool()` → `DelegateToAgent(...)` — **now handles both single and parallel** delegation: an optional `tasks: list[dict]` argument fans out concurrently with a shared UI lock + rate limiter (the separate `DelegateToAgentsParallel` tool was folded in — ADR-0070), scope-clamped via a DELIVERABLE/NON-GOALS/TASK/CONTEXT envelope
- **Background delegation** ✅: `DelegateToAgentBackground` + `GetDelegationResult` (`tool/delegate_background.py`) — fire-and-forget detached `asyncio` tasks; inherit parent context (UI, yolo, policy, sandbox, approval channel, agent mode) via ContextVar snapshot; approvals route through the parent UI's confirmation queue. `GetDelegationResult` supports a **bounded `wait=`/`kill=`** (blocks up to `min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)`, default 300s — ADR-0072), collapsing repeated polling into one call. Plan-mode parents cannot start one (DELEGATE denied by the policy gate).
- `SubAgentManager` (nested `manager/` package) with lazy filesystem loading; uses `LLMConfig.resolve_model()`
- **YOLO inheritance** ✅; **tool-guidance propagation** ✅; **permission-policy + sandbox-policy inheritance** ✅ (sub-agents inherit the parent's `current_permission_policy` and `current_sandbox_policy` via ContextVar)
- **`SubagentStart` / `SubagentStop` hooks** ✅ fire on the parent run's hook manager (`current_hook_manager` ContextVar)

**Status**: 🟡 **Partially supported**

**Gap**: File-based definitions and delegation work, with **foreground, parallel, and background** modes, full policy/sandbox inheritance, and subagent lifecycle hooks. Still no natural-language auto-delegation, no `/agents` UI, no background-session dashboard, no nested-to-5-levels orchestration. Frontmatter lacks `maxTurns`, `mcpServers`, `hooks`, `isolation: worktree`, `effort`, `disallowedTools`, `foreground`/`background`. No persistent agent memory directory, no managed subagents.

**Effort to close**: **High** (4–6 weeks): auto-delegation (3–4d), `/agents` UI (3–4d), per-agent permissionMode/maxTurns (~1wk — per-agent policy is expressible via the policy engine), subagent-scoped MCP (~1wk), worktree isolation (1–2wk).

---

## 8. Agent Teams & Dynamic Workflows

### Claude Code

- **Agent Teams** (now enabled — one implicit team per session): inter-agent `SendMessage`; shared task list (`/tasks`); display modes (`in-process`/`auto`/`tmux`/`iterm2` via `--teammate-mode`); nested subagents up to 5 levels; background isolation in separate worktrees; hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`).
- **Dynamic Workflows**: orchestrate dozens-to-hundreds of background agents via the `Workflow` tool; deterministic JS scripts that fan out / pipeline subagents; structured-output schemas; budget-aware loops; `/workflows` monitoring UI (pause/resume/stop/restart); bundled `/deep-research`; saveable run scripts.

### Zrb

`DelegateToAgent` with an optional `tasks` list (concurrent multi-agent, aggregated results, shared rate limiter + UI lock, per-agent error handling) plus `DelegateToAgentBackground` / `GetDelegationResult` (fire-and-forget background sub-agents with bounded-wait polling). No persistent team lifecycle, no inter-agent messaging, no shared task list with dependencies, no script-orchestrated fan-out to hundreds of agents, no workflow-monitoring UI.

**Status**: ❌ **Not supported** (parallel + background delegation exist, but not teams or scripted dynamic workflows)

**Gap**: Zrb's delegation is single tool calls returning aggregated/polled results — not persistent coordinated agents nor a deterministic orchestration runtime. Background delegation is a partial building block toward the dynamic-workflow side. Missing: team lifecycle, inter-agent messaging, shared task list with dependencies, tmux/iterm2 display, `SendMessage`, JS dynamic-workflow scripting + `/workflows` UI + the `Workflow` tool.

**Effort to close**: **Very High** (8–12 weeks) — fundamentally different architecture. Zrb's existing DAG task engine + parallel delegate are partial building blocks for the dynamic-workflow side.

---

## 9. Skills System

### Claude Code

File-based skills (`.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md`). Scopes: managed > personal > project > plugin. Frontmatter: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context` (fork), `agent`, `hooks`, `paths`, `shell` (`bash`/`powershell`). Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$name`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`, `${CLAUDE_EFFORT}`. Dynamic context `` !`command` ``, forked subagent context, `paths:` glob activation, nested/monorepo auto-discovery, hotreload, `disableSkillShellExecution`, `/reload-skills`. Bundled: `/batch`, `/claude-api`, `/debug`, `/loop`, `/code-review`, `/deep-research`, `/run`, `/verify`. Follows the [Agent Skills](https://agentskills.io) standard.

### Zrb

Comprehensive skill system (`src/zrb/llm/skill/`):
- File types: `.skill.md`, `.skill.py`, `SKILL.md`, `SKILL.py`
- Scopes: default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`)
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, **`hooks`** ✅ (skill-defined hooks supported)
- **Companion-file discovery** ✅: `ActivateSkill` returns the skill directory path + grouped companion-file listing; `discover_companion_files()` + `format_companion_file_lines()`
- Lazy scan + content caching; factory-function skills; `get_skill_custom_command()`

**Built-in plugin** (`src/zrb/llm_plugin/`) — three governable categories (ADR-0069):
- **`core_skills/`** — 5 always-on `core-*` methodology hubs (`core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`), no toggle
- **`skills/`** — utility skills gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS` (`debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`)
- **`agents/`** — sub-agents gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`
- `core-coding` companions: `languages/` (python, typescript, go, rust, java, ruby, php) + `workflows/` (testing, debug, refactor, review) + an observability companion (k8s/coredump/Grafana/Prometheus/Elasticsearch)
- Skill catalogue is folded into the `mandate` prompt section via `{CORE_SKILLS}`/`{AVAILABLE_SKILLS}`/`{PREACTIVATED_SKILLS}` placeholders (ADR-0079); core skills listed separately from model-invocable skills; activation is auto-approved, silent, once per session/domain

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` / `${CLAUDE_EFFORT}` (Zrb has no effort concept), `disallowed-tools`, `paths:` glob activation, `shell` field, `` !`command` `` dynamic injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitutions, nested/hotreload discovery, bundled utility skills (`/batch`, `/loop`, `/verify`).

**Effort to close**: **Low** (1–2 weeks): `paths`/`shell`/`disallowed-tools` frontmatter (2–3d), `` !`command` `` preprocessing (1–2d), `$CLAUDE_SESSION_ID`/`$CLAUDE_SKILL_DIR` (1d), `/loop` bundled skill (2–3d).

---

## 10. Permission Modes & Tool Approval

### Claude Code

**Permission modes** (cycle via Shift+Tab): `default` (ask), `acceptEdits`, `plan`, `auto` (background safety classifier), `dontAsk`, `bypassPermissions`. `--permission-mode`; `defaultMode`. Permission rules `Tool`/`Tool(specifier)`/globs/domains/MCP patterns/`Tool(param:value)` (`Bash(npm run *)`, `Read(//path/**)`, `WebFetch(domain:…)`, `Agent(model:opus)`); evaluation deny > ask > allow; config managed > CLI > local > project > user; destructive-git blocking; `PermissionRequest`/`PermissionDenied` hooks.

### Zrb

**Permission policy engine** ✅ (ADR-0049–0057, 0067, 0078) — `src/zrb/llm/permission/`:
- **Capability tags** (`capability.py`): `READ`, `EDIT`, `EXECUTE`, `NETWORK`, `DELEGATE`, `META`, `UNKNOWN` (safe-by-default). Tools tagged centrally in `common_tools.py`.
- **Rules** (`policy.py`): ordered, **first-match-wins** `Rule(key, action, arg_pattern)` where `key` ∈ {tool name, capability value, `"*"`}, `action` ∈ {`allow`, `ask`, `deny`}, and `arg_pattern` is an `fnmatch` glob over salient args (`path`/`file_path`/`command`/`url`/`agent_name`/…). `PermissionPolicy.decide(...)` resolves exact tool → capability → `"*"` → None.
- **Plan mode** ✅: `AgentMode` enum (`BUILD`/`PLAN`); `EnterPlanMode`/`ExitPlanMode` tools (tagged `META`). The preset **`PLAN_MODE_POLICY`** allows READ/META/NETWORK, denies EDIT/EXECUTE/DELEGATE, and asks before `ExitPlanMode` — enforced by `_permission_gate` in `agent/common.py`. `AgentModeState` is a ContextVar-held holder so per-tool asyncio tasks observe mode changes; `enter/exit_agent_mode_scope` isolates concurrent runs.
- **`auto-accept-edits` mode** ✅ (ADR-0075): selective YOLO over `{Write, Edit}` (files auto-approve; shell/delegation/fetch still prompt). One of the three Shift+Tab-cycled interaction modes (`normal → auto-accept-edits → plan`, §2).
- **YOLO as a policy** (`from_yolo`): `True` → `Rule("*", allow)`; `False` → `Rule("*", ask)`; tool-name set → per-tool `allow` + `"*"` ask fallback. Full + selective YOLO propagate to sub-agents.
- **First-class `permissions=` / `sandbox=` on `LLMChatTask`** ✅ (ADR-0078): symmetric with `LLMTask`, read/write properties (replaces the old hook-factory workaround). Precedence: explicit arg > `ZRB_LLM_PERMISSIONS` env > ambient ContextVar (sub-agent inheritance); plan mode overrides all. Exported `PermissionPolicyInput` / `SandboxInput` types.
- **Approval precedence chain** (`permission_policy → tool_policy → yolo`): `deny` stops at the gate; `allow` bypasses lower checks. `DelegateToAgent`'s roster is filtered by the active policy at render time. A `PreToolUse` hook's `permissionDecision: ask` can force the prompt even over ALLOW/YOLO.
- **Non-interactive resolution** ✅ (ADR-0067): under `--interactive false`, hard-ASK gates resolve deterministically (`ExitPlanMode` auto-approves; others deny with a re-run hint).
- **Auto-approve predicates** (`tool_call/tool_policy/`): `approve_if_path_inside_cwd`, `…inside_journal_dir`, `…inside_skill_or_plugin_dir`, `…mv_inside_journal_dir`; per-tool validation; **`bash_safe_command_policy`** auto-approves read-only commands and rejects dangerous metacharacters (incl. bare `&`, newlines/CR, `env`-prefixed commands).
- `ApprovalChannel` + `MultiplexApprovalChannel` (first-response-wins); override tool args at approval time (`ApprovalResult.override_args`).

**Status**: 🟡 **Partially supported** (strong)

**Gap**: Zrb now has a **named-mode + rule engine** — `PLAN` (read-only), `auto-accept-edits`, `BUILD`, and YOLO (full/selective) expressed as `PermissionPolicy`, **Shift+Tab cycling** over them, capability tags, arg-glob rules, first-match precedence, a single approval chain, and first-class `permissions=` constructor args. Still missing vs Claude Code: a dedicated `dontAsk`/`bypassPermissions` preset, `--permission-mode` CLI flag, domain-pattern rules for web tools (`WebFetch(domain:…)`) and `Tool(param:value)` parameter matching, a `hard_deny` unconditional tier, destructive-git auto-blocking, and an admin-managed policy layer.

**Effort to close**: **Low–Medium** (1.5–2.5 weeks): `dontAsk`/`bypassPermissions` presets (1–2d), `--permission-mode` flag (1–2d), domain-pattern / param arg matching (2–3d), `hard_deny` tier (2d), managed policy layer (depends on §11 JSON settings).

---

## 11. Settings & Configuration System

### Claude Code

4 scopes: managed > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`). JSON schema for autocomplete. `/config` tabbed UI + `/config key=value`. Global `~/.claude.json`. `--settings` JSON override, `--setting-sources`, `--safe-mode`. Server-managed settings (claude.ai admin, MDM/OS policies, `managed-settings.json`).

### Zrb

**Single config source**: `CFG` singleton (`src/zrb/config/`), env vars (prefix `ZRB_`), composed from mixins under `mixins/`: `foundation`, `web`, `llm_core`, `llm_ui` (+ `llm_ui_commands`/`llm_ui_runtime`/`llm_ui_styles`), `llm_limits`, `llm_content`, `llm_prompt`, `llm_search`, `llm_sandbox`, `cli_style`, `rag`, `internet_search`, `hooks`, `task_runtime`. `CFG.FOO` access stays flat regardless of owning mixin.

- **`EnvField` data descriptor**: replaced 700+ lines of getter/setter/cast boilerplate; empty env var treated as unset; `contextvars.py` is the canonical ContextVar index. Now also supports **`fallback`** (graceful degradation on cast failure), **`transform`** (sibling-config-dependent post-read transforms), and **`no_prefix=True`** (reads/writes bare env names like `BRAVE_API_KEY`, `SERPAPI_KEY`). Mass migration brought all content/foundation/internet-search/UI knobs under `EnvField`.
- **`zrb config explain`** ✅: a builtin task that lists every `EnvField`-backed knob as a markdown table (env var, current value, description), with optional `--keyword` filter.
- **Boolean naming convention codified** (ADR-0073): `<NS>_ENABLED` for namespace master switches, verb-first (`ENABLE_`/`SHOW_`/…) for standalone toggles. (E.g. `WEB_ENABLE_AUTH` → `WEB_AUTH_ENABLED`.)
- All magic numbers configurable (timeouts/intervals/sizes/retries)
- **Tool Guidance System**: `ToolGuidance` dataclass, `add_tool_guidance()` / `add_tool_guidance_factory()`; consolidated into `apply_common_tools()` shared across `LLMChatTask`/`LLMTask`/`SubAgentManager`
- **Config-positioned custom prompt sections** (ADR-0061): a non-built-in name in `include_sections` resolves as a custom section (built-in > registered provider > markdown file); `register_section(name, provider)`; empty/misspelled names log a warning at compose time
- **Consolidated model pipeline**: `LLMConfig.resolve_model()` single entry point; per-model capability registry

**Status**: 🟡 **Partially supported**

**Gap**: Env-var only — no JSON settings files, no layered scopes, no `/config` UI, no JSON schema, no managed/enterprise policy layer. (`config explain` improves discoverability but does not add file-based settings.)

**Effort to close**: **Medium** (2–3 weeks): JSON settings loader + scope hierarchy (1wk), merge with env vars (2d), JSON schema (2–3d), `/config` UI (1wk).

---

## 12. Built-in Tools

### Claude Code (~45 tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` (explicit `start_line`/`end_line`, range validation) |
| `Write` | ✅ `write_file` (post-write LSP/static diagnostics) |
| `Edit` | ✅ `replace_in_file` (fuzzy match + post-edit diagnostics; rejects empty `old_text`) |
| `Bash` | ✅ `run_bash_command` + `run_shell_command` (`Shell`, `CFG.SHELL`); `background=True` for detached jobs; tail-truncates and dumps full output to a recoverable temp log |
| `PowerShell` | 🟡 `Shell` resolves to `pwsh`/`powershell` on Windows; no dedicated PowerShell tool |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` (ripgrep acceleration; char-budget bound) |
| `Agent` (spawn subagent) | 🟡 `DelegateToAgent` (single + parallel via `tasks`) / `DelegateToAgentBackground` + `GetDelegationResult` |
| `WebFetch` | ✅ `open_web_page` (`OpenWebPage`) |
| `WebSearch` | ✅ `search_internet` (Google News RSS default, SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | ✅ `AskUserQuestion` — intrinsic auto-approval (ADR-0062); arrow-key selection UI |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full suite incl. `LspRenameSymbol` (working with pyright/pylsp/gopls — §23) |
| `Monitor` (stream background events) | 🟡 `MonitorProcess` (poll/kill background shell) — process-scoped, not a general event stream |
| `EnterPlanMode` / `ExitPlanMode` | ✅ Real plan-mode enforcement via the policy engine (§10) |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking) |
| `TaskCreate/Get/List/Update/Stop` | 🟡 `write_todos`/`get_todos` (system-context integration; `update`/`clear` folded into `write_todos`) |
| `CronCreate/Delete/List` | ❌ Not LLM tools (Zrb `Scheduler` exists at task level) |
| `EnterPlanMode` / `ExitPlanMode` | ✅ **`EnterPlanMode`/`ExitPlanMode` with enforced read-only policy** — **NEW (v2.32.0, ADR-0051)** |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking) |
| `Monitor` (stream background events) | 🟡 `MonitorProcess` polls background shell processes; no unified event stream across task types |
| `SendMessage` (agent teams) | ❌ Teams not implemented |
| `Workflow` (script-orchestrated fan-out — v2.1.154) | ❌ Not implemented (`DelegateToAgentBackground` is a partial building block) |
| `Artifact` (publish live web page to claude.ai) | ❌ Not implemented (Zrb has a local web UI instead) |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` / `ReadMcpResourceTool` | ❌ Not implemented |
| `SendMessage` / Agent Teams | ❌ Teams not implemented |
| `Workflow` (dynamic workflows) | ❌ Not implemented |
| `RemoteTrigger` / `PushNotification` / `ScheduleWakeup` | ❌ Not implemented |
| `Skill` (invoke skills) | ✅ `ActivateSkill` (returns companion files) |
| `Artifact` (publish HTML/MD) | ❌ Not implemented |

**Background execution** ✅: `Shell`/`Bash` take `background=True` (the old standalone `ShellBackground` was folded in — ADR-0071) and route through the normal approval policy; `MonitorProcess` polls/kills the detached process. Cross-platform via `start_new_session=True` + `psutil` teardown.

**Tool-output truncation backstop** ✅ (ADR-0052): global `LLM_MAX_TOOL_RESULT_CHARS` (default 100k) truncates model-facing `content` (directional head/tail with a re-fetch hint) while preserving structured `return_value` (`agent/truncate.py`).

**Post-write/edit diagnostics** ✅ (`tool/post_write_check.py`): after `write_file`/`replace_in_file`, runs LSP `get_diagnostics()` + static checks (Python `ast.parse` + `pyflakes`); appends a `[DIAGNOSTIC]` block. File-tool errors attach `[SYSTEM SUGGESTION]` recovery hints.

**Additional Zrb tools not in Claude Code** 🔵:
- `RM` (`remove_file`), `MV` (`move_file`) — **NEW (v2.24.0)**
- `SearchJournal` — **NEW (v2.24.0)**
- `AnalyzeFile` (AST-based), `AnalyzeCode` (LLM sub-agent analysis)
- `create_rag_from_directory` (ChromaDB embeddings, semantic search)
- `List{Root}Tasks` / `Run{Root}Task` (discover + run any Zrb task as a tool)
- A read-only `git` tool used by the changelog generator (§17)
- Tool Guidance System (per-tool hints into the system prompt)
- A suite of developer-utility builtin task groups: `hash`, `time`, `url`, `json` (dotted-path get, yaml convert), `case`, `cron parse`, `hex`, `number` (base conversion), `random` (password/token via `secrets`), plus `jwt`, `http request`, `base64`, `ulid`

**Gap**: Core file/shell/web/worktree/LSP/todo/plan-mode/background tools well-covered. Missing: `NotebookEdit`, `CronCreate/Delete/List`, general `Monitor` event stream, `ToolSearch`, MCP resource tools, `SendMessage`/Teams, `Workflow`, `RemoteTrigger`/`PushNotification`/`ScheduleWakeup`, `Artifact`, dedicated `PowerShell` tool.

**Gap**: Core file/shell/web/worktree/LSP/todo tools well-covered; background shell, plan-mode tools, and background delegation all present. Missing: `NotebookEdit`, `CronCreate/Delete/List`/`ScheduleWakeup`, unified `Monitor` event stream, `SendMessage` (teams), the `Workflow` orchestration tool, `Artifact`, `ToolSearch` (deferred tools), MCP resource tools, `RemoteTrigger`/`PushNotification`.

**Effort to close**: **Medium** (2–3 weeks): `NotebookEdit` (3–4d), Cron tools (3–4d, reuse `Scheduler`), `ToolSearch` deferred loading (1wk), unified `Monitor` (2–3d).

---

## 13. IDE Integrations

### Claude Code

VS Code extension (panel/sidebar/tab, inline diff accept/reject, `@`-mention, selection context, drag attachments, multi-conversation tabs, IDE MCP server, auto-install). JetBrains plugin (IntelliJ/PyCharm/WebStorm, interactive diff, Shift+Tab cycling). Desktop app (macOS/Windows, visual diff, side-by-side sessions, Dispatch, scheduled tasks, push notifications). Chrome extension (web testing + screenshots). `--ide`, `/teleport` to/from web.

### Zrb

**Web UI** (FastAPI-based) — browser chat at `http://localhost:21213`, session persistence, model switching, YOLO toggle, JWT auth, SSE streaming, ChatGPT-like layout, browser tool approval (edit args on the fly), HTTP Chat API, Jinja2 templates + local mermaid.js. No VS Code / JetBrains / Desktop / Chrome integration.

**Status**: ❌ **Not supported** (IDE integrations); 🟡 Web UI is a different paradigm.

**Effort to close**: **Very High** (3–6 months for full parity).

---

## 14. Session Management & Checkpointing

### Claude Code

Checkpointing: auto checkpoint before every edit and per prompt (`fileCheckpointingEnabled`); 30-day retention; Esc+Esc rewind menu; `/rewind`/`/rewind-all`; `/branch`/`--fork-session`. Sessions per cwd; `--continue`/`-c`, `--resume`/`-r` (by id/name/picker), `--name`/`-n`, `--session-id`, `/rename`, `--from-pr`, `--no-session-persistence`, `/export`, `/search`, `/usage` stats, resumable background sessions, `/teleport`.

### Zrb

- `FileHistoryManager` → JSON history (`~/.zrb/history/{name}.json`); named sessions via `--session`
- **In-RAM cache with LRU cap** ✅: `_MAX_CACHED_CONVERSATIONS = 8` with dirty-entry tracking
- **Backup rotation** ✅: `LLM_HISTORY_BACKUP_RETAIN` (default 3); excludes the live file from rotation; lexicographic sort
- `NoSaveHistoryManager` for ephemeral sessions; `/load` shows history with icons; fuzzy session search
- **SQLite-backed sessions** via `ChatSessionManager` for the web UI
- **Snapshot / rewind** ✅: `SnapshotManager` (shadow git repos); `/rewind` picker; 3 restore modes; incremental sync + `DEFAULT_IGNORE_DIRS`; `LLM_ENABLE_REWIND`, `LLM_SNAPSHOT_DIR`
- **Escape preserves history** ✅: interrupting a response saves the user message + `[SYSTEM: Response was interrupted]`
- **Partial-run retry context** ✅: on Escape/unrecoverable error, completed tool calls + results are captured (`PartialRunAccumulator`) and appended as a `[SYSTEM: PREVIOUS ATTEMPT FAILED]` summary so the next turn continues instead of repeating
- **`/copy` transcript export** ✅: clipboard or file; full (untruncated) export mode; `extract_last_response_text()` recovers the last response from replayed history

**Status**: 🟡 **Partially supported**

**Gap**: Rewind/snapshot + ephemeral sessions + interrupt-preserving + partial-run retry + transcript copy/export. Missing: rewind is opt-in (not automatic); no Esc+Esc shortcut; no session branching/forking; no resume-by-id picker; no startup `--name`; no `/export` (but `/copy <file>` partially covers it); no session stats / `/usage`; no `--from-pr`; no `/search` over history.

**Effort to close**: **Medium** (2–3 weeks): enable rewind by default (1d), Esc+Esc (1–2d), branching (1wk), resume picker (2–3d), `--name` (1d), stats (2–3d).

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, subscription) with `--remote`/`--teleport` bridging.

### Zrb

🔵 **Zrb-only feature**: FastAPI web UI — browser chat (`http://localhost:21213`), SSE streaming (incl. `todo_progress` events), SQLite session persistence, model switching, YOLO toggle, JWT auth (guest + admin), SSL/TLS, task browsing/execution, REST API (`/api/v1/chat/`), ChatGPT-like layout, `HTTPChatApprovalChannel` (browser tool approval with edit-args), Jinja2 templates + local mermaid.js.

- **Security hardening** ✅: JWT `type == "access"` claim enforced; `Secure`+`SameSite=Lax`+`HttpOnly` cookies; constant-time `is_password_match`; `shlex.quote` on task args; `WEB_AUTH_ENABLED` master switch
- **Chat-API authorization** ✅: all chat API routes enforce the `can_access_task` gate (authenticated-but-unauthorized users cannot reach tool/shell execution)
- **Concurrent-session isolation** ✅: `ChatSessionManager.task_lock`; per-run mode/policy ContextVar isolation

**Status**: 🔵 **Zrb advantage** — local web UI not present in the Claude Code CLI.

---

## 16. Auto Mode (Safety Classifier)

### Claude Code

Background classifier reviews each action before execution; sees user messages + tool calls (not Claude's text — anti-injection); default block (download+execute, prod deploys, mass deletes, IAM) / allow (local file ops, deps, read-only HTTP); subagent-spawn evaluation; fallback to prompting; `auto-mode` config; `useAutoModeDuringPlan`. Research preview on Anthropic (claude.ai/SDK/API); not yet on Bedrock/Vertex/Foundry.

### Zrb

No equivalent LLM-based safety classifier. The **permission policy engine** (§10) + `bash_safe_command_policy` metacharacter rejection + the **sandbox** (§18) provide rule-based and OS-level containment, but there is no model-in-the-loop pre-action classifier that reasons about intent. The `StopFailure` error-classification taxonomy (§5) provides a hookable substrate for retry/escalation logic but is not a pre-action classifier.

**Status**: ❌ **Not supported**

**Effort to close**: **High** (4–6 weeks): pre-action classification hook (1wk), default block/allow rules (1wk), configurable rules layered onto the existing policy engine (1wk), fallback counter (2d), integration with permission modes (1wk). The policy engine and sandbox provide natural enforcement hooks for a classifier's verdicts.

---

## 17. GitHub / CI/CD Integration

### Claude Code

GitHub Actions (`@claude` mention triggers), GitLab CI, GitHub Code Review bot, `/install-github-app`, `--from-pr`, `/pr-comments`, PR status footer, `/security-review`, Slack integration, `/batch` (parallel worktree agents each opening a PR), **`claude ultrareview`** (non-interactive CI review — new), `/code-review --fix`.

### Zrb

🔵 **Zrb-only**: task-automation system with Git utilities (`src/zrb/builtin/git`), `run_shell_command` can drive `gh`/`glab`/`git` (both `gh` and the GitLab `glab` CLI are now detected), RAG tools, `review` built-in skill (structured code + security review), `git-summary` skill (drafts only; commit/PR on explicit request).

- **`zrb git changelog generate`** ✅: generates one changelog file per git tag via the LLM (incremental — skips tags with existing files), configurable regex/sort/template, `--stat`-first diff strategy skipping lock files, handles the initial release via the empty-tree object, graceful degradation. The LLM is given a read-only `git` tool (diff/log/show/shortlog/tag).

A CI workflow exists for Zrb's own tests (`.github/workflows/test.yml`), but there is no native GitHub app, CI triggers, PR-comment triggers, Slack, or Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Effort to close**: **High** (4–8 weeks): GitHub Actions template calling `zrb llm chat -p` (1–2d), GitLab template (1d), PR footer via `gh` (1–2d), `/pr-comments` (2–3d), `/security-review` adapt from `review` skill (1d), GitHub webhook → Zrb trigger (2–3wk), Slack bot (2–3wk).

---

## 18. Sandboxing

### Claude Code

OS-level Bash sandboxing (macOS Seatbelt, Linux/WSL bubblewrap): `sandbox.enabled`, `excludedCommands`, `allowUnsandboxedCommands`, `filesystem.allowWrite/allowRead/denyWrite/denyRead`, `network.allowedDomains/deniedDomains/proxy`, `credentials` (credential-file blocking), `allowAppleEvents`, managed-read/domain-only enforcement, weaker-isolation toggles. `/sandbox` command; `autoAllowBashIfSandboxed`. PowerShell tool default-on for Windows.

### Zrb

🔵 **Opt-in filesystem + OS sandbox** ✅ (ADR-0063, ADR-0078) — `src/zrb/llm/sandbox/`:
- **`SandboxPolicy`** (frozen dataclass): `enabled`, `writable_paths` (empty = auto: cwd + `/tmp`), `deny_read_paths` (defaults to credential stores — `~/.ssh`, `~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.gnupg`, `~/.netrc`, `~/.npmrc`, `~/.git-credentials`, `~/Library/Keychains`, …), `os_shell` (`auto`/`off`), `fallback` (`warn`/`deny`), `allow_escape`.
- **Two enforcement layers**:
  1. **Python-level FS gate** (`_sandbox_gate` in `agent/common.py`, right after `_permission_gate`): blocks writes outside writable roots (EDIT/UNKNOWN tools) and reads of credential dirs (all tools) via `check_read()`/`check_write()` (`fs_policy.py`). Windows `normcase` + cross-drive blocking. (No per-call escape on file tools — sandbox escape is Bash-only by design.)
  2. **OS-level shell wrapper** for `Shell`/`Bash` (`os_sandbox.py`): macOS `sandbox-exec` + generated SBPL (`seatbelt.py`, last-match-wins); Linux `bwrap` (`bwrap.py`, ro-bind root → writable binds → tmpfs/`/dev/null` deny-read masks). Network stays open in v1.
- **First-class plumbing** ✅: `--sandbox` CLI input (§1); `LLMChatTask(sandbox=…)` and `LLMTask(sandbox=…)` constructor args + read/write properties (ADR-0078); `run_agent(sandbox_policy=…)`; `current_sandbox_policy` ContextVar (sub-agent inheritance). Config (`LLMSandboxMixin`): `ZRB_LLM_SANDBOX_ENABLED` (default `false`), `_OS_SHELL`, `_WRITABLE_PATHS`, `_DENY_READ_PATHS`, `_FALLBACK`, `_ALLOW_ESCAPE`.
- Where no OS mechanism exists (Windows, Linux without bwrap), `fallback=warn` runs unsandboxed with a visible warning, `deny` refuses — never silent.
- **Escape hatch**: `dangerously_skip_sandbox` arg on shell tools — never auto-approved, blockable via `ALLOW_ESCAPE=false`, blocked at both layers, emits a `[NOTE]` to the model.

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has FS-level (read+write) sandboxing on macOS (Seatbelt) and Linux (bwrap) plus credential-read denial, a `--sandbox` flag, first-class constructor args, and a safe fallback. Missing vs Claude Code: **network sandboxing** (allowed/denied domains, proxy — Zrb keeps network open in v1), `excludedCommands`/`allowUnsandboxedCommands` granularity, managed-read/domain-only enforcement, weaker-isolation toggles, a `/sandbox` UI command, and a dedicated Windows mechanism.

**Effort to close**: **Medium** (2–3 weeks): network filtering via proxy or bwrap `--unshare-net` + allowlist (1–2wk), per-command exclusions (2–3d), Windows AppContainer/Job-object research (open-ended).

---

## 19. Remote & Cloud Sessions

### Claude Code

`--remote` (new web session), `--teleport`, `--remote-control`/`--rc`, `claude remote-control`. Control from claude.ai/app; Channels (Telegram/Discord/iMessage/webhooks via MCP channel plugins); Dispatch (phone → Desktop); cloud sessions across devices; Remote Control MCP connectors with OAuth.

### Zrb

🔵 **Zrb-only**: built-in web server (`zrb server start`), REST API, JWT, SSL/TLS. **MultiUI** (broadcast to terminal + Telegram + web; first-response-wins). **MultiplexApprovalChannel** (route approvals to multiple channels). No cloud sessions, Remote Control protocol, Channels plugin system, Dispatch, or multi-device sync.

**Status**: 🟡 **Different approach** — local web server + multi-channel vs cloud infra.

**Gap**: True cloud sessions need cloud infra. Channels (Telegram/Discord/iMessage/webhooks) partially bridged by MultiUI/MultiplexApprovalChannel + HTTP API but no drop-in Channels system.

**Effort to close**: **Low–Medium** for remote API (web server already provides this); **Medium** (2–3 weeks) for WebSocket remote control + channel plugins; **Very High** for true cloud sessions.

---

## 20. Plugins System

### Claude Code

Install from marketplace or local dir; `--plugin-dir`, `--plugin-url`. Structure: `hooks/`, `agents/`, `skills/`, `mcp.json`, output styles, `${CLAUDE_PLUGIN_DATA}`. `.claude-plugin/plugin.json` manifest; `defaultEnabled`; dependency enforcement. `/plugin install/list/disable/enable`, `/plugin marketplace add/remove`, `/reload-plugins`. Plugins auto-load from `.claude/skills/`. Marketplaces, channel plugins.

### Zrb

**Skill/Agent/Hook plugin dirs** (closest analog): skills/agents/hooks loaded from multiple dirs; `CFG.LLM_PLUGIN_DIRS` (tilde-expanded); plugin dirs discovered via `.claude-plugin/plugin.json` manifest (`scan_plugin_dirs`); MCP config from multiple locations; `add_hook_factory()`; built-in plugin split into governable `core_skills`/`skills`/`agents` categories (ADR-0069). No formal packaging/marketplace, no `zrb plugin` command, no lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (skills + agents + hooks + MCP, but no packaging/marketplace)

**Effort to close**: **Medium** (3–4 weeks): plugin package format (3–4d), installer `zrb plugin add` (1wk), full plugin-dir scanning (1wk), `/reload-plugins` (2d).

---

## 21. Rate Limiting & Budget Control

### Claude Code

`--max-budget-usd`, `/usage` (merged cost+stats; per-skill/agent/plugin/MCP tracking), rate-limit status in footer, `--fallback-model` (chain), per-turn token usage.

### Zrb

🔵 **Zrb advantage**: sophisticated rate limiting + retry:
- `LLMLimiter`: requests/min + tokens/min (`ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`); shared across sub-agents; a configured limiter of `0` blocks correctly
- **`fit_context_window` O(n)**: ~46× faster at 320 turns
- **Transient provider error retry**: exponential backoff for HTTP 429/5xx, honors `Retry-After`, caps at `LLM_API_MAX_WAIT`, `LLM_API_MAX_RETRIES`; `StopFailure` hook exposes a classified error type (`rate_limit`/`overloaded`/…)
- Summarizer threshold accounts for system-prompt tokens

Missing: per-session budget cap, `/usage`/`/cost`, cumulative spend, fallback model on overload.

**Status**: 🟡 **Partially supported** (rate limiting + retry exceed Claude Code; budget/cost UI missing)

**Effort to close**: **Low** (3–5 days): cumulative token/cost tracking (2d), `--max-budget` input (1d), `/cost` command (1d), fallback model in CFG (1d).

---

## 22. Platform Support

### Claude Code

macOS (Intel + Apple Silicon, Homebrew, Desktop), Linux (native, Docker), Windows (WSL + native, PowerShell/WinGet, Desktop; WSL image/screenshot paste — new), iOS/Android (mobile app, Dispatch), browser (claude.ai/code).

### Zrb

- macOS: ✅ Full (incl. Seatbelt sandbox)
- Linux: ✅ Full (incl. bwrap sandbox)
- Windows: 🟡 Cross-platform shell execution — `Shell`/`Bash` (incl. `background=True`) converge on shared primitives (`start_new_session=True`, `psutil` teardown, `resolve_shell()`); `get_current_shell()` existence-checks candidates (`pwsh`→`powershell`→`cmd`). Caveat: Windows paths are unit-tested with mocks and reasoned from documented behavior but **not yet verified on a real Windows host**. No native installer; sandbox falls back to warn/deny (no Windows OS mechanism).
- Docker: 🔵 images available
- Android/Termux: 🔵 documented (cold-import optimized); TUI keybindings adapt to Termux (auto-detected `CFG.IS_TERMUX`: plain-Tab cycles modes, focus toggle on Ctrl+K)
- Browser: 🔵 web UI via `zrb server start`

**Status**: 🟡 Partial for Windows (improved but unverified on hardware); ✅ excellent for macOS/Linux; 🔵 explicit Termux handling.

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool: post-edit type errors/warnings; `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`; requires language plugin.

### Zrb

🔵 **Zrb advantage**: `LSPManager` singleton (lazy startup, idle timeout); symbol-based API; full suite (`find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, **`rename_symbol`** with dry-run + honest `applied` flag, `list_available_servers`); auto-detect servers (pyright, gopls, tsserver, rust-analyzer…); **`ZRB_LLM_LSP_PREFERRED_SERVERS`** (ordered preference); per-file project-root cache bounded at 4096 entries; all LSP tools auto-approved.

- **Correct LSP wire protocol** ✅: byte-accurate message framing (the root cause of earlier pyright failures), documents opened before file-scoped queries, `find_definition` uses `textDocument/definition`, `SymbolInformation` positions fixed, `get_workspace_symbols` graceful fallback, stderr drained — verified against real pyright, pylsp, and gopls
- **User-extensible server registry** ✅: `LSPServerConfigRegistry` + `lsp_manager.register_lsp_server(...)` from `zrb_init.py` to add/override languages; participates in auto-detection and preferred-server ordering
- Post-write/edit diagnostics feed LSP results back into tool results (§12)

**Status**: ✅ **Fully supported** (Zrb arguably broader — `rename_symbol`, workspace symbols, preferred-server ordering, user-extensible registry).

---

## 24. Context Compaction

### Claude Code

Auto-compaction on limit; `/compact [instructions]`; `PreCompact`/`PostCompact` hooks; original transcript preserved in `.jsonl`. **Prompt caching** on by default; `--exclude-dynamic-system-prompt-sections` to improve cache reuse; caches CLAUDE.md / project context / long instructions; re-attaches first 5k tokens of each skill after compaction.

### Zrb

Two-layer auto-summarization:
- **Layer 1** — per-message: large tool results summarized in-place
- **Layer 2** — conversational: triggers on message/token thresholds (now system-prompt-aware, v2.24.2); respects tool call/return pairs; chunk-and-summarize with `<state_snapshot>` consolidation; **parallel chunk summarization** (`asyncio.gather`); `<active_skills>` tracked + restored; all summarizer agents use `LLMConfig.resolve_model()`
- Manual: `/compress` / `/compact`
- **`PRE_COMPACT` and `POST_COMPACT` hooks fire** ✅; PreCompact can inject `additionalContext` and block compaction (§5)
- **Partial-run retry context** ✅: failed/interrupted turns capture completed tool calls for the next attempt (§14)

**Prompt caching** ✅ (ADR-0065, ADR-0079):
- The system prompt is **byte-stable across turns** so any provider's prefix cache hits. Session-invariant facts (OS, CWD, project markers, tools, model identity) render into the cached system prompt; volatile per-turn state lives in a **`render_live_context()`** block wrapped as `<live-context>…</live-context>` and **appended to the end of the current user turn** (append-only, frozen into history) so the prefix stays stable.
- The skill catalogue is folded into the byte-stable `mandate` section (ADR-0079) rather than a separately-recomputed section.
- **Tool-schema token reduction**: nullable params converted to non-nullable defaults to drop `anyOf:[type,null]` unions; trimmed tool docstrings; compact schemas for `DelegateToAgent`/`RunZrbTask`.
- Sub-agents are single-turn, so the live block folds back into their inherited system prompt.

**Status**: ✅ **At parity / strong** (compaction has Pre+Post hooks, parallel chunks, skill tracking, partial-run retry; prompt caching is byte-stable)

**Gap**: Missing: focus instructions for manual compact (`/compress [instructions]`), original transcript preservation in `.jsonl`, per-model cache toggles.

**Effort to close**: **Low** (2–4 days): focus-instructions argument (1–2d), transcript `.jsonl` preservation (1–2d).

---

## 25. Vim Mode & Editor Features

### Claude Code

Full Vim mode: NORMAL/INSERT, complete navigation/editing/text-objects, `/` reverse-search in NORMAL; `editorMode: "vim"`.

### Zrb

No Vim mode. Standard `prompt_toolkit` input only.

**Status**: ❌ **Not supported**

**Effort to close**: **Medium** (2–3 weeks) — `prompt_toolkit` key-binding layer.

---

## 26. Voice Input

### Claude Code

Push-to-talk / hold dictation (`/mic`, `voice: {enabled, mode}`, Option+M); CJK + long-silence handling.

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

`TaskCreate/Update/Get/List/Stop` (background bash tasks, unique IDs, auto-clean, Ctrl+T list); `TodoWrite` (session checklist, deprecated).

### Zrb

🔵 **Zrb advantage**: `TodoManager` with persistent JSON (`~/.zrb/todos/{session}.json`); states `pending`/`in_progress`/`completed`/`cancelled`; auto IDs, timestamps, progress. Tool surface simplified to **`write_todos`** (replace-semantics, subsumes the old `update_todo`/`clear_todos`) + **`get_todos`** (ADR-0068); a quantified trigger seeds the list before the first edit when work spans ≥3 steps / multiple files / multiple turns. Session isolation + ContextVar wiring; **todo progress card pushed to the active UI** (TUI/StdUI/web SSE `todo_progress`) after every change; **pending todos rendered into the live context every turn**. Plus 🔵 the full task-automation framework (`CmdTask`, `LLMTask`, DAG, dependencies, retries, scheduling — with cycle detection).

**Status**: ✅ **Fully supported** (Zrb advantage on persistence + system-context integration).

---

## 29. Scheduling

### Claude Code

`CronCreate/Delete/List` tools (in-session recurring/one-shot prompts); `/schedule` (cloud tasks); `/loop [interval] <prompt>`; Desktop scheduled tasks; cloud scheduled tasks (persist when machine off).

### Zrb

🔵 **Zrb advantage** at the task level: full `Scheduler` task type (cron-based, with correct weekday/day-of-month semantics) + `CmdTask` scheduling, plus a `cron parse` developer-utility task. No `CronCreate/Delete/List` as in-session LLM tools; no `/loop`; no cloud scheduling.

**Status**: 🟡 **Partially supported** (task-level scheduling; not in-session LLM tools; no cloud).

**Effort to close**: **Low** for in-session (2–3d): wrap `Scheduler` as `CronCreate/Delete/List`. **Very High** for cloud scheduling.

---

## 30. Worktree Isolation

### Claude Code

First-class: `--worktree`/`-w`, `--tmux`; `isolation: worktree` in agent frontmatter; `EnterWorktree`/`ExitWorktree`; `WorktreeCreate`/`WorktreeRemove` hooks; `/batch`; `worktree.symlinkDirectories`/`sparsePaths`/`bgIsolation`/`baseRef`; `.worktreeinclude`.

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

Native image input on vision models; clipboard paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11); drag-as-attachment in IDE; `@`-mention files; PDF (page-ranged) + Jupyter notebook reads.

### Zrb

🔵 **Multimodal attachment pipeline** ✅ **NEW (v2.26.0)** (`src/zrb/llm/util/`):
- `LLM_MULTIMODAL_MODEL` — designate a vision model to describe attachments when the main model is text-only
- `LLM_MAX_IMAGE_DIMENSION` (1568, Anthropic no-extra-cost tier) + `LLM_IMAGE_JPEG_QUALITY` (85): pasted/`/attach`-ed images auto-scaled; opaque→JPEG, alpha→PNG
- `runner._apply_multimodal_fallback`: if the main model can't consume an image/audio, the multimodal model describes it and substitutes text; if none configured, the attachment is dropped with a `⚠️ Dropped <modality>` warning (never silently sent to a rejecting provider)
- Audio: describe/transcribe fallback. Video: kept for Gemini-class, dropped-with-warning otherwise
- Per-model capability registry (`model_capabilities`) drives support detection
- Clipboard paste via Ctrl+V and Alt+V; `/model multimodal <name>` sets the vision model at runtime

**Status**: ✅ **Fully supported / 🔵 advantage** — the text-only-model fallback (describe-then-substitute) and explicit drop-with-warning are beyond Claude Code's image handling, important for Zrb's multi-provider story.

---

## 32. Provider Resilience & Multi-Model

### Claude Code

Single primary provider (Anthropic) with `--fallback-model` chain on overload; Bedrock/Vertex/Foundry deployments; opaque-error handling abstracted by the platform. Model lineup: Opus 4.8, Sonnet 4.x, Haiku 4.5, Fable 5; effort tiers `low`→`max`; fast mode.

### Zrb

🔵 **Major Zrb advantage** — multi-provider robustness (largely built v2.23–2.26):
- Any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock, …)
- **4-stage history sanitization** (`sanitize_history`): filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles
- **Provider-specific 400 recovery**: DeepSeek `reasoning_content` rejection → `strip_thinking_parts` retry; GLM empty `ValidationException` retry; **generic opaque-400** → `strip_to_text_only()` collapse + single retry (provider-agnostic); Bedrock nil-content → `"."` placeholder; invalid-tool-call detection requires entity + problem keyword
- **Empty-completion guard** (ADR-0059): regenerates blank / leaked `"(tool call)"` completions instead of surfacing them; `filter_nil_content` no longer injects the placeholder into tool-call-only turns
- **Deferred-tool summarizer death-spiral fix** (ADR-0058); `create_agent(resolve_model=False)` stops model-callback double-firing; OpenAI `content:null` patch verifies its target and warns on pydantic-ai drift
- **Parallel-tool-call guard**: `model_capabilities` injects `parallel_tool_calls=False` for known-malforming models
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

Remote Control (control a session from claude.ai/app; `--remote-control`/`--rc`, `claude remote-control`; MCP connectors with OAuth). Channels (push external events via MCP channel plugins: Telegram/Discord/iMessage/webhooks; `--channels`, `channelsEnabled`, `allowedChannelPlugins`). Dispatch (phone → Desktop).

### Zrb

🔵 **Zrb-only existing**: MultiUI (CLI + Telegram + web simultaneously; broadcast output; first-response-wins input); MultiplexApprovalChannel (route approvals to multiple channels); HTTP Chat API (external POST to `/api/v1/chat/sessions/{id}/messages` pushes messages into an active session — authorization-gated). No Remote Control protocol, native Channels plugin system, or Dispatch.

**Status**: 🟡 **Partially covered** (MultiUI + HTTP API cover core use cases; no standardized protocol).

**Effort to close**: **Medium** (2–3 weeks): WebSocket remote control (1wk), webhook endpoint refinement (partial via HTTP API), Telegram/Discord channel plugins (2wk).

---

## 35. Summary & Roadmap

### Overall Coverage Assessment

| Category | Status | Notes |
|----------|--------|-------|
| CLI Flags | 🟡 ~22% | Infra is broad; only `--sandbox` exposed; 7 inputs vs 70+ flags |
| Interactive TUI | 🟡 ~78% | Shift+Tab mode cycling, /copy, arrow-key choice, output scrolling, theming |
| Slash Commands | 🟡 ~47% | Core infra + skill commands + command hooks |
| Memory/CLAUDE.md | 🟡 ~72% | Auto-loading + rich journal; missing local/imports/rules |
| Hooks | 🟡 ~60% | 16/~31 events but near-parity *control* + drop-in CC compat |
| MCP | 🟡 ~55% | stdio + http; no sse/ws/OAuth/ToolSearch/resources |
| Subagents | 🟡 ~58% | Single+parallel+background delegation, policy/sandbox inheritance, lifecycle hooks |
| Agent Teams & Dynamic Workflows | ❌ ~5% | Background delegate only; no teams/Workflow runtime |
| Skills | ✅ ~85% | Governable core/utility/agent split; minor frontmatter gaps |
| Permission Modes | 🟡 ~75% | Policy engine + plan + auto-accept-edits + Shift+Tab + first-class args |
| Settings System | 🟡 ~38% | EnvField + `config explain`; still env-only, no JSON files |
| Built-in Tools | 🟡 ~80% | File/shell/web/LSP/todo/plan/background/worktree covered |
| IDE Integrations | ❌ 0% | Web UI is a different paradigm |
| Session/Checkpoint | 🟡 ~64% | Rewind/snapshot, partial-run retry, /copy export |
| Web UI | 🔵 advantage | Hardened local web UI not in the CC CLI |
| Auto Mode | ❌ ~10% | Policy + sandbox provide enforcement substrate; no classifier |
| GitHub/CI Integration | ❌ ~8% | `git changelog generate`, glab detect; no app/triggers |
| Sandboxing | 🟡 ~58% | FS+OS sandbox + credential deny-read + `--sandbox`; no network |
| Remote/Cloud | 🟡 different | Local web server + multi-channel vs cloud |
| Plugins | 🟡 ~38% | Skills/agents/hooks/MCP dirs; no packaging/marketplace |
| Rate Limiting | 🟡 ~78% | Req/min + tok/min + retry exceed CC; budget/cost UI missing |
| Platform Support | 🟡 ~85% | macOS/Linux excellent; Windows unverified; Termux handling |
| LSP | ✅ advantage | Working wire protocol, rename, workspace symbols, extensible registry |
| Context Compaction & Prompt Caching | ✅ ~92% | Pre+Post hooks, parallel chunks, byte-stable caching |
| Vim Mode | ❌ 0% | — |
| Voice Input | ❌ 0% | — |
| Diff Viewer | ❌ 0% | — |
| Task/Todo | ✅ advantage | Persistent + progress visualization + DAG framework |
| Scheduling | 🟡 ~40% | Task-level Scheduler; no in-session LLM tools; no cloud |
| Worktree Isolation | 🟡 ~65% | Tools + tracking + stale guard; no CLI flag / agent isolation |
| Multimodal & Attachments | ✅ / 🔵 advantage | Describe-then-substitute fallback for text-only models |
| Provider Resilience & Multi-Model | 🔵 advantage | Any provider + deep resilience layer |
| Side Questions (`/btw`) | ✅ 100% | — |
| Channels & Remote Control | 🟡 ~25% | MultiUI + HTTP API; no standardized protocol |

### Zrb Unique Advantages (Superset Features)

1. 🔵 **Multi-model / any provider** via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock…)
2. 🔵 **Provider resilience layer**: 4-stage history sanitization, provider-agnostic opaque-400 recovery, DeepSeek/GLM-5/Bedrock-specific handling, per-model parallel-tool-call guard
3. 🔵 **Multimodal fallback pipeline**: describe-then-substitute for text-only models, image auto-scaling, audio transcribe, explicit drop-with-warning
4. 🔵 **Local Web UI** with hardened auth, streaming, task management, browser tool approval (edit-args)
5. 🔵 **HTTP Chat API** (`/api/v1/chat/`, authorization-gated) for programmatic sessions/messages
6. 🔵 **MultiUI + MultiplexApprovalChannel**: broadcast to terminal + Telegram + web; first-response-wins
7. 🔵 **Task Automation Framework**: CmdTask, LLMTask, Scaffolder, Scheduler, HttpCheck, TcpCheck — a DAG engine (with cycle detection)
8. 🔵 **Run Zrb tasks as LLM tools**: the agent can discover and execute any project task; an LLMTask can itself be a DAG pipeline node ("agent-in-pipeline")
9. 🔵 **AST analysis + RAG**: `AnalyzeFile`/`AnalyzeCode`, `create_rag_from_directory`
10. 🔵 **Richer LSP**: working wire protocol, `rename_symbol` (dry-run), workspace symbols, preferred-server ordering, user-extensible server registry, post-write diagnostics
11. 🔵 **Persistent todos with live-context injection + progress cards**
12. 🔵 **Bidirectional journal graph**: backlinks protocol (file-relative), two-write-kind system, `journal-lint.py`
13. 🔵 **"Program the agent" surface**: custom tools, lifecycle hooks (both task types), permission policies, approval channels, model routing, dynamic prompt sections (`add_live_context`/`add_system_context`/`add_project_context`/`register_section`), history processors
14. 🔵 **Per-model capability registry**: user-extensible image/audio/video/parallel-tool flags
15. 🔵 **Consolidated model pipeline**: single `LLMConfig.resolve_model()`
16. 🔵 **Capability-tagged permission engine + plan + auto-accept-edits**: READ/EDIT/EXECUTE/NETWORK/DELEGATE/META tags with first-match rules, per-tool and per-arg, first-class `permissions=` args
17. 🔵 **Byte-stable prompt + `<live-context>` split** for cross-turn prefix caching (ADR-0065)
18. 🔵 **Fully configurable limits + `config explain`**: all timeouts/intervals/retries/sizes as discoverable env vars
19. 🔵 **Rate limiting + transient retry**: req/min + tok/min, O(n) context fit, backoff + `Retry-After`, classified `StopFailure`
20. 🔵 **Self-hosted, no subscription**: bring your own API key
21. 🔵 **Android/Termux support** with cold-import optimization and adaptive keybindings
22. 🔵 **Flexible web search**: Google News RSS (zero-setup) + SearXNG/Brave/SerpAPI
23. 🔵 **White-labeling**: build custom CLIs via Zrb's framework
24. 🔵 **Selective YOLO** with sub-agent inheritance
25. 🔵 **Inherit-sections sub-agents**
26. 🔵 **Drop-in Claude Code command hooks**: unmodified CC `settings.json` command hooks run as-is (stdin payload + tool-name matchers)
27. 🔵 **Developer-utility task library**: hash/time/url/json/case/cron/hex/number/random/jwt/http/base64/ulid + LLM-driven `git changelog generate`

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. **Surface named permission modes on the CLI** — `dontAsk`/`bypassPermissions` presets + `--permission-mode` flag (the engine, plan, auto-accept-edits, and Shift+Tab cycling already exist) (3–5d)
2. **Extended CLI flags**: `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--worktree` (1wk)
3. **JSON settings files** with scope hierarchy (user/project/local) (1wk)
4. **`/usage`/`/cost` + budget tracking** (3–5d)
5. **Remaining hook events**: `ExitPlanMode`, `WorktreeCreate/Remove`, `TaskCreated/Completed` (fire points now exist) (3–4d)
6. **Additional built-in slash commands**: `/clear`, `/config`, `/export`, `/permissions`, `/diff`, `/sandbox`, `/mode` (1wk)
7. **`/compress [focus]`** focus instructions (1–2d)
8. **MCP prompts as slash commands** (3d)
9. **`--worktree` CLI flag** (1–2d)
10. **CLAUDE.local.md** + `@import` (3–4d)
11. **Enable rewind by default** + Esc+Esc shortcut (2–3d)
12. **`NotebookEdit` tool** (3–4d) — ~~`Monitor`~~ 🟡 mostly done as `MonitorProcess`
13. **Declarative permission rules** — parse a `settings.json`-style rule list into `PermissionPolicy` (1wk); add `Tool(param:value)`-style matching

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

11. **Network sandboxing** (proxy-based allowed/denied domains) + `excludedCommands` (2–3wk)
12. **Full worktree isolation** — `isolation: worktree` in agent defs + `/batch` (2–3wk)
13. **`@-mention` + auto-delegation** for file-based agents + `/agents` UI (2–3wk)
14. **Per-agent frontmatter**: `permissionMode` (via policy engine), `maxTurns`, `mcpServers`, `hooks`, `effort` (1–2wk)
15. **GitHub CI/CD templates** + `/security-review` from `review` skill (1wk)
16. **Plugin packaging format** + `zrb plugin add` (1–2wk)
17. **MCP `sse` + OAuth + resource tools + `ToolSearch`** (2–3wk)
18. **`http` hook handler type** + `if`/`once`/`statusMessage` (1wk)
19. **Skill enhancements**: `paths`, `shell`, `disallowed-tools`, `` !`command` `` injection (1wk)
20. **`NotebookEdit` tool** (3–4d)

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

- **Phase 1** (core feature parity): ~4–6 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~8–12 months with 2–3 developers

> **Net assessment**: Zrb has closed most of its previously-largest structural gaps. **Permission/interaction modes** are now a full capability-tagged policy engine with a read-only **plan mode**, an **auto-accept-edits** mode, and **Shift+Tab cycling** over them, plus first-class `permissions=`/`sandbox=` constructor args. The **hooks system** went from observe-only to near-parity *control* — `PreToolUse`/`PostToolUse`/`Stop` can deny, rewrite tool input/output, and extend turns, and unmodified Claude Code `settings.json` command hooks run drop-in (16 events vs Claude Code's ~31, but the control surface for those events is largely at parity). **Sandboxing** is an opt-in two-layer FS+OS sandbox (Python gate + Seatbelt/bwrap) with credential-read denial, a `--sandbox` flag, and a safe fallback. Zrb is at **prompt-caching parity** (byte-stable prompt + `<live-context>` split), has **single/parallel/background delegation**, a **working LSP** wire protocol, transcript `/copy` export, an arrow-key `AskUserQuestion` UI, `config explain`, an LLM-driven changelog generator, and adaptive Termux keybindings. The remaining structural gaps are concentrated in: **agent teams / dynamic workflows**, **IDE & desktop integration**, the **auto-mode classifier**, **cloud sessions**, **network sandboxing**, JSON file-based settings, and the (large but mostly mechanical) **CLI-flag and built-in-command surface** — where Claude Code keeps widening its lead on managed-cloud orchestration (the `Workflow` tool, implicit Agent Teams, `/workflows`). Zrb's 27 unique advantages — multi-model, provider resilience, local web UI, multi-channel, task automation, RAG, richer LSP, the policy engine, prompt caching, the "program the agent" surface — keep it a genuine superset in the self-hosted / multi-provider / automation dimensions, while Claude Code remains ahead on managed-cloud orchestration and IDE depth.

---

*Analysis updated: 2026-06-27 | Claude Code docs: code.claude.com/docs (surveyed June 2026) | Zrb version: 2.43.1*
