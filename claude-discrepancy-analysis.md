# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Identify every Claude Code feature, assess Zrb's current coverage, quantify the gap, and outline the effort required to make Zrb a superset of Claude Code.
>
> **Methodology**: Claude Code features sourced from official docs (code.claude.com/docs) and the public CHANGELOG, fetched May 2026. Zrb features sourced from full codebase exploration of `src/zrb/` at v2.31.0 plus the changelog (`docs/changelog-v2.md`).
>
> **Zrb version**: 2.31.0 (May 2026)
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
- `--plugin-dir` (now accepts `.zip`), **`--plugin-url`** (fetch plugins from archives — new), `--from-pr`
- Subcommands: `claude agents` (now `--json`, `--cwd`), `claude auto-mode defaults`, `claude auth`, `claude mcp`, `claude plugin` (now `init`/`validate`), `claude setup-token`, `claude update`, **`claude ultrareview`** (non-interactive code review for CI — new), `claude remote-control`

### Zrb

`zrb llm chat` with 6 CLI inputs (`src/zrb/builtin/llm/chat.py`):
- `--message` / `-m`
- `--model`
- `--session` — conversation session name
- `--yolo` — bypass confirmations; full (`true`) or selective (`--yolo "Write,Edit"`)
- `--attach` — file attachments (now multimodal-aware, §31)
- `--interactive` — toggle interactive mode

**Status**: 🟡 **Partially supported**

**Gap**: Unchanged structurally since v2.22.6 — still 6 inputs against Claude Code's 70+ flags. Critical missing: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agents`, `--plugin-dir`, `--remote-control`, `--channels`. The underlying infra (rate limiting, session management, YOLO, snapshots) exists; only the surface is missing.

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

### Zrb

`prompt_toolkit`-based TUI (`src/zrb/llm/ui/`):
- Multi-line input (trailing `\` continuation, Ctrl+J newline)
- Command history with reverse search
- **`!` bash prefix** — `! cmd` / `/exec cmd` runs shell and injects output
- **`@` file mention** with autocomplete (`completion.py`)
- **`/` slash-command palette** — full built-in set + custom skill commands
- `/attach`, `/model`, `/yolo` (full + selective), `/save` / `/load`, `/compress` / `/compact`, `>` / `/redirect`, `/btw`, `/rewind`
- **Image clipboard paste** — Ctrl+V and **Alt+V** ✅
- **MultiUI** — broadcast to multiple channels (terminal + Telegram + web), first-response-wins
- **Animated thinking / confirmation indicators** ✅ (v2.26.x): adaptive refresh loop, debounced invalidation (33–100× fewer redraws)
- **`/help` keyboard-shortcut reference + width-guarded welcome banner** ✅ (v2.28.4–5)
- Git branch + dirty status, active worktree, pending todos, recent commits all shown in context

**Status**: 🟡 **Partially supported**

**Gap**: Zrb has `!`, `@`, `/`, `/btw`, image paste (incl. Alt+V), MultiUI, animated status. Still missing: Vim mode, voice input, permission-mode cycling (Shift+Tab — no named modes to cycle), extended-thinking toggle, background bash (Ctrl+B), task-list toggle (Ctrl+T), Esc+Esc rewind shortcut, git-history prompt suggestions, transcript viewer, color themes, configurable status line, session branching.

**Effort to close**: **Medium** (3–5 weeks): Shift+Tab cycling (needs named modes first), background bash (~1wk), prompt suggestions (~1wk), Vim mode (2–3wk), themes (1–2d), voice (2–3wk).

---

## 3. Slash Commands / Custom Commands

### Claude Code

**Built-in commands** (~55+): `/clear`, `/compact`, `/config`, `/model`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/rewind`, `/branch`, `/export`, `/context`, `/help`, `/ide`, `/init`, `/skills`, `/btw`, `/tasks`, `/permissions`, `/security-review`, `/theme`, `/voice`, `/agents`, `/rename`, `/schedule`, `/effort`, `/desktop`, `/fast`, `/statusline`, **`/goal`** (work until conditions met — new), **`/usage`** (merged `/cost`+`/stats` — new), **`/code-review`** (was `/simplify`; `--fix` applies findings — new), **`/reload-skills`** (new), **`/scroll-speed`** (new).

Bundled skills as commands: `/batch`, `/claude-api`, `/debug`, `/loop`, `/simplify`→`/code-review`. Custom skills become slash commands automatically. MCP prompts become `/mcp__<server>__<prompt>`. Argument interpolation (`$ARGUMENTS`, `$N`), dynamic context (`` !`command` ``), `--disable-slash-commands`.

### Zrb

Custom commands via `CustomCommand` class:
- Argument interpolation: `${name}`, `${name:-default}`, `$1`; literal-`$` guard removed (v2.27.0) so regex/price prompts pass args correctly
- Skill-based commands via `get_skill_custom_command()`; skills become slash commands from `name` metadata
- Skill slash-command stubs delegate to core-skill companion files (`/debug`, `/testing`, `/review`, `/refactor`, `/research`)

Built-in slash commands: `/compress` / `/compact`, `/attach`, `/q` `/bye` `/quit` `/exit`, `/info` `/help`, `/save` `/load`, `/yolo [tools]`, `>` `/redirect`, `!` `/exec`, `/model`, `/btw`, `/rewind`.

**`PRE_COMMAND` / `POST_COMMAND` hooks** ✅ **NEW (v2.31.0)**: hooks fire before/after slash-command dispatch; can block a command, and can **rewrite command arguments on-the-fly** (e.g. `/model opus` → `/model sonnet`) via the hook result's `command_args` (`commands_mixin.py::_command_arg_override`).

**Status**: 🟡 **Partially supported**

**Gap**: Core command infra plus skill-derived commands and command hooks. Missing: ~40 built-in management commands (`/clear`, `/config`, `/diff`, `/branch`, `/export`, `/usage`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/security-review`, `/voice`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/effort`, `/goal`, `/rename`, `/statusline`), MCP prompts as commands, bundled utility skills (`/batch`, `/loop`).

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

**Capabilities**: universal `continue`/`stopReason`/`suppressOutput`/`systemMessage`/`terminalSequence`; `additionalContext` injection; `decision: block`; PreToolUse `permissionDecision` (allow/deny/ask/defer) + `updatedInput`; PermissionRequest `behavior` + `permissionRule`; PermissionDenied `retry`; MessageDisplay `displayContent`; SessionStart `reloadSkills`/`sessionTitle`/`watchPaths`/`initialUserMessage`. Conditional `if`, `async`, `once`, `statusMessage`, `CLAUDE_ENV_FILE`, `allowedHttpHookUrls`, `disableAllHooks`, `/hooks` UI, plugin `monitors`.

### Zrb

**11 hook events** (`src/zrb/llm/hook/types.py`, up from 9):
- `SESSION_START`, `SESSION_END`, `USER_PROMPT_SUBMIT`
- `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE`
- `NOTIFICATION`, `STOP`, `PRE_COMPACT`
- **`PRE_COMMAND`, `POST_COMMAND`** ✅ **NEW (v2.31.0)** — slash-command bracketing (Zrb-specific naming; no direct Claude Code equivalent — closest to `UserPromptExpansion`)

**3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent). No `http`, no `mcp_tool`.

**7 matcher operators**: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`.

**Capabilities**:
- `HookResult` factories: `block`, `allow`, `ask`, `deny`, `with_system_message(replace_response=…)`, `with_additional_context`
- **Tool-input mutation** ✅ **NEW (v2.31.0)**: `allow(updated_input=…)` merges into `hookSpecificOutput.updatedInput` — hooks can rewrite tool params before execution (parity with Claude Code's `updatedInput`)
- **Command-arg mutation** ✅ **NEW (v2.31.0)**: `command_args` rewriting for slash commands
- Async/sync with timeouts (`HOOKS_TIMEOUT`, default 30000ms)
- Config tiers (high→low): plugins → user-home (`~/.claude/`, `~/.zrb/`) → project dirs → `CFG.HOOKS_DIRS`; formats JSON / YAML / `.hook.py` (`register(manager)`); Claude-style env vars (`CLAUDE_HOOK_EVENT`, `CLAUDE_CWD`, `CLAUDE_PERMISSION_MODE`, …)
- Skill-frontmatter hook definitions; `add_hook_factory()`; built-in journaling hook fires reminder at `SESSION_END`

**Status**: 🟡 **Partially supported**

**Gap**: 11 of 30 Claude Code events (~37%). Missing events: `Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `StopFailure`, `CwdChanged`, `FileChanged`, `ConfigChange`, `PostCompact`, `Elicitation`/`ElicitationResult`, `WorktreeCreate`/`WorktreeRemove`, `SubagentStart`/`SubagentStop`, `TaskCreated`/`TaskCompleted`, `TeammateIdle`, `PermissionRequest`/`PermissionDenied`. Missing handler types: `http`, `mcp_tool`. Missing features: `CLAUDE_ENV_FILE`, `once`, `statusMessage`, `/hooks` UI, conditional `if`, `allowedHttpHookUrls`, `terminalSequence`.

**Note**: tool-input and command-arg mutation (the most powerful PreToolUse capability) now reach parity. The remaining gap is breadth of lifecycle coverage, not depth of action.

**Effort to close**: **Medium-High** (4–5 weeks): add missing events + fire points (~1.5wk), `http` handler (2–3d), `mcp_tool` handler (2–3d), `if`/`once`/`statusMessage` (2–3d), security settings (2d), `/hooks` UI (2–3d).

---

## 6. MCP (Model Context Protocol)

### Claude Code

Transports: `stdio`, `http`, `sse`, `ws`. Config scopes (priority): managed → user `~/.claude.json` → local project → `.mcp.json` → `--mcp-config`. `claude mcp add`, OAuth (incl. certificate-based Workload Identity on Vertex — new), MCP prompts as `/mcp__…` commands, MCP tool search (deferred tools), MCP resources tools, subagent-scoped servers, `allowManagedMcpServersOnly`/`deniedMcpServers`, `--strict-mcp-config`, `/mcp` UI, registry/marketplace, Channels notifications.

### Zrb

- **Transports**: `stdio` + **`http`/URL** ✅ (now via `fastmcp`; the prior `sse`-only assessment is outdated)
- Config: `mcp-config.json` (configurable via `MCP_CONFIG_FILE`), searched home → CWD hierarchy
- **Env var expansion** with `${VAR}` / `${VAR:-default}` (recursive over command/args/env)
- Retry via `LLM_MCP_MAX_RETRIES` (default 3)
- Loaded via `load_mcp_config()` in `LLMChatTask`

**Status**: 🟡 **Partially supported**

**Gap**: `stdio` + `http` work. Missing: `ws`/`sse` transports, `zrb mcp add` CLI, OAuth, MCP prompts → slash commands, MCP tool search / deferred loading, MCP resources tools, subagent-scoped MCP, `/mcp` UI, managed-only policy, registry/marketplace.

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
- `create_delegate_to_agent_tool()` → `DelegateToAgent(agent_name, deliverable, task, non_goals, additional_context)` — single sub-agent, scope-clamped via DELIVERABLE/NON-GOALS/TASK/CONTEXT envelope
- `create_parallel_delegate_tool()` → `DelegateToAgentsParallel(tasks)` — concurrent multi-agent, shared UI lock for sequential approvals
- `SubAgentManager` (nested `manager/` package) with lazy filesystem loading; uses `LLMConfig.resolve_model()` so sub-agents respect the global model pipeline
- **YOLO inheritance** ✅ (v2.28.0): full and selective YOLO propagate to sub-agents
- **Tool-guidance propagation** ✅ (v2.22.8): sub-agents receive the same `# Tool Usage Guide`

**Status**: 🟡 **Partially supported**

**Gap**: File-based definitions and delegation work, but invocation is via the `DelegateToAgent` tool — no `@-mention`, no natural-language auto-delegation, no `/agents` UI. Frontmatter lacks `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory`, `isolation: worktree`, `initialPrompt`, `color`, `disallowedTools`. No persistent agent memory directory, no managed subagents.

**Effort to close**: **High** (5–7 weeks): `@-mention` + typeahead (3–4d), auto-delegation (3–4d), per-agent permissionMode/maxTurns/memory (~1wk), subagent-scoped MCP (~1wk), worktree isolation (1–2wk), `/agents` UI (3–4d).

---

## 8. Agent Teams & Dynamic Workflows

### Claude Code

- **Agent Teams**: multiple Claude Code instances cooperating; shared task list with self-coordination; inter-agent `SendMessage`; display modes (in-process or split tmux via `--teammate-mode`); `TeamCreate`/`TeamDelete`; file locking; task dependencies; hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`); storage `~/.claude/teams/`, `~/.claude/tasks/`; non-ASCII team names (new).
- **Dynamic Workflows** (new, v2.1.154): orchestrate "tens to hundreds of agents in the background"; deterministic JS scripts that fan out/pipeline subagents; structured-output schemas; budget-aware loops.

### Zrb

`create_parallel_delegate_tool()`: concurrent multi-agent execution, aggregated results, shared rate limiter + UI lock, per-agent error handling. No persistent team lifecycle, no inter-agent messaging, no shared task list with dependencies, no script-orchestrated fan-out to hundreds of agents.

**Status**: ❌ **Not supported** (parallel delegation exists, but not teams or scripted dynamic workflows)

**Gap**: Zrb's parallel delegation is a single tool call returning aggregated results — not persistent coordinated agents nor a deterministic orchestration runtime. Missing: team lifecycle, inter-agent messaging, shared task list with dependencies, tmux display, file locking, `TeamCreate`/`TeamDelete`, dynamic-workflow scripting.

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

**Built-in skills** (`src/zrb/llm_plugin/skills/`, 13 total) — **new 5-core architecture (v2.27.0)**:
- Core hubs: `core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`
- `core-coding` companions: `languages/` (python, typescript, go, rust, java, ruby, php) + `workflows/` (testing, debug, refactor, review)
- Others: `debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`
- Skill activation table in the mandate maps domain → core skill (auto-approved, silent, once per session/domain)

**Status**: ✅ **Mostly supported** (with minor gaps)

**Gap**: Very close. Missing: `effort` and `${CLAUDE_EFFORT}` (Zrb has no effort concept), `disallowed-tools`, `paths:` glob activation, `shell` field, `` !`command` `` dynamic injection, `$CLAUDE_SESSION_ID` / `$CLAUDE_SKILL_DIR` substitutions, bundled utility skills (`/batch`, `/loop`).

**Effort to close**: **Low** (1–2 weeks): `paths`/`shell`/`disallowed-tools` frontmatter (2–3d), `` !`command` `` preprocessing (1–2d), `$CLAUDE_SESSION_ID`/`$CLAUDE_SKILL_DIR` (1d), `/loop` bundled skill (2–3d).

---

## 10. Permission Modes & Tool Approval

### Claude Code

**6 permission modes**: `default`, `acceptEdits`, `plan`, `auto` (background safety classifier; now on Bedrock/Vertex/Foundry for Opus 4.7/4.8), `bypassPermissions`, `dontAsk`. Shift+Tab cycling; `--permission-mode`; `defaultMode`. Permission rules `Tool`/`Tool(specifier)`/globs/domains/MCP patterns; evaluation deny > ask > allow; config managed > CLI > local > project > user; **`hard_deny`** unconditional rules (new); `PermissionRequest`/`PermissionDenied` hooks.

### Zrb

**Tool approval system** (`chat_tool_policy.py`, `tool_call/tool_policy/`):
- YOLO mode = full `bypassPermissions`; **selective YOLO** (`--yolo "Write,Edit"` / `/yolo Write,Edit`) — `frozenset` of names auto-approved
- **YOLO propagates to sub-agents** ✅ (v2.28.0), including selective sets
- `auto_approve()` predicates: `approve_if_path_inside_cwd`, `approve_if_path_inside_journal_dir`, **`approve_if_path_inside_skill_or_plugin_dir`** ✅ (v2.28.0), `approve_if_mv_inside_journal_dir`
- Per-tool validation: `replace_in_file_validation_policy`, `read_file_validation_policy`
- **`bash_safe_command_policy`**: auto-approves read-only commands (git status/diff/log, ls, cat, grep/rg, version queries…); rejects dangerous metacharacters (`>`, `|`, `;`, `&&`, `` ` ``, `$(`)
- Read/LS/Glob/Grep/AnalyzeFile auto-approved inside cwd / journal / skill+plugin dirs; read-only LSP, todo, `ListWorktrees`, `AskUserQuestion`, `Delegate*`, `ActivateSkill`, web tools auto-approved
- `ApprovalChannel` + `MultiplexApprovalChannel` (first-response-wins across channels); override tool args at approval time (`ApprovalResult.override_args`)

**Status**: 🟡 **Partially supported**

**Gap**: YOLO (full + selective) and rich per-tool auto-approval. Still **no named permission modes** — no `plan`, `acceptEdits`, `dontAsk`, `auto`; no Shift+Tab cycling; no permission-rule config syntax (`Bash(npm run *)`, domain restricts); no deny>ask>allow rule engine; no `PermissionRequest`/`PermissionDenied` hooks; no admin-managed policies.

**Effort to close**: **Medium-High** (4–6 weeks): mode enum + state (1d), `plan` enforcement (3–4d), `acceptEdits` (1d), `dontAsk` (2d), rule-syntax parser (1wk), rule engine (3–4d), Shift+Tab cycling (1d), permission hooks (2d).

---

## 11. Settings & Configuration System

### Claude Code

4 scopes: managed > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`). JSON schema for autocomplete. `/config` tabbed UI. Global `~/.claude.json` (`editorMode`, `autoConnectIde`, `teammateMode`, …). Server-managed settings (claude.ai admin, MDM/OS policies, `managed-settings.json` + `managed-settings.d/`).

### Zrb

**Single config source**: `CFG` singleton (`src/zrb/config/`), env vars (prefix `ZRB_`), composed from **15 mixins** under `_mixins/`: `foundation`, `web`, `llm_core`, `llm_ui` (+ `llm_ui_commands`/`llm_ui_runtime`/`llm_ui_styles`), `llm_limits`, `llm_content`, `llm_prompt`, `llm_search`, `rag`, `internet_search`, `hooks`, `task_runtime`. `CFG.FOO` access stays flat regardless of owning mixin.

- All magic numbers configurable (timeouts/intervals/sizes/retries) since v2.20.0
- **Tool Guidance System** (v2.21.0): `ToolGuidance` dataclass, `add_tool_guidance()` / `add_tool_guidance_factory()`, `CFG.LLM_INCLUDE_TOOL_GUIDANCE`; consolidated into `apply_common_tools()` (v2.28.6) shared across `LLMChatTask`/`LLMTask`/`SubAgentManager`
- **Consolidated model pipeline** (v2.23.0): `LLMConfig.resolve_model()` is the single model-resolution entry point (replaced the task-level getter/renderer of v2.22.0)
- **Per-model capability registry** (v2.28.2): `model_capabilities.register("pattern", supports_parallel_tool_calls=…, supports_image_input=…)`; `create_agent()` injects `parallel_tool_calls=False` for known-malforming models
- Retry config: `LLM_API_MAX_RETRIES`, `LLM_API_MAX_WAIT`; history backup retention `LLM_HISTORY_BACKUP_RETAIN`

**Status**: 🟡 **Partially supported**

**Gap**: Env-var only — no JSON settings files, no layered scopes, no `/config` UI, no JSON schema, no managed/enterprise policy layer.

**Effort to close**: **Medium** (2–3 weeks): JSON settings loader + scope hierarchy (1wk), merge with env vars (2d), JSON schema (2–3d), `/config` UI (1wk).

---

## 12. Built-in Tools

### Claude Code (38+ tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` |
| `Write` | ✅ `write_file` (post-write LSP/static diagnostics v2.30) |
| `Edit` | ✅ `replace_in_file` (fuzzy match + post-edit diagnostics) |
| `Bash` | ✅ `run_shell_command` (120s default, actionable suggestions) |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` (ripgrep acceleration) |
| `Agent` (spawn subagent) | 🟡 `DelegateToAgent` / `DelegateToAgentsParallel` (file-based defs, tool-invoked) |
| `WebFetch` | ✅ `open_web_page` (`OpenWebPage`) |
| `WebSearch` | ✅ `search_internet` (Google News RSS default, SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | ✅ **`AskUserQuestion`** (`ask_user_question`) — **NEW (v2.30)**; short-circuits in non-interactive mode |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` (code intelligence) | ✅ Full suite incl. `LspRenameSymbol` (8 tools) |
| `TaskCreate/Get/List/Update/Stop` | ✅ `write_todos`/`get_todos`/`update_todo`/`clear_todos` (system-context integration) |
| `CronCreate/Delete/List` | ❌ Not LLM tools (Zrb `Scheduler` exists at task level) |
| `EnterPlanMode` / `ExitPlanMode` | 🟡 todo/plan tools exist; no plan-mode enforcement |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking) |
| `Monitor` (stream background events) | ❌ Not implemented |
| `SendMessage` (agent teams) | ❌ Teams not implemented |
| `TeamCreate` / `TeamDelete` | ❌ Teams not implemented |
| `ToolSearch` (deferred tools) | ❌ Not implemented |
| `ListMcpResourcesTool` / `ReadMcpResourceTool` | ❌ Not implemented |
| `PowerShell` | ❌ Not implemented (Windows) |
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

**Post-write/edit diagnostics** ✅ **NEW (v2.30)** (`src/zrb/llm/tool/post_write_check.py`): after `write_file`/`replace_in_file`, runs LSP `get_diagnostics()` + static checks (Python `ast.parse` + `pyflakes`); appends a `[DIAGNOSTIC]` block (up to 5 errors) to the tool result. Mirrors Claude Code's post-edit type-error reporting.

**Status**: 🟡 **Partially supported**

**Gap**: Core file/shell/web/worktree/LSP/todo tools well-covered; `AskUserQuestion` now closed. Missing: `NotebookEdit`, `CronCreate/Delete/List`, `Monitor`, `SendMessage`, `TeamCreate`/`TeamDelete`, `ToolSearch`, MCP resource tools, `RemoteTrigger`/`PushNotification`, `PowerShell`.

**Effort to close**: **Medium** (2–3 weeks): `NotebookEdit` (3–4d), Cron tools (3–4d, reuse `Scheduler`), `ToolSearch` deferred loading (1wk), `Monitor` (2–3d).

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
- `NoSaveHistoryManager` for ephemeral sessions; `/load` shows history with icons; fuzzy session search
- **SQLite-backed sessions** via `ChatSessionManager` for the web UI
- **Snapshot / rewind** ✅: `SnapshotManager` (shadow git repos); `/rewind` picker; 3 restore modes; incremental sync + `DEFAULT_IGNORE_DIRS` (`.venv`, `node_modules`, …) for sub-second backup/restore (v2.26.8/2.28.0); `LLM_ENABLE_REWIND`, `LLM_SNAPSHOT_DIR`
- **Escape preserves history** ✅ (v2.28.0): interrupting a response saves the user message + `[SYSTEM: Response was interrupted]` so the next turn continues from context

**Status**: 🟡 **Partially supported**

**Gap**: Rewind/snapshot + ephemeral sessions + interrupt-preserving history. Missing: rewind is opt-in (not automatic); no Esc+Esc shortcut; no session branching/forking; no resume-by-id picker; no startup `--name`; no `/export`; no session stats; no `--from-pr`.

**Effort to close**: **Medium** (3–4 weeks): enable rewind by default (1d), Esc+Esc (1–2d), branching (1wk), resume picker (2–3d), `--name` (1d), export (1d), stats (2–3d).

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

Background classifier reviews each action before execution; sees user messages + tool calls (not Claude's text — anti-injection); default block (download+execute, prod deploys, mass deletes, IAM) / allow (local file ops, deps, read-only HTTP); fallback to prompting after 3 consecutive / 20 total blocks; `autoMode.environment`/`allow`/`soft_deny`, **`hard_deny`** unconditional (new); `disableAutoMode`; `useAutoModeDuringPlan`; `claude auto-mode defaults`. Now on Bedrock/Vertex/Foundry for Opus 4.7/4.8; classifier detects data exfiltration / bulk repo transfers.

### Zrb

No equivalent safety classifier. YOLO bypasses all confirmations; non-YOLO requires approval (with the rich auto-approve predicates of §10).

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

No OS-level sandboxing. Permission/approval system + `bash_safe_command_policy` metacharacter rejection only.

**Status**: ❌ **Not supported**

**Effort to close**: **High** (3–5 weeks, platform-dependent): macOS `sandbox-exec` (1–2wk), Linux `seccomp`/`bubblewrap` (1–2wk), Docker-based alternative (1wk).

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

**Skill/Agent/Hook plugin dirs** (closest analog): skills/agents/hooks loaded from multiple dirs; `CFG.LLM_PLUGIN_DIRS` (tilde-expanded since v2.26.8); plugin dirs discovered via `.claude-plugin/plugin.json` manifest (`scan_plugin_dirs`); MCP config from multiple locations; `add_hook_factory()`. No formal packaging/marketplace, no `zrb plugin` command, no lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (skills + agents + hooks + MCP, but no packaging/marketplace)

**Effort to close**: **Medium** (3–4 weeks): plugin package format (3–4d), installer `zrb plugin add` (1wk), full plugin-dir scanning (1wk), `/reload-plugins` (2d).

---

## 21. Rate Limiting & Budget Control

### Claude Code

`--max-budget-usd`, `/usage` (merged cost+stats; category breakdown), rate-limit status in footer, `--fallback-model`, per-turn token usage.

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
- Windows: 🟡 Partial (pip works; PowerShell autocomplete + clipboard; no native installer)
- Docker: 🔵 images available
- Android/Termux: 🔵 documented (cold-import optimized — lazy `prompt_toolkit`, ~250ms saved on phone)
- Browser: 🔵 web UI via `zrb server start`

**Status**: 🟡 Partial for Windows; ✅ excellent for macOS/Linux.

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool: post-edit type errors/warnings; `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`; requires language plugin.

### Zrb

🔵 **Zrb advantage**: `LSPManager` singleton (lazy startup, 300s idle timeout); symbol-based API; full suite (`find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, **`rename_symbol`** with dry-run, `list_available_servers`); auto-detect servers (pyright, gopls, tsserver, rust-analyzer…); project-root detection; all LSP tools auto-approved. **Post-write/edit diagnostics** now feed LSP results back into tool results (§12).

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
- **`PRE_COMPACT` hook fires** ✅ (one of the 11 events; payload carries token count)

**Status**: 🟡 **Partially supported**

**Gap**: Robust auto-compaction with parallel chunks + skill tracking + `PreCompact`. Missing: `PostCompact` hook, focus instructions for manual compact (`/compress [instructions]`), original transcript preservation in `.jsonl`.

**Effort to close**: **Low** (3–5 days): `PostCompact` event (2d), focus-instructions argument (1–2d).

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

🔵 **Zrb advantage**: `TodoManager` with persistent JSON (`~/.zrb/todos/{session}.json`); states `pending`/`in_progress`/`completed`/`cancelled`; auto IDs, timestamps, progress; `write_todos`/`get_todos`/`update_todo`/`clear_todos`; session isolation + ContextVar wiring (no explicit `session=`); archive on retention; **pending todos rendered into every system prompt** (LLM never starts blind). Plus 🔵 the full task-automation framework (`CmdTask`, `LLMTask`, DAG, dependencies, retries, scheduling).

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

### Changes Since v2.22.6 (the prior analysis baseline)

#### Zrb improvements (v2.22.7 → v2.31.0)

| Feature | Old Status | New Status | Details |
|---------|-----------|-----------|---------|
| `AskUserQuestion` tool | ❌ (gap) | ✅ | Structured mid-turn questions; non-interactive short-circuit (v2.30) |
| `RM` / `MV` / `SearchJournal` tools | ❌ | 🔵 | File delete/move + journal search (v2.24.0) |
| Post-write/edit diagnostics | ❌ | ✅ | LSP + `ast`/`pyflakes` checks appended to tool result (v2.30) |
| Hook events | 9 | 11 | Added `PRE_COMMAND`/`POST_COMMAND` (slash-command bracketing, v2.31.0) |
| Hook param mutation | ❌ | ✅ | `updated_input` (tool params) + `command_args` (slash-command args) (v2.31.0) |
| MCP HTTP transport | ❌ (stdio/sse) | ✅ | `stdio` + `http` via `fastmcp` |
| Multimodal pipeline | ❌ | 🔵 | Vision-model fallback, image scaling, audio describe (v2.26.0) |
| Provider resilience | partial | 🔵 | 4-stage sanitization, opaque-400 retry, GLM-5/DeepSeek/Bedrock handling, parallel-tool guard (v2.23–2.28) |
| 5-core skill architecture | 10 flat skills | ✅ | core-coding/research/design/writing/journaling + companions (v2.27.0) |
| Skill hooks frontmatter | ❌ | ✅ | Skills can define hooks |
| YOLO → sub-agents | ❌ | ✅ | Full + selective YOLO propagate (v2.28.0) |
| Prompt sections | per-section flags | ✅ | Single `include_sections` / `CFG.LLM_INCLUDE_SECTIONS` (v2.28.0) |
| Model capability registry | ❌ | 🔵 | `model_capabilities.register(...)` per-model (v2.28.2) |
| `apply_common_tools()` | scattered | ✅ | One registration path for chat/LLMTask/SubAgentManager (v2.28.6) |
| `fit_context_window` | O(n²) | ✅ | O(n), ~46× faster at 320 turns (v2.24.1) |
| Escape preserves history | ❌ | ✅ | Interrupted turns continue from context (v2.28.0) |
| History backup rotation | ❌ | ✅ | `LLM_HISTORY_BACKUP_RETAIN` (v2.28.0) |
| System-context perf | recompute/turn | ✅ | `@lru_cache` per-CWD; ThreadPoolExecutor 16→4 (v2.25.2) |
| Google News RSS search | ❌ | 🔵 | Zero-setup default backend (v2.25.2) |
| ReadMany/WriteMany | present | removed | `Read`/`Write` handle multiples via parallel calls (v2.28.0) |

#### New Claude Code features since the prior analysis

| Feature | Impact on Gap |
|---------|--------------|
| Hook events 27 → **30** (`Setup`, `MessageDisplay`, plus prior new ones) | Gap widened (§5) |
| `/goal`, `/usage` (merged cost+stats), `/code-review` (was `/simplify`), `/reload-skills`, `/scroll-speed` | Gap widened (§3) |
| `claude ultrareview` (non-interactive CI review) | Gap widened (§17) |
| **Dynamic workflows** (orchestrate hundreds of agents) | New large gap (§8) |
| Opus 4.8, fast mode, effort high-default + `xhigh`, `${CLAUDE_EFFORT}` | Minor gaps (§1, §9) |
| Auto mode on Bedrock/Vertex/Foundry; `hard_deny`; exfiltration detection | Gap widened (§16) |
| Plugin `--plugin-url`/`.zip`, `init`/`validate`, `defaultEnabled`, dependency enforcement | Gap widened (§20) |
| Vim visual mode; custom theme editing | Minor gaps (§25, §2) |

### Overall Coverage Assessment

| Category | Status | Change vs v2.22.6 |
|----------|--------|-----------------|
| CLI Flags | 🟡 ~22% | = (CC added more) |
| Interactive TUI | 🟡 ~68% | ↑ (multimodal paste, animated status) |
| Slash Commands | 🟡 ~45% | ↑ (command hooks, skill stubs) |
| Memory/CLAUDE.md | 🟡 ~72% | ↑ (journal graph, caching, RTK.md) |
| Hooks | 🟡 ~37% (11/30) | ↑ (param mutation, +2 events) but CC +3 events |
| MCP | 🟡 ~58% | ↑ (HTTP transport) |
| Subagents | 🟡 ~50% | ↑ (file-based + YOLO/guidance propagation) |
| Agent Teams & Dynamic Workflows | ❌ 0% | ↓ (CC added dynamic workflows) |
| Skills | ✅ ~85% | ↑ (5-core architecture, hooks, companions) |
| Permission Modes | 🟡 ~35% | ↑ (YOLO inheritance, more predicates) |
| Settings System | 🟡 ~35% | ↑ (model capability registry, common_tools) |
| Built-in Tools | 🟡 ~78% | ↑ (AskUserQuestion, RM/MV, post-write diag) |
| IDE Integrations | ❌ 0% | = |
| Session/Checkpoint | 🟡 ~58% | ↑ (backup rotation, escape-preserve) |
| Web UI | 🔵 advantage | = |
| Auto Mode | ❌ 0% | = |
| GitHub/CI Integration | ❌ 0% | = |
| Sandboxing | ❌ 0% | = |
| Remote/Cloud | 🟡 different | = |
| Plugins | 🟡 ~38% | ↑ (manifest discovery) |
| Rate Limiting | 🟡 ~78% | ↑ (O(n) context fit) |
| Platform Support | 🟡 ~82% | = |
| LSP | ✅ advantage | ↑ (post-write diagnostics) |
| Context Compaction | 🟡 ~84% | ↑ (PreCompact fires, system-prompt-aware) |
| Vim Mode | ❌ 0% | = |
| Voice Input | ❌ 0% | = |
| Diff Viewer | ❌ 0% | = |
| Task/Todo | ✅ advantage | = |
| Scheduling | 🟡 ~40% | = |
| Worktree Isolation | 🟡 ~65% | ↑ (stale guard) |
| Multimodal & Attachments | ✅ / 🔵 advantage | ↑↑ (new pipeline) |
| Provider Resilience & Multi-Model | 🔵 advantage | ↑↑ (major resilience work) |
| Side Questions (`/btw`) | ✅ 100% | = |
| Channels & Remote Control | 🟡 ~25% | = |

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

### Recommended Implementation Priority

#### Phase 1: High-Impact, Lower Effort (4–6 weeks)

1. **Named permission modes** (`plan`, `acceptEdits`, `dontAsk`) + Shift+Tab cycling (1–1.5wk)
2. **Extended CLI flags**: `--permission-mode`, `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--effort` (1wk)
3. **JSON settings files** with scope hierarchy (user/project/local) (1wk)
4. **`/usage`/`/cost` + budget tracking** (3–5d)
5. **More missing hook events**: `PostCompact`, `SubagentStart/Stop`, `PostToolUseFailure` already present — add `UserPromptExpansion`, `PostToolBatch`, `SessionStart` extras (3–4d)
6. **Additional built-in slash commands**: `/clear`, `/config`, `/export`, `/permissions`, `/diff` (1wk)
7. **`/compress [focus]`** focus instructions (1–2d)
8. **MCP prompts as slash commands** (3d)
9. **`--worktree` CLI flag** (1–2d)
10. **CLAUDE.local.md** + `@import` (3–4d)
11. **Enable rewind by default** + Esc+Esc shortcut (2–3d)
12. **`Monitor` tool** + `NotebookEdit` tool (1wk)

#### Phase 2: Medium-Impact, Medium Effort (6–10 weeks)

13. **Full worktree isolation** — `isolation: worktree` in agent defs + `/batch` (2–3wk)
14. **`@-mention` + auto-delegation** for file-based agents + `/agents` UI (2–3wk)
15. **Per-agent frontmatter**: `permissionMode`, `maxTurns`, `mcpServers`, `hooks`, `memory` (1–2wk)
16. **GitHub CI/CD templates** + `/security-review` from `review` skill (1wk)
17. **Plugin packaging format** + `zrb plugin add` (1–2wk)
18. **MCP `ws`/`sse` + OAuth + resources tools** (2–3wk)
19. **`http` + `mcp_tool` hook handler types** (1wk)
20. **Permission rules config syntax** + deny>ask>allow engine (1.5wk)
21. **Skill enhancements**: `paths`, `shell`, `disallowed-tools`, `` !`command` `` injection (1wk)
22. **Cron tools** (`CronCreate/Delete/List`) wrapping `Scheduler` (3d)

#### Phase 3: Lower-Priority, Higher Effort (3–6 months)

23. **Auto mode safety classifier** (4–6wk)
24. **Dynamic workflows runtime** (script-orchestrated fan-out to many agents) (6–10wk)
25. **Agent Teams** — persistent coordinated agents (2–3mo)
26. **IDE integrations** (VS Code, JetBrains) (3–4mo)
27. **Vim mode** in TUI (2–3wk)
28. **OS-level sandboxing** (3–5wk)
29. **Voice input** (2–3wk)
30. **Desktop app** (Electron/Tauri) (4–6wk)
31. **Cloud scheduled tasks** (requires cloud infra)

### Estimated Total Effort to Full Parity

- **Phase 1** (core feature parity): ~6–8 weeks, 1–2 developers
- **Phase 2** (advanced features): ~8–12 weeks, 2–3 developers
- **Phase 3** (specialized features): ~4–6 months, dedicated teams per feature
- **Total for complete superset**: ~8–12 months with 2–3 developers

> **Net assessment**: From v2.22.6 → v2.31.0 Zrb closed several real gaps — `AskUserQuestion`, post-write diagnostics, hook parameter mutation, slash-command hooks, MCP HTTP transport, file-move/delete tools — and **widened its lead on the "quality of execution" axis**: a multimodal-fallback pipeline, a provider-resilience layer (4-stage sanitization + opaque-400 recovery across DeepSeek/GLM-5/Bedrock), a per-model capability registry, the 5-core skill architecture, and O(n) context fitting. Meanwhile Claude Code expanded breadth: hooks 27→30 events, **dynamic workflows orchestrating hundreds of agents**, `/goal`/`/usage`/`/code-review`/`ultrareview`, Opus 4.8 + fast mode + effort tiers, and auto mode on more platforms. The structural gaps that remain are the same ones — named permission modes, agent teams/dynamic workflows, IDE/desktop, auto-mode classifier, sandboxing, cloud sessions — and they are exactly the items requiring net-new architecture rather than surface wiring. Zrb's 23 unique advantages (multi-model, provider resilience, local web UI, multi-channel, task automation, RAG, richer LSP, tool guidance) make it a genuine superset in the self-hosted / multi-provider / automation dimensions even as Claude Code remains ahead on managed-cloud orchestration and IDE depth.

---

*Analysis updated: 2026-05-30 | Claude Code docs: code.claude.com/docs (fetched May 2026) | Zrb version: 2.31.0*
