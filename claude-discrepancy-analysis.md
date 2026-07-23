# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Map the full Claude Code feature surface, assess where Zrb stands against each area, name the *substantive* difference even where the two overlap, quantify the gap, and estimate the effort to close it.
>
> **Method**: Claude Code features are drawn from its public documentation, CLI surface, and shipped tool set. Zrb features are drawn from a direct read of `src/zrb/`, the changelog (`docs/changelog.md`, `docs/changelog-v2/`), and the ADR record (`docs/adr/`).
>
> **Zrb version**: 2.50.3
>
> **Model lineup (both tools target these)**: Opus 4.8, Sonnet 5, Haiku 4.5, Fable 5; effort tiers `low → medium → high → xhigh → max`; fast mode on Opus 4.8/4.7.
>
> **Legend**:
> - ✅ **Fully supported** — identical or functionally equivalent
> - 🟡 **Partially supported** — exists, with a named gap
> - ❌ **Not supported** — absent
> - 🔵 **Zrb-only** — Zrb has it; Claude Code does not
>
> **Reading note**: a shared ✅ almost never means *identical*. Claude Code is a managed, single-provider, desktop-and-cloud product; Zrb is a self-hosted, any-provider Python framework. The same capability is therefore reached by different mechanisms with different edges. Each section names that difference rather than stopping at "both have it".

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
25. [Prompt Composition & Model Adaptation](#25-prompt-composition--model-adaptation)
26. [Voice Input](#26-voice-input)
27. [Vim Mode & Editor Features](#27-vim-mode--editor-features)
28. [Diff Viewer](#28-diff-viewer)
29. [Task / Todo System](#29-task--todo-system)
30. [Scheduling](#30-scheduling)
31. [Worktree Isolation](#31-worktree-isolation)
32. [Multimodal & Attachments](#32-multimodal--attachments)
33. [Provider Resilience & Multi-Model](#33-provider-resilience--multi-model)
34. [Side Questions (`/btw`)](#34-side-questions-btw)
35. [Channels & Remote Control](#35-channels--remote-control)
36. [Summary & Roadmap](#36-summary--roadmap)

---

## 1. CLI Interface & Flags

### Claude Code

A wide CLI: ~70 flags across ~30 subcommands. Highlights: `claude "query"`, `-p`/`--print`, `-c`/`--continue`, `-r`/`--resume`, `-n`/`--name`, `--session-id`; `--model` (aliases `opus`/`sonnet`/`haiku`/`fable`/`best`), `--permission-mode` (`default`/`acceptEdits`/`plan`/`auto`/`dontAsk`/`bypassPermissions`), `--allow-dangerously-skip-permissions`; `--max-turns`, `--max-budget-usd`, `--output-format` (`text`/`json`/`stream-json`), `--input-format`, `--json-schema`; `--system-prompt[-file]`, `--append-system-prompt[-file]`, `--add-dir`, `--settings`, `--setting-sources`, `--safe-mode`, `--bare`; `--mcp-config`, `--strict-mcp-config`, `--agent`, `--teammate-mode`, `--tools`/`--allowedTools`/`--disallowedTools`; `--worktree`/`-w`, `--effort` (incl. `ultracode`), `--fork-session`, `--fallback-model` (chain); `--bg`/`--background`, `--exec`, `--no-session-persistence`, `--include-partial-messages`, `--include-hook-events`; `--channels`, `--chrome`, `--remote`, `--remote-control`/`--rc`, `--teleport`, `--teammate-mode`; `--plugin-dir`, `--plugin-url`, `--from-pr`, `--ide`. Subcommands include `agents`, background-session verbs (`attach`/`stop`/`kill`/`respawn`/`rm`/`logs`), `daemon`, `auth`, `mcp` (incl. `login`/`logout`), `plugin`, `setup-token`, `update`/`install`, `ultrareview`, `remote-control`, `auto-mode`, `project purge`.

### Zrb

`zrb llm chat` exposes **7 CLI inputs** (`src/zrb/builtin/llm/chat.py`): `message`/`-m`, `model`, `session`, `yolo` (`true`/`false` or comma-separated tool names), `attach` (multimodal, §32), `interactive` (default `true`), `sandbox` (`true`/`false`, §18).

The imbalance is not depth of capability but *surface*. Zrb's engine already has permission policy + plan mode, an FS/OS sandbox, background delegation, prompt caching, rate limiting, snapshots, hooks, and named themes — but most of it is reached through in-session commands and `ZRB_*` env vars, not CLI flags. `--sandbox` is the only mode toggle promoted to a flag; interaction modes cycle in-session (Shift+Tab, §2) rather than via `--permission-mode`.

Under `--interactive false`, hard-ASK approval gates resolve deterministically rather than hanging: `ExitPlanMode` auto-approves (no human to show a plan to); every other hard-ASK tool is denied with a "re-run with `--interactive true`" message.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Claude Code treats the CLI as the primary control plane; Zrb treats the *Python task definition* as the control plane (a `LLMChatTask` is configured in code — `permissions=`, `sandbox=`, hooks, prompt sections — then bound to whatever CLI inputs the author chooses). Zrb's gap is that the shipped `chat` task exposes few of those knobs as flags, so an ad-hoc CLI user can't reach them without writing a task or setting env.

**Missing surface**: `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format json/stream-json`, `--system-prompt`, `--add-dir`, `--worktree`, `--bare`, `--no-session-persistence`, `--effort`, `--fork-session`, `--fallback-model`, `--resume`, `--name`, `--agent`, `--plugin-dir`, `--remote-control`, `--channels`.

**Effort to close**: **Medium** (2–3 weeks) — most map directly onto existing config; the work is wiring, not new capability.

---

## 2. Interactive Terminal Mode

### Claude Code

Rich TUI: Vim mode (`editorMode: "vim"`, NORMAL/INSERT, `/` reverse-search); voice input (`/mic`, hold/push); `!` bash prefix, `@` file mention w/ autocomplete, `/` command palette; multiline (Shift+Enter, Option+Enter, `\`+Enter, Ctrl+J); shortcuts Shift+Tab (cycle permission modes), Ctrl+B (background agents), Ctrl+T (task list), Esc+Esc (stop / rewind), Cmd/Ctrl+Enter (submit), Cmd/Ctrl+K (new session), Cmd/Ctrl+L (clear); `/btw` side questions, image paste/drag-drop, artifact previews; fullscreen vs classic TUI, configurable status line, effort slider, model picker, live thinking counter, color themes, wheel-scroll control.

### Zrb

`prompt_toolkit` TUI (`src/zrb/llm/ui/`):
- Multi-line input (trailing `\`, Ctrl+J); command history with reverse search
- `!` bash prefix (`! cmd` / `/exec cmd` injects shell output); `@` file mention w/ autocomplete (`completion.py`); `/` slash palette (built-ins + skill commands)
- `/attach`, `/model` (+ `small`/`multimodal`), `/yolo` (full + selective), `/plan`, `/save`/`/load`, `/compress`/`/compact`, `>`/`/redirect`, `/copy`, `/btw`, `/rewind`, `/voice`
- **Shift+Tab interaction-mode cycling** (`normal → auto-accept-edits → plan → normal`) with a persistent status-bar mode badge and an on-screen hint. `auto-accept-edits` is selective YOLO over `{Write, Edit}` (files auto-approve; shell/delegation/fetch still prompt). On Termux (auto-detected via `CFG.IS_TERMUX`, incl. proot distros via `ANDROID_ROOT`), plain Tab also cycles and focus toggle moves to Ctrl+K, because Termux terminals can't distinguish Tab from Shift+Tab.
- **`/copy` + clipboard `/redirect`**: `/copy` copies the full transcript (or to a file); bare `/redirect` copies the last AI response. `pyperclip` with an OSC 52 fallback (works over SSH/tmux/screen); ANSI stripped on copy.
- **Arrow-key selection UI for `AskUserQuestion`**: ↑/↓ move, Enter confirm, Space toggle (multi-select), plus a synthetic "✎ Type my own answer…" row; web/`SimpleUI`/`MultiUI` fall back to type-a-number.
- **Sub-agent activity panel**: a live TUI panel lists currently-running sub-agents with ordinal, task summary, and latest output line; collapses to zero height when idle. Sub-agents are labelled `[name #1]`, `[name #2]` — the panel is the legend for those output prefixes.
- **Session token tracking**: the status bar shows accumulated input/output tokens for the session (`💸 1.5k in · 34 out`) beside the Ready/working indicator; resets on `/load`.
- **Output-pane scrolling**: mouse-wheel scrolls the output cursor, pauses auto-follow when scrolled up, resumes at bottom; scroll-follow detection is O(1).
- **Image clipboard paste** (Ctrl+V and Alt+V); **MultiUI** (broadcast to terminal + Telegram + web, first-response-wins); animated thinking/confirmation indicators.
- **Named themes + configurable colors**: `ZRB_THEME` (`dark`/`light`, extensible via `register_theme`) supplies defaults for every style knob across TUI, markdown renderer, and CLI semantic colors; individual `ZRB_LLM_UI_STYLE_*` / `ZRB_CLI_*` still override.
- Live context shows git branch + dirty status, active worktree, pending todos, recent commits.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the two TUIs converge on the same *interaction grammar* (`!`/`@`/`/`, Shift+Tab modes, arrow-key choices, mode badge). Where they diverge is the runtime substrate: Claude Code runs as a desktop app with OS-level key events, so it can offer hold-to-talk voice, drag-drop attachments, and artifact previews; Zrb runs inside a terminal, so it reaches equivalents through terminal-safe mechanisms (press-to-start voice §26, OSC 52 clipboard, mouse-wheel scroll) and *adds* things a desktop app doesn't need — the sub-agent activity panel, Termux keybinding adaptation, and broadcast MultiUI.

**Gap**: still missing Vim mode, a background-agents shortcut (Ctrl+B — background delegation exists as tools but has no hotkey), a task-list toggle (Ctrl+T — todos render in live context but no dedicated pane), an Esc+Esc rewind shortcut, git-history prompt suggestions, an in-TUI transcript viewer, and an in-TUI theme editor (theming is env-var/registry only).

**Effort to close**: **Medium** (2–4 weeks): background-agents shortcut + task pane (~1wk), Vim mode (2–3wk), Esc+Esc rewind (~2d), theme editor (~2d).

---

## 3. Slash Commands / Custom Commands

### Claude Code

~60 built-ins: `/clear`, `/compact`, `/config` (+ `key=value`), `/model`, `/effort`, `/fast`, `/vim`, `/memory`, `/mcp`, `/hooks`, `/diff`, `/plan`, `/review`, `/rewind`, `/branch`, `/worktree`, `/commit`, `/cd`, `/export`, `/search`, `/context`, `/help`, `/status`, `/doctor`, `/ide`, `/init`, `/skills`, `/reload-skills`, `/btw`, `/tasks`, `/background`, `/resume`, `/agents`, `/permissions`, `/add-dir`, `/security-review`, `/theme`, `/voice` (`/mic`), `/rename`, `/schedule`, `/loop`, `/usage`, `/statusline`, `/sandbox`, `/workflows`, `/plugin`, `/reload-plugins`, `/feedback`, `/ultrareview`. Bundled skills as commands: `/batch`, `/code-review` (`--fix`), `/claude-api`, `/debug`, `/loop`, `/deep-research`, `/run`, `/verify`. Custom skills become slash commands automatically; MCP prompts become `/mcp__<server>__<prompt>`. Interpolation: `$ARGUMENTS`, `$N`; dynamic context `` !`command` ``.

### Zrb

Custom commands via `CustomCommand`: `${name}`, `${name:-default}`, `$1` interpolation (literal-`$` guarded); skill-derived commands via `get_skill_custom_command()` (a skill's `name` metadata becomes its slash command); skill stubs delegate to core-skill companion files. Built-ins: `/compress`/`/compact`, `/attach`, `/q` `/bye` `/quit` `/exit`, `/info` `/help`, `/save` `/load`, `/yolo [tools]`, `/plan`, `>` `/redirect`, `/copy [file]`, `!` `/exec`, `/model [small|multimodal] <name>`, `/btw`, `/rewind`, `/voice`. Command names are configurable (`ZRB_LLM_UI_COMMAND_*`).

**`PRE_COMMAND` / `POST_COMMAND` hooks**: fire before/after slash-command dispatch; can block a command and **rewrite its arguments** on the fly (`command_args` on the hook result).

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's command set is deliberately small and *composed from the skill system* — most agent capability is expressed as skills (which auto-register as commands) rather than hardcoded built-ins, and command dispatch is itself hookable (PRE/POST_COMMAND with arg rewrite, which Claude Code does not expose). Claude Code's set is large because it surfaces every management concern (config, permissions, diff, usage, worktree) as a discrete command; Zrb folds several of those into modes (Shift+Tab) and env config instead.

**Gap**: ~40 management commands absent (`/clear`, `/config`, `/diff`, `/branch`, `/export`, `/usage`, `/context`, `/mcp`, `/hooks`, `/permissions`, `/theme`, `/security-review`, `/vim`, `/ide`, `/init`, `/tasks`, `/agents`, `/schedule`, `/loop`, `/effort`, `/rename`, `/statusline`, `/sandbox`, `/workflows`); no `/mode` for web/MultiUI parity; MCP prompts not surfaced as commands; bundled utility skills (`/batch`, `/loop`, `/verify`) absent.

**Effort to close**: **Medium** (3–5 weeks) — most wrap functionality that already exists.

---

## 4. Memory System

### Claude Code

**CLAUDE.md** (human-authored): managed/enterprise, user (`~/.claude/CLAUDE.md`), user-local, project (`./CLAUDE.md` / `./.claude/CLAUDE.md`), `CLAUDE.local.md` (gitignored), subdirectory lazy-load, `@import` (≤4 hops), `claudeMdExcludes`, `.claude/rules/` path-scoped (YAML `paths:`), `<!-- comment -->` stripping. **Auto memory** (Claude-authored): `~/.claude/projects/<project>/memory/MEMORY.md` (index) + on-demand topic files, first 200 lines / 25KB loaded at start; `/memory`, `autoMemoryEnabled` / `autoMemoryDirectory`.

### Zrb

**CLAUDE.md / AGENTS.md / GEMINI.md / README.md / RTK.md auto-loading** (`src/zrb/llm/prompt/claude.py`): the `project_context` section (default-on) searches `~/.claude/` → filesystem root → … → CWD; the most-specific occurrence loads up to `MAX_PROJECT_DOC_CHARS`, others are listed for on-demand `Read`; per-`(path, mtime)` read caching. The mandate requires a full `Read` of AGENTS.md / CLAUDE.md / README.md on the first *code-touching* turn (grep does not satisfy it).

**Journal system** (the auto-memory analog): `LLM_JOURNAL_DIR` (`~/.zrb/journal/`), injected via the `journal_mandate` section; read/write/search tools incl. `SearchJournal`; auto-approved within the journal dir. It goes beyond a flat notes file: a **bidirectional journal graph** with a backlinks protocol and file-relative link resolution; a **two-write-kind system** (Insight vs Activity) with a `core-journaling` skill, activity-log template, and `journal-lint.py`; a decision-table protocol with verify-before-logging. `ZRB_LLM_INCLUDE_JOURNAL_MANDATE` and `ZRB_LLM_INCLUDE_JOURNAL_REMINDER` are independent; the reminder fires at `Stop`. The journal *index* is injected into the per-turn `<live-context>` (not the cached system prompt), at exactly two moments — session start and each summarization — so a journal write mid-session no longer invalidates the cached prompt prefix (§24, ADR-0082).

**Status**: 🟡 **Partially supported**

**Difference that matters**: Claude Code's auto-memory is a Claude-maintained scratchpad loaded verbatim at startup; Zrb's journal is a *structured graph* with typed entries, backlinks, and a linter, designed to be navigated with a search tool rather than dumped into context — and it is caching-aware (index in live-context). The human-authored side is where Zrb is thinner: it loads project docs but lacks the layered override files and path-scoped rules.

**Gap**: no `CLAUDE.local.md`, no `@import` chaining, no `.claude/rules/` path-scoped YAML, no `claudeMdExcludes`, no `<!-- comment -->` stripping, no subdirectory lazy-load, no interactive `/memory`, no configurable char limit surfaced as a command.

**Effort to close**: **Low–Medium** (1–2 weeks): `CLAUDE.local.md` (1d), comment stripping (1d), `@import` (2–3d), `.claude/rules/` (3–5d), `/memory` (2–3d).

---

## 5. Hooks System

### Claude Code

**~31 events**: `SessionStart`, `Setup`, `SessionEnd`, `UserPromptSubmit`, `UserPromptExpansion`, `Stop`, `StopFailure`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`, `PermissionDenied`, `ExitPlanMode`, `SubagentStart`, `SubagentStop`, `TeammateIdle`, `TaskCreated`, `TaskCompleted`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `Notification`, `MessageDisplay`, `PreCompact`, `PostCompact`, `Elicitation`, `ElicitationResult`. **5 handler types**: `command`, `http`, `mcp_tool`, `prompt`, `agent`. Capabilities: `continue`/`stopReason`/`suppressOutput`/`systemMessage`, `additionalContext`, `decision: block`, PreToolUse `permissionDecision` (allow/deny/ask/defer) + `updatedInput`, PostToolUse `updatedToolOutput`, `exec`-form `args`, `if`/`async`/`once`/`statusMessage`, `allowedHttpHookUrls`, `disableAllHooks`, `/hooks` UI.

### Zrb

**16 events** (`src/zrb/llm/hook/types.py`): `SESSION_START`, `SESSION_END`, `USER_PROMPT_SUBMIT`, `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_USE_FAILURE`, `PERMISSION_REQUEST`, `NOTIFICATION`, `STOP`, `STOP_FAILURE`, `PRE_COMPACT`, `POST_COMPACT`, `SUBAGENT_START`, `SUBAGENT_STOP`, `PRE_COMMAND`, `POST_COMMAND` (the last two are Zrb-specific slash-command bracketing). **3 handler types**: `COMMAND` (shell), `PROMPT` (LLM eval), `AGENT` (sub-agent). **7 matcher operators**: `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `REGEX`, `GLOB`.

Capabilities (ADR-0066, ADR-0074, ADR-0076):
- **Drop-in Claude Code command-hook compatibility**: the payload is written to the hook's **stdin** as Claude-shaped JSON (with `tool_name`/`tool_input`/`tool_response`), and `.claude/settings.json` / `settings.local.json` (home + project) are read as a hook source, so unmodified CC command hooks run as-is.
- **Single `SafeToolsetWrapper.call_tool` chokepoint**: `PRE_TOOL_USE` fires for every tool call and honors `permissionDecision: deny/ask/defer`, exit-2 (reason from stderr, Claude convention), and `updatedInput`; `POST_TOOL_USE` honors `decision: block`, `updatedToolOutput`, `additionalContext`; `POST_TOOL_USE_FAILURE` fires on tool raise.
- **Turn control**: `USER_PROMPT_SUBMIT` can block a prompt; `STOP` is a block-to-continue / turn-extension point (re-runs the agent with `reason`, capped at 8 blocks); `continue: false` halts the loop; `PRE_COMPACT` injects `additionalContext` and can block compaction.
- **`STOP_FAILURE` error classification**: maps API errors to matcher tokens (`rate_limit`/`overloaded`/`server_error`/`context_length`/`authentication_failed`/`invalid_request`/`model_not_found`/`unknown`).
- **Claude tool-name aliases** for matchers: `Shell` matches `Bash`; `DelegateToAgent`/`DelegateToAgentBackground` match `Task`.
- `HookResult` factories (`block`, `allow`, `ask`, `deny`, `with_system_message`, `with_additional_context`); async (fire-and-forget with concurrency semaphore + backlog ceiling) / sync with timeouts (`HOOKS_TIMEOUT`); `ZRB_HOOKS_ENABLED` kill-switch; config tiers plugins → user-home → project → `CFG.HOOKS_DIRS`; formats JSON / YAML / `.hook.py` / `.claude/settings.json`. Uniform `add_hook_factory()` on both `LLMChatTask` and `LLMTask` with per-task isolation.

**Status**: 🟡 **Partially supported** (control-capability parity is high; event breadth is the gap)

**Difference that matters**: for the events Zrb *does* have, the control surface is at near-parity — deny, ask, arg-rewrite, output-rewrite, turn-extension, additionalContext — and Claude Code command hooks run drop-in. The divergence is (a) lifecycle breadth: 16 vs ~31 events, and (b) handler richness: Zrb has an `AGENT`/`PROMPT` handler (evaluate a hook with an LLM) that Claude Code's `mcp_tool` handler doesn't mirror, while Claude Code has `http`/`mcp_tool` handlers Zrb lacks (`mcp_tool` is explicitly out of scope per ADR-0074).

**Gap**: missing events `Setup`, `InstructionsLoaded`, `UserPromptExpansion`, `PostToolBatch`, `MessageDisplay`, `CwdChanged`, `FileChanged`, `ConfigChange`, `ExitPlanMode`, `Elicitation`/`ElicitationResult`, `WorktreeCreate`/`WorktreeRemove`, `TaskCreated`/`TaskCompleted`, `TeammateIdle`, `PermissionDenied`; missing `http` handler; missing `if`/`once`/`statusMessage`, parallel most-restrictive-merge execution (Zrb is sequential-by-priority), `/hooks` UI.

**Effort to close**: **Medium** (2.5–4 weeks): remaining events + fire points (~1wk), `http` handler (2–3d), `if`/`once`/`statusMessage` (2–3d), `/hooks` UI (2–3d).

---

## 6. MCP (Model Context Protocol)

### Claude Code

Transports `stdio`, `http`, `sse` (deprecated), `ws`; scopes managed → user `~/.claude.json` → local project → `.mcp.json` → `--mcp-config`; `claude mcp add/list/remove/get/login/logout/serve`; live reconnect with backoff; OAuth 2.0; MCP prompts as `/mcp__…`; **MCP tool search** (`ToolSearch`, deferred tools, `ENABLE_TOOL_SEARCH`); MCP resource tools (`ListMcpResourcesTool`/`ReadMcpResourceTool`, `@server:…`); subagent-scoped servers; idle timeout; elicitation; `/mcp` UI; registry/marketplace; claude.ai connectors.

### Zrb

- **Transports** `stdio` + `http`/URL (via `fastmcp`).
- Config: `mcp-config.json` (`MCP_CONFIG_FILE`), searched home → CWD; `${VAR}` / `${VAR:-default}` env expansion (recursive over command/args/env); retry via `LLM_MCP_MAX_RETRIES`; loaded by `load_mcp_config()`.
- **MCP results are token-safe**: results are capped to `CFG.LLM_MAX_OUTPUT_CHARS` via pydantic-ai's `process_tool_call` hook (keeping the toolset id/client intact for namespacing), and `BinaryContent` (images) pass through untouched rather than being stringified/truncated — so an oversized MCP payload can't livelock the rate limiter or corrupt image data.
- **Deferred loading**: MCP toolsets register with `defer_loading=True`, so their schemas stay out of the per-turn context until the model references them (see §12 for how this relates to Claude Code's `ToolSearch`).

**Status**: 🟡 **Partially supported**

**Difference that matters**: both keep large MCP tool surfaces out of the per-turn prompt, but by different means — Claude Code exposes an explicit model-facing `ToolSearch` tool the model calls to load schemas; Zrb defers loading at the framework layer (pydantic-ai `defer_loading`), so the model never issues an explicit search — schemas resolve transparently when a tool is referenced. Zrb's payload-capping and binary-content correctness are areas where it is arguably more defensive than the baseline.

**Gap**: no `sse`/`ws`, no `zrb mcp add` CLI, no OAuth, no MCP prompts → slash commands, no MCP resource tools (`@server:…`), no subagent-scoped MCP, no idle timeout, no elicitation, no `/mcp` UI, no registry/marketplace.

**Effort to close**: **Medium** (3–4 weeks): `ws`/`sse` (3–5d), `zrb mcp add` (2d), prompts→commands (3–4d), resource tools (2–3d), `/mcp` UI (2–3d), OAuth (1–2wk).

---

## 7. Subagents / Multi-Agent Orchestration

### Claude Code

Declarative subagents via markdown + YAML frontmatter (`.claude/agents/`, `~/.claude/agents/`, plugin `agents/`, `--agent`). Frontmatter: `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `memory` (persistent auto memory), `isolation` (`worktree`), `context` (`fork`), `background`. Invocation: natural-language auto-delegation, `/agents`, `Agent(...)` tool, forked-skill context. Foreground/background, nestable (subagents can themselves spawn subagents; each level gets its own context window), background-permission surfacing in the main session, `/agents` UI, pinned worktrees. Built-ins: Explore, Plan, general-purpose.

### Zrb

**File-based agents** (`.agent.md` / `AGENT.md` / `.agent.py` / plain `.md` in `agents/`):
- Frontmatter: `name`, `description`, `model`, `tools` (YAML list **or** comma-separated string), `disallowedTools` (removes tools after the allowlist/factories resolve; list or comma-separated), and **`inherit_sections`** (🔵 Zrb-specific — the sub-agent inherits named PromptManager sections from the main agent).
- Discovery from search dirs (home → project → plugins → builtin); built-ins gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`. Built-in agents (`src/zrb/llm_plugin/agents/`): `generalist`, `researcher`, `code-reviewer`.

**Delegation tools**:
- `DelegateToAgent(...)` handles **both single and parallel** delegation: an optional `tasks: list[dict]` fans out concurrently with a shared UI lock + rate limiter, scope-clamped via a DELIVERABLE/NON-GOALS/TASK/CONTEXT envelope.
- **Background delegation**: `DelegateToAgentBackground` + `GetDelegationResult` — fire-and-forget detached `asyncio` tasks that inherit parent context (UI, yolo, policy, sandbox, approval channel, agent mode) via a ContextVar snapshot; approvals route through the parent UI's confirmation queue. `GetDelegationResult` supports a **bounded `wait=`/`kill=`** (blocks up to `min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)`), collapsing repeated polling. Plan-mode parents cannot start one (DELEGATE denied by the policy gate).
- `SubAgentManager` (nested `manager/` package) with lazy filesystem loading; `LLMConfig.resolve_model()`.
- **Inheritance**: YOLO, tool-guidance, and permission-policy + sandbox-policy all propagate to sub-agents via ContextVar. `SUBAGENT_START`/`SUBAGENT_STOP` hooks fire on the parent run's hook manager.
- **Observability**: a live activity panel (§2) shows every running sub-agent with ordinal labels.

**Status**: 🟡 **Partially supported**

**Difference that matters**: both do file-based definitions + delegation with foreground/parallel/background modes and policy inheritance. The divergence: Claude Code's subagents are *auto-delegated* (the model decides to spawn one from a natural-language description match) and can nest (a subagent spawns its own subagents) with worktree isolation, persistent per-agent `memory`, and per-agent `maxTurns`/`effort`; Zrb's are *explicitly invoked* through a delegation tool (no natural-language auto-routing), single-level, and lack per-agent turn/effort caps and worktree isolation. Conversely, Zrb's `inherit_sections` (compose a sub-agent's prompt from the parent's sections) has no Claude Code analog.

**Gap**: no natural-language auto-delegation, no `/agents` UI, no nested orchestration, no worktree isolation for agents, no persistent per-agent memory; frontmatter lacks `maxTurns`, `effort`, `memory`, `isolation: worktree`.

**Effort to close**: **High** (4–6 weeks): auto-delegation (3–4d), `/agents` UI (3–4d), per-agent policy/maxTurns (~1wk), subagent-scoped MCP (~1wk), worktree isolation (1–2wk).

---

## 8. Agent Teams & Dynamic Workflows

### Claude Code

- **Agent Teams** (experimental; gated behind `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`): a lead + teammates architecture with inter-agent `SendMessage`; a shared task list (`/tasks`, backed by `~/.claude/teams/{team}/`); display modes (`in-process` default / `tmux` / `iterm2` via `--teammate-mode`); plan-approval gates; quality-gate hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`).
- **Dynamic Workflows**: the `Workflow` tool orchestrates many background agents via deterministic JS scripts (`agent()` / `pipeline()` fan-out, structured-output schemas, budget-aware loops; caps ~1000 agents/run, 16 concurrent, large-workflow warning at 25+ agents or ~1.5M projected tokens); `/workflows` monitoring UI (pause/resume/stop/restart); bundled `/deep-research`; saveable, `args`-parameterizable run scripts. **Ultracode** (`/effort ultracode`, or the keyword `ultracode` in a prompt) pairs `xhigh` effort with automatic workflow planning.

### Zrb

`DelegateToAgent` with an optional `tasks` list (concurrent multi-agent, aggregated results, shared rate limiter + UI lock, per-agent error handling) plus `DelegateToAgentBackground` / `GetDelegationResult` (fire-and-forget background sub-agents with bounded-wait polling). No persistent team lifecycle, no inter-agent messaging, no shared task list with dependencies, no script-orchestrated fan-out, no workflow-monitoring UI.

Adjacent building block: Zrb's own **DAG task engine** (`CmdTask`, `LLMTask`, dependencies, retries, cycle detection) is a deterministic orchestration runtime — but it orchestrates *tasks*, not a fleet of LLM agents, and it isn't driven by an in-session `Workflow` tool.

**Status**: ❌ **Not supported** (parallel + background delegation exist; teams and scripted workflows do not)

**Difference that matters**: this is the widest structural gap. Claude Code's Workflow runtime is a *model-authored, deterministically-executed* orchestration layer (the model writes a JS script that fans out agents and the harness runs it); Zrb has no equivalent seam. Zrb's DAG engine is human-authored Python, not model-authored, and its delegation is single tool calls returning aggregated/polled results — a coordination primitive, not a team.

**Gap**: team lifecycle, inter-agent `SendMessage`, shared task list with dependencies, tmux/iterm2 display, the `Workflow` tool + `/workflows` UI + scripted fan-out.

**Effort to close**: **Very High** (8–12 weeks) — a fundamentally different architecture; the DAG engine + parallel/background delegate are partial building blocks for the workflow side.

---

## 9. Skills System

### Claude Code

File-based skills (`.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md`). Scopes managed > personal > project > plugin. Frontmatter: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context` (fork), `agent`, `hooks`, `paths`, `shell` (`bash`/`powershell`). Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$name`, `$CLAUDE_SESSION_ID`, `$CLAUDE_SKILL_DIR`, `${CLAUDE_EFFORT}`. Dynamic context `` !`command` ``, forked context, `paths:` glob activation, nested/monorepo discovery, hotreload, `/reload-skills`. Bundled: `/batch`, `/claude-api`, `/debug`, `/loop`, `/code-review`, `/deep-research`, `/run`, `/verify`. Follows the [Agent Skills](https://agentskills.io) standard.

### Zrb

Skill system (`src/zrb/llm/skill/`):
- File types `.skill.md`, `.skill.py`, `SKILL.md`, `SKILL.py`.
- Scopes default plugin > user plugins > global (`~/.claude/skills/`, `~/.zrb/skills/`) > project (`.claude/skills/`, `.zrb/skills/`).
- Frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context`, `agent`, **`hooks`** (skill-defined hooks).
- **Companion-file discovery**: `ActivateSkill` returns the skill directory path + grouped companion-file listing (`discover_companion_files()` / `format_companion_file_lines()`).
- Lazy scan + content caching; factory-function skills; `get_skill_custom_command()`.

**Built-in plugin** (`src/zrb/llm_plugin/`) — three governable categories (ADR-0069):
- **`core_skills/`** — always-on methodology hubs (`core-coding`, `core-research`, `core-design`, `core-writing`, `core-journaling`), no toggle.
- **`skills/`** — utility skills gated by `CFG.LLM_ENABLE_BUILTIN_SKILLS` (`debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`).
- **`agents/`** — sub-agents gated by `CFG.LLM_ENABLE_BUILTIN_AGENTS`.
- `core-coding` companions: `languages/` (python, typescript, go, rust, java, ruby, php) + `workflows/` (testing, debug, refactor, review) + an observability companion.
- The skill catalogue is folded into the byte-stable `mandate` section via `{CORE_SKILLS}`/`{AVAILABLE_SKILLS}`/`{PREACTIVATED_SKILLS}` placeholders (ADR-0079); core skills are listed separately from model-invocable skills; activation is auto-approved, silent, once per session/domain.

**Status**: ✅ **Mostly supported** (minor gaps)

**Difference that matters**: this is the closest-to-parity area, and Zrb reads Claude Code's own `.claude/skills/` layout, so skills are largely portable. Zrb's addition is the **governable core/utility/agent split** — an always-on methodology layer (`core_skills/`) that the utility skills delegate into, with independent toggles — which is a stronger opinion about skill *organization* than Claude Code's flat scope model. Claude Code's edge is activation richness: `paths:` glob activation, `shell` selection, `effort`, and `` !`command` `` dynamic injection.

**Gap**: no `effort` / `${CLAUDE_EFFORT}` (Zrb has no effort concept), no `disallowed-tools` on skills (it exists on *agents*, §7), no `paths:` activation, no `shell` field, no `` !`command` `` injection, no `$CLAUDE_SESSION_ID`/`$CLAUDE_SKILL_DIR` substitutions, no hotreload, no bundled `/batch`/`/loop`/`/verify`.

**Effort to close**: **Low** (1–2 weeks).

---

## 10. Permission Modes & Tool Approval

### Claude Code

**Modes** (Shift+Tab): `default` (ask), `acceptEdits`, `plan`, `auto` (background safety classifier), `dontAsk`, `bypassPermissions`. `--permission-mode`; `defaultMode`. Rules `Tool`/`Tool(specifier)`/globs/domains/MCP patterns/`Tool(param:value)` (`Bash(npm run *)`, `Read(//path/**)`, `WebFetch(domain:…)`, `Agent(model:opus)`); evaluation deny > ask > allow; config managed > CLI > local > project > user; destructive-git blocking; `PermissionRequest`/`PermissionDenied` hooks.

### Zrb

**Permission policy engine** (`src/zrb/llm/permission/`, ADR-0049–0057, 0067, 0078):
- **Capability tags** (`capability.py`): `READ`, `EDIT`, `EXECUTE`, `NETWORK`, `DELEGATE`, `META`, `UNKNOWN` (safe-by-default); tools tagged centrally in `common_tools.py`.
- **Rules** (`policy.py`): ordered, **first-match-wins** `Rule(key, action, arg_pattern)` where `key` ∈ {tool name, capability, `"*"`}, `action` ∈ {`allow`, `ask`, `deny`}, `arg_pattern` an `fnmatch` glob over salient args (`path`/`file_path`/`command`/`url`/`agent_name`/…). `decide(...)` resolves exact tool → capability → `"*"` → None.
- **Plan mode**: `AgentMode` enum (`BUILD`/`PLAN`); `EnterPlanMode`/`ExitPlanMode` tools (tagged `META`). Preset `PLAN_MODE_POLICY` allows READ/META/NETWORK, denies EDIT/EXECUTE/DELEGATE, asks before `ExitPlanMode`; enforced by `_permission_gate`. `AgentModeState` is a ContextVar holder so per-tool asyncio tasks observe mode changes; scopes isolate concurrent runs.
- **`auto-accept-edits`**: selective YOLO over `{Write, Edit}`; one of the three Shift+Tab-cycled modes (§2).
- **YOLO as policy** (`from_yolo`): `True` → `Rule("*", allow)`; `False` → `Rule("*", ask)`; tool-name set → per-tool `allow` + `"*"` ask. Full + selective YOLO propagate to sub-agents.
- **First-class `permissions=` / `sandbox=` on both `LLMChatTask` and `LLMTask`** (ADR-0078): read/write properties; precedence explicit arg > `ZRB_LLM_PERMISSIONS` env > ambient ContextVar; plan mode overrides all. Exported `PermissionPolicyInput` / `SandboxInput` types.
- **Approval chain** (`permission_policy → tool_policy → yolo`): `deny` stops at the gate; `allow` bypasses lower checks; `DelegateToAgent`'s roster is filtered by the active policy at render time; a `PRE_TOOL_USE` hook's `ask` can force the prompt even over ALLOW/YOLO.
- **Auto-approve predicates** (`tool_call/tool_policy/`): path-inside-cwd, inside-journal-dir, inside-skill/plugin-dir, mv-inside-journal-dir; per-tool validation; **`bash_safe_command_policy`** auto-approves read-only commands and rejects dangerous metacharacters (bare `&`, newlines/CR, `env`-prefixed commands).
- `ApprovalChannel` + `MultiplexApprovalChannel` (first-response-wins); override tool args at approval time (`ApprovalResult.override_args`).

**Status**: 🟡 **Partially supported** (strong)

**Difference that matters**: both are rule engines with Shift+Tab modes and deny>ask>allow precedence, and both express modes as rule sets. Zrb's model is **capability-first** (tools carry `READ`/`EDIT`/`EXECUTE`/… tags, so a rule can target a whole capability class) — Claude Code's is tool-and-specifier-first. Zrb also makes the policy a **first-class constructor arg** on the task (programmatic, per-task), whereas Claude Code's lives in layered settings files. Claude Code's edge is the *managed* layer (admin/MDM policy) and richer specifiers (`WebFetch(domain:…)`, `Tool(param:value)`).

**Gap**: no dedicated `dontAsk`/`bypassPermissions` presets, no `--permission-mode` flag, no domain-pattern rules for web tools or `Tool(param:value)` matching, no unconditional `hard_deny` tier, no destructive-git auto-blocking, no admin-managed layer.

**Effort to close**: **Low–Medium** (1.5–2.5 weeks): presets (1–2d), `--permission-mode` (1–2d), domain/param matching (2–3d), `hard_deny` (2d), managed layer (depends on §11).

---

## 11. Settings & Configuration System

### Claude Code

4 scopes: managed > user (`~/.claude/settings.json`) > project (`.claude/settings.json`) > local (`.claude/settings.local.json`); JSON schema; `/config` tabbed UI + `/config key=value`; global `~/.claude.json`; `--settings` override, `--setting-sources`, `--safe-mode`; server-managed settings (claude.ai admin, MDM, `managed-settings.json`).

### Zrb

**Single config source**: the `CFG` singleton (`src/zrb/config/`), env vars (prefix `ZRB_`, or a white-labeled `CFG.ENV_PREFIX`), composed from mixins (`foundation`, `web`, `llm_core`, `llm_ui` [+ commands/runtime/styles], `llm_limits`, `llm_content`, `llm_prompt`, `llm_search`, `llm_sandbox`, `llm_voice`, `cli_style`, `theme`, `rag`, `internet_search`, `hooks`, `task_runtime`). `CFG.FOO` stays flat regardless of owning mixin.
- **`EnvField` data descriptor**: empty env treated as unset; supports `fallback` (graceful cast-failure degradation), `transform` (sibling-dependent post-read), `no_prefix=True` (bare names like `BRAVE_API_KEY`), and **`secret=True`** (shown as `[set]`/`[unset]` in `config explain` — applied to API keys and passwords).
- **`zrb config explain`**: lists every `EnvField`-backed knob as a markdown table (env var, current value, description), with a `--keyword` filter.
- **Boolean naming convention** (ADR-0073): `<NS>_ENABLED` for namespace master switches; verb-first (`ENABLE_`/`SHOW_`/…) for standalone toggles.
- **Named themes** (ADR-0084): `ZRB_THEME` (`dark`/`light`, extensible via `register_theme`) supplies defaults for ~40 style knobs at once; individual knobs still override.
- All magic numbers configurable; `add_tool_guidance()` per-tool hints; config-positioned custom prompt sections (ADR-0061); consolidated model pipeline (`LLMConfig.resolve_model()`).

**Status**: 🟡 **Partially supported**

**Difference that matters**: the two take opposite stances. Claude Code is **file-first with layered scopes** (managed/user/project/local JSON, merged and admin-overridable) plus a `/config` UI; Zrb is **env-var-first with a flat namespace** and no file layer — but it compensates on *discoverability* (`config explain` enumerates every knob with current value and doc) and *white-labeling* (the whole env prefix is configurable). Zrb reads `.claude/settings.json` **only for hooks** (§5), not for general settings. The managed/enterprise policy layer is the real absence.

**Gap**: no JSON settings files, no layered scopes, no `/config` UI, no JSON schema, no managed/enterprise policy.

**Effort to close**: **Medium** (2–3 weeks): JSON loader + scope hierarchy (1wk), merge with env (2d), JSON schema (2–3d), `/config` UI (1wk).

---

## 12. Built-in Tools

### Claude Code (~45 tools)

| Tool | Status in Zrb |
|------|--------------|
| `Read` | ✅ `read_file` — explicit `start_line`/`end_line`, range validation, **PDF text extraction** (pdfplumber) |
| `Write` | ✅ `write_file` — post-write LSP/static diagnostics |
| `Edit` | ✅ `replace_in_file` — fuzzy match + post-edit diagnostics; rejects empty `old_text` |
| `Bash` | ✅ `run_bash_command` + `run_shell_command` (`Shell`, `CFG.SHELL`); `background=True`; 8 MB stream line limit; tail-truncates + dumps full output to a recoverable temp log; runs sync tools via `asyncio.to_thread` so the TUI loop never freezes |
| `PowerShell` | 🟡 `Shell` resolves to `pwsh`/`powershell` on Windows; no dedicated tool |
| `Glob` | ✅ `glob_files` |
| `Grep` | ✅ `search_files` (ripgrep-accelerated; char-budget bound) |
| `Agent` (spawn subagent) | 🟡 `DelegateToAgent` (single + parallel via `tasks`) / `DelegateToAgentBackground` + `GetDelegationResult` |
| `WebFetch` | ✅ `open_web_page` (`OpenWebPage`) — HTML→markdown, **PDF fetch** (`.pdf` URLs or `application/pdf` content-type, incl. extensionless viewer URLs); output capped to `LLM_MAX_OUTPUT_CHARS` |
| `WebSearch` | ✅ `search_internet` (Google News RSS default, SearXNG/Brave/SerpAPI) |
| `AskUserQuestion` | ✅ `AskUserQuestion` — intrinsic auto-approval (ADR-0062); arrow-key selection UI |
| `NotebookEdit` | ❌ Not implemented |
| `LSP` | ✅ Full suite incl. `LspRenameSymbol` (pyright/pylsp/gopls — §23) |
| `EnterPlanMode` / `ExitPlanMode` | ✅ Enforced read-only policy via the engine (§10) |
| `EnterWorktree` / `ExitWorktree` | ✅ `enter_worktree`/`exit_worktree`/`list_worktrees` (ContextVar tracking; register only inside a git repo) |
| `TaskCreate/Get/List/Update/Stop` | 🟡 `write_todos`/`get_todos` (system-context integration; update/clear folded into `write_todos`) |
| `Monitor` (background event stream) | 🟡 `MonitorProcess` (poll/kill background shell) — process-scoped, not a general stream |
| `CronCreate/Delete/List` | ❌ Not LLM tools (task-level `Scheduler` exists — §30) |
| `Skill` (invoke skills) | ✅ `ActivateSkill` (returns companion files) |
| `ToolSearch` (deferred tools) | 🟡 Framework-level `defer_loading=True` (no explicit model-facing search tool — see below) |
| `ListMcpResourcesTool` / `ReadMcpResourceTool` | ❌ Not implemented |
| `SendMessage` (agent teams) | ❌ Teams not implemented |
| `Workflow` (dynamic workflows) | ❌ Not implemented |
| `Artifact` (publish HTML/MD to claude.ai) | ❌ Not implemented (Zrb has a local web UI instead) |
| `RemoteTrigger` / `PushNotification` / `ScheduleWakeup` | ❌ Not implemented |

**Deferred loading** (the `ToolSearch` analog): delegate tools, `analyze_code`/`analyze_file`, worktree tools, LSP tools, plan-mode tools, skill activation, `MonitorProcess`, and MCP toolsets all register with `defer_loading=True`, keeping their schemas out of every turn until the model references them by name; the Tool Usage Guide still lists them so nothing is lost but the standing token cost. This achieves the same token saving as Claude Code's `ToolSearch` — but *transparently* (the framework resolves the schema on reference) rather than via an explicit `ToolSearch` tool the model must call.

**Background execution**: `Shell`/`Bash` take `background=True` and route through the normal approval policy; `MonitorProcess` polls/kills the detached process (cross-platform via `start_new_session=True` + `psutil` teardown).

**Tool-output backstop** (ADR-0052): global `LLM_MAX_TOOL_RESULT_CHARS` truncates model-facing `content` (directional head/tail + re-fetch hint) while preserving structured `return_value`. JSON payloads truncate the dominant text field *inside* the dict and re-serialize so the result is always valid JSON.

**Post-write/edit diagnostics** (`tool/post_write_check.py`): after `write_file`/`replace_in_file`, runs LSP `get_diagnostics()` + static checks (Python `ast.parse` + `pyflakes`), appending a `[DIAGNOSTIC]` block; file-tool errors attach `[SYSTEM SUGGESTION]` recovery hints.

**Zrb-only tools** 🔵: `RM` (`remove_file`), `MV` (`move_file`), `SearchJournal`, `AnalyzeFile` (AST), `AnalyzeCode` (LLM sub-agent), `create_rag_from_directory` (ChromaDB semantic search), `List{Root}Tasks`/`Run{Root}Task` (discover + run any Zrb task as a tool), a read-only `git` tool for the changelog generator, and a developer-utility task library (`hash`, `time`, `url`, `json`, `case`, `cron parse`, `hex`, `number`, `random`, `jwt`, `http request`, `base64`, `ulid`).

**Status**: 🟡 **Partially supported** (core file/shell/web/worktree/LSP/todo/plan/background well-covered)

**Difference that matters**: Zrb's tool layer is hardened around the *multi-provider, terminal-hosted* reality — payload capping, valid-JSON truncation, binary-content preservation, `asyncio.to_thread` offload so tools don't freeze the event loop, recoverable temp logs — edges that a managed single-provider harness doesn't have to fight. The absences (`NotebookEdit`, `Cron*`, `Workflow`, `Artifact`, resource tools, `SendMessage`) are all features tied to Claude Code's cloud/desktop/teams surface rather than the local agent loop.

**Effort to close**: **Medium** (2–3 weeks): `NotebookEdit` (3–4d), Cron tools (3–4d, reuse `Scheduler`), unified `Monitor` (2–3d), MCP resource tools (2–3d).

---

## 13. IDE Integrations

### Claude Code

VS Code extension (panel/sidebar/tab, inline diff accept/reject, `@`-mention, selection context, drag attachments, multi-conversation tabs, IDE MCP server, auto-install); JetBrains plugin (interactive diff, Shift+Tab cycling); Desktop app (macOS/Windows, visual diff, side-by-side sessions, Dispatch, scheduled tasks, push notifications); Chrome extension (web testing + screenshots); `--ide`, `/teleport` to/from web.

### Zrb

A **local web UI** (FastAPI) at `http://localhost:21213` — browser chat, session persistence, model switching, YOLO toggle, JWT auth, SSE streaming, ChatGPT-like layout, browser tool approval (edit-args), HTTP Chat API, Jinja2 + local mermaid.js. No VS Code / JetBrains / Desktop / Chrome integration.

**Status**: ❌ **Not supported** (IDE); 🟡 the web UI is a different paradigm (§15).

**Difference that matters**: Claude Code embeds *into the editor*; Zrb ships *its own surface* (terminal + browser). For an IDE-centric workflow this is a hard gap; for a headless/server workflow the web UI is arguably better placed.

**Effort to close**: **Very High** (3–6 months for real parity).

---

## 14. Session Management & Checkpointing

### Claude Code

Auto checkpoint before every edit and per prompt (`fileCheckpointingEnabled`); 30-day retention; Esc+Esc rewind menu; `/rewind`/`/rewind-all`; `/branch`/`--fork-session`; sessions per cwd; `--continue`/`-c`, `--resume`/`-r` (id/name/picker), `--name`/`-n`, `--session-id`, `/rename`, `--from-pr`, `--no-session-persistence`, `/export`, `/search`, `/usage`, resumable background sessions, `/teleport`.

### Zrb

- `FileHistoryManager` → JSON history (`~/.zrb/history/{name}.json`); named sessions via `--session`; **crash-safe writes** (`.tmp` file + atomic rename so a crash mid-write can't truncate the live conversation).
- **In-RAM LRU cache** (`_MAX_CACHED_CONVERSATIONS = 8`, dirty-entry tracking); **backup rotation** (`LLM_HISTORY_BACKUP_RETAIN`, live file excluded); `NoSaveHistoryManager` for ephemeral sessions; fuzzy session search on `/load`.
- **SQLite-backed sessions** via `ChatSessionManager` for the web UI.
- **Snapshot / rewind** (`SnapshotManager`, shadow git repos): `/rewind` picker, 3 restore modes, incremental sync + `DEFAULT_IGNORE_DIRS`; `LLM_ENABLE_REWIND`, `LLM_SNAPSHOT_DIR`.
- **Interrupt-preserving**: Escape saves the user message + `[SYSTEM: Response was interrupted]`; on Escape/unrecoverable error, completed tool calls + results are captured (`PartialRunAccumulator`) and appended as a `[SYSTEM: PREVIOUS ATTEMPT FAILED]` summary so the next turn continues instead of repeating.
- **`/copy` transcript export**: clipboard or file, full (untruncated) mode.

**Status**: 🟡 **Partially supported**

**Difference that matters**: both checkpoint to a shadow git store and offer rewind. Claude Code checkpoints *automatically* (before every edit) with 30-day retention and an Esc+Esc menu; Zrb's rewind is *opt-in* (`LLM_ENABLE_REWIND`) with a `/rewind` picker. Zrb's distinctive strength is *turn-continuity under failure* — the partial-run accumulator that lets an interrupted turn resume with its completed work intact, which matters more in a multi-provider world where transient errors are common. Claude Code's edge is session *plumbing*: branching/forking, resume-by-id picker, `/export`, `/search`, `--from-pr`.

**Gap**: rewind not automatic; no Esc+Esc shortcut; no branching/forking; no resume-by-id picker; no startup `--name`; no `/export` (partly covered by `/copy <file>`); no `/search` over history; no `--from-pr`.

**Effort to close**: **Medium** (2–3 weeks): enable rewind by default (1d), Esc+Esc (1–2d), branching (1wk), resume picker (2–3d), `--name` (1d).

---

## 15. Web UI

### Claude Code

No built-in web UI in local mode. Web access via `claude.ai/code` (cloud, subscription) with `--remote`/`--teleport` bridging.

### Zrb

🔵 **Zrb-only**: a FastAPI web UI — browser chat (`http://localhost:21213`), SSE streaming (incl. `todo_progress`), SQLite session persistence, model switching, YOLO toggle, JWT auth (guest + admin), SSL/TLS, task browsing/execution, REST API (`/api/v1/chat/`), ChatGPT-like layout, `HTTPChatApprovalChannel` (browser tool approval with edit-args), Jinja2 + local mermaid.js.
- **Security hardening**: JWT `type == "access"` claim enforced; `Secure` (configurable via `WEB_ENABLE_SECURE_COOKIES`) + `SameSite=Lax` + `HttpOnly` cookies; constant-time `is_password_match`; `shlex.quote` on task args; input `to_html()` HTML-escapes name/description/default; `StaticFiles` mount owns `/static` (no hand-rolled traversal-prone route); `WEB_AUTH_ENABLED` master switch.
- **Chat-API authorization**: every chat API route enforces the `can_access_task` gate.
- **Concurrent-session isolation**: `ChatSessionManager.task_lock`; per-run mode/policy ContextVar isolation; a failed/timed-out request no longer kills the session loop.

**Status**: 🔵 **Zrb advantage** — a hardened, self-hosted web UI with no cloud dependency; Claude Code's browser access is a cloud subscription product.

---

## 16. Auto Mode (Safety Classifier)

### Claude Code

A background classifier reviews each action before execution; it sees user messages + tool calls (not Claude's text — anti-injection); default block (download+execute, prod deploys, mass deletes, IAM) / allow (local file ops, deps, read-only HTTP); evaluates subagent spawns; falls back to prompting; `auto-mode` config; `useAutoModeDuringPlan`. Research preview on Anthropic (claude.ai/SDK/API); not yet on Bedrock/Vertex/Foundry.

### Zrb

No model-in-the-loop pre-action classifier. The **permission policy engine** (§10) + `bash_safe_command_policy` metacharacter rejection + the **sandbox** (§18) provide rule-based and OS-level containment. The `STOP_FAILURE` error-classification taxonomy (§5) is a hookable substrate for retry/escalation, but not a pre-action intent classifier.

**Status**: ❌ **Not supported**

**Difference that matters**: Zrb's safety is *deterministic* (rules + OS sandbox), which is auditable and provider-independent but cannot reason about novel intent; Claude Code's auto-mode *reasons* about each action but is a research preview tied to Anthropic-hosted models. Zrb's policy engine and sandbox are the natural enforcement points a classifier's verdicts would plug into.

**Effort to close**: **High** (4–6 weeks): pre-action classification hook (1wk), default block/allow rules (1wk), config layered onto the policy engine (1wk), fallback + mode integration (1wk+).

---

## 17. GitHub / CI/CD Integration

### Claude Code

GitHub Actions (`@claude` triggers), GitLab CI, GitHub Code Review bot, `/install-github-app`, `--from-pr`, `/pr-comments`, PR status footer, `/security-review`, Slack integration, `/batch` (parallel worktree agents each opening a PR), `claude ultrareview` (non-interactive CI review), `/code-review --fix`.

### Zrb

🔵 **Zrb-only strengths**: a task-automation system with Git utilities (`src/zrb/builtin/git`); `run_shell_command` can drive `gh`/`glab`/`git` (both `gh` and `glab` detected); RAG tools; a `review` built-in skill (structured code + security review); a `git-summary` skill (drafts only; commit/PR on explicit request).
- **`zrb git changelog generate`**: generates one changelog file per git tag via the LLM (incremental — skips tags with existing files), configurable regex/sort/template, `--stat`-first diff strategy skipping lock files, initial-release handling via the empty-tree object, graceful degradation; the LLM gets a read-only `git` tool.

A CI workflow exists for Zrb's own tests (`.github/workflows/test.yml`), but there is no native GitHub app, PR-comment trigger, Slack, or Code Review bot.

**Status**: ❌ **Not supported** (for GitHub/Slack integration)

**Difference that matters**: Claude Code integrates *as a bot into the forge* (mention-triggered, PR-commenting, CI-runnable); Zrb integrates *the forge into a task* (drive `gh`/`glab` from a task, generate changelogs). Same tools, opposite direction of control.

**Effort to close**: **High** (4–8 weeks): GH Actions template calling `zrb llm chat -p` (1–2d), GitLab template (1d), PR footer via `gh` (1–2d), `/security-review` from the `review` skill (1d), webhook → Zrb trigger (2–3wk), Slack bot (2–3wk).

---

## 18. Sandboxing

### Claude Code

OS-level Bash sandboxing (macOS Seatbelt, Linux/WSL bubblewrap): `sandbox.enabled`, `excludedCommands`, `allowUnsandboxedCommands`, `filesystem.allowWrite/allowRead/denyWrite/denyRead`, `network.allowedDomains/deniedDomains/proxy`, `credentials` (credential-file blocking), `allowAppleEvents`, managed-read/domain-only enforcement. `/sandbox` command; `autoAllowBashIfSandboxed`.

### Zrb

🔵 **Opt-in FS + OS sandbox** (`src/zrb/llm/sandbox/`, ADR-0063, ADR-0078):
- **`SandboxPolicy`** (frozen dataclass): `enabled`, `writable_paths` (empty = auto: cwd + `/tmp`), `deny_read_paths` (defaults to credential stores — `~/.ssh`, `~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.gnupg`, `~/.netrc`, `~/.npmrc`, `~/.git-credentials`, `~/Library/Keychains`, …), `os_shell` (`auto`/`off`), `fallback` (`warn`/`deny`), `allow_escape`.
- **Two enforcement layers**: (1) a Python-level FS gate (`_sandbox_gate`, right after `_permission_gate`) blocks writes outside writable roots (EDIT/UNKNOWN tools) and reads of credential dirs (all tools) via `check_read()`/`check_write()`, with Windows `normcase` + cross-drive blocking; (2) an OS-level shell wrapper for `Shell`/`Bash` — macOS `sandbox-exec` + generated SBPL (last-match-wins), Linux `bwrap` (ro-bind root → writable binds → tmpfs/`/dev/null` deny-read masks).
- **First-class plumbing**: `--sandbox` CLI input (§1); `LLMChatTask(sandbox=…)` / `LLMTask(sandbox=…)` + read/write properties; `current_sandbox_policy` ContextVar (sub-agent inheritance); config `LLMSandboxMixin` (`ZRB_LLM_SANDBOX_ENABLED` default `false`, `_OS_SHELL`, `_WRITABLE_PATHS`, `_DENY_READ_PATHS`, `_FALLBACK`, `_ALLOW_ESCAPE`).
- Where no OS mechanism exists (Windows, Linux without bwrap), `fallback=warn` runs unsandboxed with a visible warning, `deny` refuses — never silent.
- **Escape hatch**: `dangerously_skip_sandbox` on shell tools — never auto-approved, blockable via `ALLOW_ESCAPE=false`, blocked at both layers, emits a `[NOTE]`.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the FS + credential-read enforcement is at parity (Seatbelt/bwrap on both). The single meaningful gap is **network sandboxing** — Claude Code can allow/deny domains and route through a proxy; Zrb keeps network open (enforcement is FS + OS-shell only). Zrb also lacks per-command exclusion granularity and a dedicated Windows mechanism.

**Effort to close**: **Medium** (2–3 weeks): network filtering via proxy or bwrap `--unshare-net` + allowlist (1–2wk), per-command exclusions (2–3d), Windows research (open-ended).

---

## 19. Remote & Cloud Sessions

### Claude Code

`--remote` (new web session), `--teleport`, `--remote-control`/`--rc`, `claude remote-control`; control from claude.ai/app; Channels (Telegram/Discord/iMessage/webhooks via MCP channel plugins); Dispatch (phone → Desktop); cloud sessions across devices; Remote Control MCP connectors with OAuth.

### Zrb

🔵 **Zrb-only building blocks**: a built-in web server (`zrb server start`), REST API, JWT, SSL/TLS; **MultiUI** (broadcast to terminal + Telegram + web, first-response-wins); **MultiplexApprovalChannel** (route approvals to multiple channels). No cloud sessions, Remote Control protocol, Channels plugin system, Dispatch, or multi-device sync.

**Status**: 🟡 **Different approach** — a local server + multi-channel fan-out, versus managed cloud infra.

**Difference that matters**: Zrb's "remote" is *you host it* (a server you can reach and multiplex over channels); Claude Code's is *they host it* (cloud sessions, device sync, Dispatch). One trades convenience for control.

**Effort to close**: **Low–Medium** for a remote API (the web server already provides it); **Medium** (2–3 weeks) for WebSocket remote control + channel plugins; **Very High** for true cloud sessions.

---

## 20. Plugins System

### Claude Code

Install from marketplace or local dir; `--plugin-dir`, `--plugin-url`; structure `hooks/`, `agents/`, `skills/`, `mcp.json`, output styles, `${CLAUDE_PLUGIN_DATA}`; `.claude-plugin/plugin.json` manifest; `defaultEnabled`; dependency enforcement; `/plugin install/list/disable/enable`, `/plugin marketplace add/remove`, `/reload-plugins`; channel plugins.

### Zrb

**Skill/Agent/Hook/MCP plugin dirs** (the closest analog): skills/agents/hooks loaded from multiple dirs; `CFG.LLM_PLUGIN_DIRS` (tilde-expanded); plugin dirs discovered via `.claude-plugin/plugin.json` (`scan_plugin_dirs`); MCP config from multiple locations; `add_hook_factory()`; the built-in plugin split into governable `core_skills`/`skills`/`agents` categories (ADR-0069). No formal packaging/marketplace, no `zrb plugin` command, no lifecycle management, no channel plugins.

**Status**: 🟡 **Partially supported** (loads the same plugin layout, but no packaging/marketplace)

**Difference that matters**: Zrb *consumes* the Claude plugin directory layout (so a plugin's skills/agents/hooks work), but treats plugins as filesystem content to discover, not as installable/versioned packages with a lifecycle. There is no install/enable/disable command and no marketplace.

**Effort to close**: **Medium** (3–4 weeks): package format (3–4d), `zrb plugin add` (1wk), full dir scanning (1wk), `/reload-plugins` (2d).

---

## 21. Rate Limiting & Budget Control

### Claude Code

`--max-budget-usd`, `/usage` (merged cost+stats; per-skill/agent/plugin/MCP tracking), rate-limit status in footer, `--fallback-model` (chain), per-turn token usage.

### Zrb

🔵 **Rate limiting + retry that exceeds the baseline**:
- `LLMLimiter`: requests/min + tokens/min (`ZRB_LLM_MAX_REQUEST_PER_MINUTE`, `ZRB_LLM_MAX_TOKEN_PER_MINUTE`), shared across sub-agents; a configured limiter of `0` blocks correctly.
- **`fit_context_window` is O(n)** (fast even at hundreds of turns).
- **Transient-error retry**: exponential backoff for HTTP 429/5xx, honors `Retry-After`, caps at `LLM_API_MAX_WAIT` / `LLM_API_MAX_RETRIES`; `STOP_FAILURE` exposes a classified error type.
- **Session token tracking**: the TUI status bar shows accumulated input/output tokens (`💸 1.5k in · 34 out`), reading `context_usage.input_tokens` directly (cache reads/writes already folded in, so no double-counting).

Missing: a per-session USD budget cap, a `/usage`/`/cost` command with cumulative spend and per-skill/agent breakdown, and a fallback-model chain on overload.

**Status**: 🟡 **Partially supported** (rate limiting + retry exceed Claude Code; a *budget* cap and cost UI are missing)

**Difference that matters**: Zrb tracks *tokens* (and enforces req/min + tok/min limits far beyond what the managed product exposes) but not *dollars* — it has no price table, so it can show `in/out` token totals but not `--max-budget-usd`. Claude Code, running on known Anthropic pricing, can meter spend and enforce a USD ceiling.

**Effort to close**: **Low** (3–5 days): cumulative token/cost tracking (2d — the token side already exists), `--max-budget` input (1d), `/cost` command (1d), fallback model in CFG (1d).

---

## 22. Platform Support

### Claude Code

macOS (Intel + Apple Silicon, Homebrew, Desktop), Linux (native, Docker), Windows (WSL + native, PowerShell/WinGet, Desktop; WSL image/screenshot paste), iOS/Android (mobile app, Dispatch), browser (claude.ai/code).

### Zrb

- macOS: ✅ Full (incl. Seatbelt sandbox).
- Linux: ✅ Full (incl. bwrap sandbox).
- Windows: 🟡 Cross-platform shell — `Shell`/`Bash` (incl. `background=True`) converge on shared primitives (`start_new_session=True`, `psutil` teardown, `resolve_shell()`); `get_current_shell()` existence-checks `pwsh`→`powershell`→`cmd`. Windows paths are unit-tested with mocks but not verified on a real Windows host; no native installer; sandbox falls back to warn/deny.
- Docker: 🔵 images available.
- Android/Termux: 🔵 documented (cold-import optimized — `import zrb` is ~0.4s after deferring the `pydantic_ai` import off the import path); Termux auto-detected (incl. proot distros via `ANDROID_ROOT`) with adaptive keybindings.
- Browser: 🔵 web UI via `zrb server start`.

**Status**: 🟡 Partial for Windows (unverified on hardware); ✅ excellent for macOS/Linux; 🔵 explicit Termux support.

**Difference that matters**: install/run stories differ — Claude Code ships native installers and a mobile app; Zrb installs via `pipx` (cross-platform, with autocomplete + optional LSP server install) and reaches mobile through Termux rather than a native app. Both cover macOS/Linux well; Windows is where Zrb is least proven.

---

## 23. LSP / Code Intelligence

### Claude Code

Built-in LSP tool: post-edit type errors/warnings; `find_definition`, `find_references`, `get_hover_info`, `list_symbols`, `find_implementations`, `trace_call_hierarchies`; requires a language plugin.

### Zrb

🔵 **Broader**: `LSPManager` singleton (lazy startup, idle timeout); symbol-based API; full suite (`find_definition`, `find_references`, `get_diagnostics`, `get_document_symbols`, `get_workspace_symbols`, `get_hover_info`, **`rename_symbol`** with dry-run + honest `applied` flag, `list_available_servers`); auto-detect servers (pyright, gopls, tsserver, rust-analyzer…); **`ZRB_LLM_LSP_PREFERRED_SERVERS`** (ordered preference); per-file project-root cache bounded at 4096 entries; all LSP tools auto-approved and deferred-loaded.
- **Correct wire protocol**: byte-accurate framing, documents opened before file-scoped queries, `textDocument/definition`, fixed `SymbolInformation` positions, graceful `get_workspace_symbols` fallback, stderr drained — verified against real pyright, pylsp, gopls.
- **User-extensible registry**: `LSPServerConfigRegistry` + `lsp_manager.register_lsp_server(...)` from `zrb_init.py`.

**Status**: ✅ **Fully supported** (Zrb arguably broader).

**Difference that matters**: Zrb adds `rename_symbol` (refactor, with dry-run), workspace symbols, preferred-server ordering, and a user-extensible server registry — capabilities beyond the read-oriented Claude Code LSP surface. Claude Code's `trace_call_hierarchies` is the one primitive Zrb doesn't expose by name.

---

## 24. Context Compaction & Prompt Caching

### Claude Code

Auto-compaction on limit; `/compact [instructions]`; `PreCompact`/`PostCompact` hooks; original transcript preserved in `.jsonl`. Prompt caching on by default; `--exclude-dynamic-system-prompt-sections` improves cache reuse; caches CLAUDE.md / project context / long instructions; re-attaches the first 5k tokens of each skill after compaction.

### Zrb

Two-layer auto-summarization:
- **Layer 1** (per-message): large tool results summarized in place.
- **Layer 2** (conversational): triggers on message/token thresholds (system-prompt-token-aware); respects tool call/return pairs; chunk-and-summarize with `<state_snapshot>` consolidation; **parallel chunk summarization** (`asyncio.gather`); `<active_skills>` tracked + restored; summarizers use `LLMConfig.resolve_model()`.
- Manual `/compress` / `/compact`; `PRE_COMPACT`/`POST_COMPACT` hooks fire (PreCompact can inject `additionalContext` and block); partial-run retry context on failure (§14).

**Prompt caching** (ADR-0065, ADR-0079, ADR-0082):
- The system prompt is **byte-stable across turns** so any provider's prefix cache hits. Session-invariant facts render into the cached system prompt; volatile per-turn state lives in a **`render_live_context()`** block wrapped as `<live-context>…</live-context>` and appended to the end of the current user turn (append-only, frozen into history). The journal index snapshot moved into that live block (ADR-0082), so a mid-session journal write no longer invalidates the cached prefix.
- The skill catalogue is folded into the byte-stable `mandate` section (ADR-0079) rather than a separately-recomputed section.
- **Tool-schema token reduction**: nullable params converted to non-nullable defaults (drops `anyOf:[type,null]` unions); trimmed docstrings; compact schemas for `DelegateToAgent`/`RunZrbTask`; rarely-used tools deferred (§12).
- Sub-agents are single-turn, so the live block folds back into their inherited system prompt.

**Status**: ✅ **At parity / strong**

**Difference that matters**: both keep a cacheable prefix and split volatile state out (Zrb's `<live-context>` is the direct analog of `--exclude-dynamic-system-prompt-sections`). Where Zrb differs is that its caching is **provider-agnostic by construction** — byte-stability is engineered so *any* provider's prefix cache hits, not just Anthropic's, which is the whole point given §33. The remaining gaps are cosmetic: no focus-instructions argument on manual compact, no original-transcript `.jsonl` preservation.

**Effort to close**: **Low** (2–4 days): focus-instructions arg (1–2d), transcript preservation (1–2d).

---

## 25. Prompt Composition & Model Adaptation

### Claude Code

A single, hand-tuned system prompt for its (Anthropic) model family, with `--system-prompt[-file]` / `--append-system-prompt[-file]` override and `--exclude-dynamic-system-prompt-sections` for cache reuse. Effort tiers (`low`→`max`) modulate reasoning depth; there is no user-facing per-section composition or per-model prompt-register switch — the product targets one model family.

### Zrb

🔵 **Composable, model-adaptive prompt** (`src/zrb/llm/prompt/`, ADR-0061, ADR-0083):
- **Section composition**: `PromptManager` assembles the prompt from ordered, MECE sections (`persona → mandate → examples → git_mandate → journal_mandate → system_context → project_context → tool_guidance`, then user prompts). Order is overridable via `include_sections` or `ZRB_LLM_INCLUDE_SECTIONS`. A non-built-in name resolves as a custom section (built-in > registered provider > markdown file), so downstreams add ordered sections without editing `PromptManager`.
- **Two independent axes**: *which* sections appear (above) and *how* each is phrased. `ZRB_LLM_PROFILE` (`terse`/`explicit`/`auto`, default `auto`) selects a **profile**: the base `*.md` files are the `terse` register; other profiles are variant overlays (`{name}.explicit.md`, falling back to the base), so only sections whose phrasing actually changes need a variant (currently `persona.explicit.md` + a few-shot `examples.explicit.md`).
- **Declared, not guessed**: `auto` resolves to `terse` unless a per-model profile was *declared* via `register_model_profile(pattern, profile)` — zrb makes no capability guess from a model id (family names span tiny→frontier). This mirrors the `model_capabilities` registry.

**Status**: 🔵 **Zrb advantage** — a composition + model-adaptation surface Claude Code doesn't need (it targets one model family) but that is essential for Zrb's any-provider story.

**Difference that matters**: this exists *because* of §33. Claude Code can hand-tune one prompt for one family; Zrb must phrase for a weak local model and a frontier one from the same codebase, so it separates topic (sections) from register (profile) and adapts the register per declared model. The design is grounded in a study of opencode's per-family monoliths, but avoids their duplication by composing MECE sections instead of copying whole prompts.

---

## 26. Voice Input

### Claude Code

Push-to-talk / hold dictation (`/mic`, `voice: {enabled, mode: "hold"/"push"}`, Option+M); CJK + long-silence handling. Runs as a desktop app with OS-level key-down/key-up events, so hold-to-record/release-to-transcribe works directly.

### Zrb

✅ **Opt-in voice dictation** (`src/zrb/llm/voice/`, `/voice`, ADR-0081): enable with `ZRB_LLM_VOICE_ENABLED=true`, then `/voice` toggles push-to-talk. Because a terminal (prompt_toolkit) emits only a single byte on key-press with **no key-release event**, the hold-to-talk model is impossible; Zrb uses **press-to-start / press-again-to-stop**: the first press of the push-to-talk key (`ZRB_LLM_VOICE_PUSH_TO_TALK_KEY`, default spacebar) starts recording, a second press stops it and exits voice mode. A 300ms debounce filters OS key-repeat so a held key can't self-trigger a stop. Transcribed text inserts at the cursor, enabling hybrid typing+voice. Four STT backends via `ZRB_LLM_VOICE_MODE`: `vosk` (offline default — model auto-downloads to `~/.cache/vosk/`, cancellable), `openai` (Whisper), `google` (Gemini STT), `multimodal` (uses `ZRB_LLM_MULTIMODAL_MODEL`). All audio deps are lazy-imported (no startup cost when disabled).

**Status**: ✅ **Supported** (via a terminal-appropriate interaction model)

**Difference that matters**: same feature, genuinely different mechanism forced by the runtime. Claude Code (desktop, OS key events) does hold-to-talk; Zrb (terminal, no key-release) does press/press with debounce, and offers an **offline default** (Vosk) plus API backends — a self-hosted-friendly choice Claude Code's cloud STT doesn't mirror.

---

## 27. Vim Mode & Editor Features

### Claude Code

Full Vim mode: NORMAL/INSERT, complete navigation/editing/text-objects, `/` reverse-search in NORMAL; `editorMode: "vim"`.

### Zrb

No Vim mode. Standard `prompt_toolkit` input (multiline, history, reverse search).

**Status**: ❌ **Not supported**

**Effort to close**: **Medium** (2–3 weeks) — `prompt_toolkit` ships a Vim key-binding layer, so this is wiring + testing rather than net-new.

---

## 28. Diff Viewer

### Claude Code

`/diff` interactive viewer (uncommitted + per-turn; keyboard scrolling, GFM task-list rendering); IDE accept/reject hunks; checkpoint-based diff.

### Zrb

No interactive diff viewer in the TUI. Changes apply directly; git diff via `run_shell_command`; tool-approval dialogs show formatted edits (with correct terminal-width detection via fd 0, so diffs render at real width even when stdout is captured).

**Status**: ❌ **Not supported** (in-TUI; available via shell + approval previews)

**Effort to close**: **Low–Medium** (1–2 weeks) — `/diff` via `unified_diff` + `rich`.

---

## 29. Task / Todo System

### Claude Code

`TaskCreate/Update/Get/List/Stop` (background bash tasks, unique IDs, auto-clean, Ctrl+T list); `TodoWrite` (session checklist, deprecated).

### Zrb

🔵 **Advantage**: `TodoManager` with persistent JSON (`~/.zrb/todos/{session}.json`); states `pending`/`in_progress`/`completed`/`cancelled`; auto IDs, timestamps, progress. Tool surface is **`write_todos`** (replace-semantics, subsumes update/clear) + **`get_todos`** (ADR-0068); a quantified trigger seeds the list before the first edit when work spans ≥3 steps / multiple files / turns. Session isolation + ContextVar wiring; a **todo progress card** pushes to the active UI (TUI/StdUI/web SSE `todo_progress`) after every change; **pending todos render into the live context every turn**. Plus 🔵 the full task-automation framework (`CmdTask`, `LLMTask`, DAG, dependencies, retries, scheduling — with cycle detection).

**Status**: ✅ **Fully supported** (Zrb advantage on persistence + live-context integration)

**Difference that matters**: Claude Code's todos are an ephemeral session checklist; Zrb's are *persistent, session-scoped, and continuously re-injected* into context and pushed to every UI surface — so the plan survives across turns and is visible in the terminal, stdout, and browser simultaneously. Claude Code separately has background *bash tasks* (`TaskCreate`) that Zrb models as background shell + `MonitorProcess` (§12) rather than a first-class task object.

---

## 30. Scheduling

### Claude Code

`CronCreate/Delete/List` tools (in-session recurring/one-shot prompts); `/schedule` (cloud tasks); `/loop [interval] <prompt>`; Desktop scheduled tasks; cloud scheduled tasks (persist when the machine is off).

### Zrb

🔵 **Advantage at the task level**: a full `Scheduler` task type (cron-based, correct weekday/day-of-month semantics — validated cron parsing: wildcard steps in lists, out-of-range rejection, `7`=Sunday; deduped fired-minute ticks; drift-clamped sleeps) + `CmdTask` scheduling, plus a `cron parse` developer utility. No `CronCreate/Delete/List` as in-session LLM tools; no `/loop`; no cloud scheduling.

**Status**: 🟡 **Partially supported** (robust task-level scheduling; not in-session LLM tools; no cloud)

**Difference that matters**: Zrb's scheduler is a *task-engine primitive* an author wires up in Python; Claude Code's is a *model-callable tool* the agent creates on the fly (plus a cloud tier that runs when your machine is off — which requires infra Zrb doesn't have). The engine is arguably more correct; the in-session ergonomics and cloud persistence are the gap.

**Effort to close**: **Low** for in-session (2–3d): wrap `Scheduler` as `CronCreate/Delete/List`. **Very High** for cloud.

---

## 31. Worktree Isolation

### Claude Code

First-class: `--worktree`/`-w`, `--tmux`; `isolation: worktree` in agent frontmatter; `EnterWorktree`/`ExitWorktree`; `WorktreeCreate`/`WorktreeRemove` hooks; `/batch`; `worktree.symlinkDirectories`/`sparsePaths`/`bgIsolation`/`baseRef`; `.worktreeinclude`.

### Zrb

**Worktree tools** (`src/zrb/llm/tool/worktree.py`): `enter_worktree(branch_name)`, `exit_worktree(worktree_path, keep_branch)`, `list_worktrees()`; wrapped in `tool_wrapper` (structured `{"error": …}`); registered only inside a git repo (and deferred-loaded).
- **ContextVar tracking**: `EnterWorktree` sets `active_worktree`, injected into every system context + delegate messages; the LLM is reminded to pass `cwd`/absolute paths; `.zrb/worktree/` auto-added to `.gitignore`; a stale-worktree guard clears the var if the path vanishes.
- Storage `{git_root}/.zrb/worktree/{branch_name}`.

**Status**: 🟡 **Partially supported**

**Difference that matters**: both expose worktree enter/exit tools with tracking. The gap is *isolation as a policy* — Claude Code can pin a subagent or a `/batch` fan-out into its own worktree (`isolation: worktree`) so parallel agents don't collide; Zrb has the tools but no per-agent isolation binding and no `--worktree` flag / worktree hooks.

**Effort to close**: **Medium** (2–3 weeks): `--worktree` flag (1–2d), `isolation: worktree` in agent defs (~1wk after §7 frontmatter work), worktree hooks (2d), `/batch` (2–3wk).

---

## 32. Multimodal & Attachments

### Claude Code

Native image input on vision models; clipboard paste (Ctrl+V/Cmd+V; WSL screenshot paste on Win 11); drag-as-attachment in IDE; `@`-mention files; PDF (page-ranged) + Jupyter notebook reads.

### Zrb

🔵 **Multimodal pipeline** (`src/zrb/llm/util/`):
- `LLM_MULTIMODAL_MODEL` designates a vision model to describe attachments when the main model is text-only.
- `LLM_MAX_IMAGE_DIMENSION` (1568, the Anthropic no-extra-cost tier) + `LLM_IMAGE_JPEG_QUALITY` (85): pasted / `/attach`-ed images auto-scaled; opaque→JPEG, alpha→PNG.
- `runner._apply_multimodal_fallback`: if the main model can't consume an image/audio, the multimodal model describes it and substitutes text; if none is configured the attachment is dropped with a `⚠️ Dropped <modality>` warning (never silently sent to a rejecting provider). Audio: describe/transcribe fallback. Video: kept for Gemini-class, dropped-with-warning otherwise.
- **PDF**: extracted to text (`extract_pdf_text()`, shared by `read_file`, the attachment pipeline, and `open_web_page`), with binary fallback when extraction fails.
- Per-model capability registry (`model_capabilities`) drives support detection; clipboard paste via Ctrl+V and Alt+V; `/model multimodal <name>` sets the vision model at runtime.

**Status**: ✅ **Fully supported / 🔵 advantage**

**Difference that matters**: Claude Code assumes a vision-capable model; Zrb assumes it *might not have one* and builds the describe-then-substitute fallback + explicit drop-with-warning around that reality — again a direct consequence of §33. PDF handling is unified across file/attachment/web paths. The absence vs Claude Code is *page-ranged* PDF reads and native Jupyter notebook reads (§12 `NotebookEdit` is also absent).

---

## 33. Provider Resilience & Multi-Model

### Claude Code

A single primary provider (Anthropic) with `--fallback-model` chain on overload; Bedrock/Vertex/Foundry deployments; opaque-error handling abstracted by the platform. Model lineup Opus 4.8, Sonnet 5, Haiku 4.5, Fable 5; effort tiers `low`→`max`; fast mode.

### Zrb

🔵 **Major advantage** — multi-provider robustness:
- Any model via Pydantic AI (OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock, Mistral…).
- **4-stage history sanitization** (`sanitize_history`): filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles.
- **Provider-specific 400 recovery**: DeepSeek `reasoning_content` rejection → `strip_thinking_parts` retry; GLM empty `ValidationException` retry; **generic opaque-400** → `strip_to_text_only()` collapse + single retry (provider-agnostic); Bedrock nil-content → `"."` placeholder; invalid-tool-call detection requires entity + problem keyword.
- **Empty-completion guard** (ADR-0059): regenerates blank / leaked `"(tool call)"` completions.
- **Parallel-tool-call guard**: `model_capabilities` injects `parallel_tool_calls=False` for known-malforming models.
- `request_limit=None` overrides pydantic-ai's 50-request tool-loop cap; `ModelRetry` is re-raised so pydantic-ai's retry protocol works; `create_agent` uses `tool_retries`.

**Status**: 🔵 **Zrb advantage** — far broader provider coverage and resilience than the Claude Code CLI exposes.

**Difference that matters**: this is Zrb's defining axis and the *cause* of several designs above (§24 provider-agnostic caching, §25 model-adaptive prompts, §26 offline STT, §32 text-only fallback). Claude Code's platform makes provider quirks invisible because there's effectively one provider; Zrb makes them *survivable* across a dozen, at the cost of carrying a resilience layer Claude Code never needs. The one thing Claude Code has here that Zrb doesn't is an automatic `--fallback-model` chain on overload.

---

## 34. Side Questions (`/btw`)

### Claude Code

`/btw <question>` — answered, but the Q&A pair is dropped from the transcript; doesn't interrupt in-progress work.

### Zrb

✅ Fully implemented (`_handle_btw_command` in `base_ui.py`): `/btw <question>` is answered in a temporary context and not appended to history; it shares the conversation context for relevant answers.

**Status**: ✅ **Fully supported**

**Difference that matters**: functionally identical. (Zrb answers from the current context but does not run a fresh side agent; both discard the exchange.)

---

## 35. Channels & Remote Control

### Claude Code

Remote Control (control a session from claude.ai/app; `--remote-control`/`--rc`, `claude remote-control`; MCP connectors with OAuth). Channels (push external events via MCP channel plugins: Telegram/Discord/iMessage/webhooks; `--channels`, `channelsEnabled`, `allowedChannelPlugins`). Dispatch (phone → Desktop).

### Zrb

🔵 **Existing**: MultiUI (CLI + Telegram + web simultaneously; broadcast output; first-response-wins input); MultiplexApprovalChannel (route approvals to multiple channels, denying only after every channel finishes without a result — so a slow human on the terminal isn't pre-empted by a fast erroring channel); HTTP Chat API (an external POST to `/api/v1/chat/sessions/{id}/messages` pushes a message into an active session — authorization-gated). No Remote Control protocol, native Channels plugin system, or Dispatch.

**Status**: 🟡 **Partially covered** (MultiUI + HTTP API cover core use cases; no standardized protocol)

**Difference that matters**: Zrb already *fans a single session out* over multiple channels (and merges their input) — which is close to what Channels does — but there's no plugin contract to add a new channel declaratively, and no cloud Remote Control protocol. Zrb's approach is code-configured multiplexing; Claude Code's is a plugin/connector ecosystem.

**Effort to close**: **Medium** (2–3 weeks): WebSocket remote control (1wk), a channel-plugin contract over the existing multiplexer (2wk).

---

## 36. Summary & Roadmap

### Overall Coverage

| Category | Status | Notes |
|----------|--------|-------|
| CLI Flags | 🟡 | Broad engine; only `--sandbox` exposed; 7 inputs vs ~70 flags |
| Interactive TUI | 🟡 | Shift+Tab modes, /copy, arrow-key choice, sub-agent panel, token bar, themes, voice |
| Slash Commands | 🟡 | Core infra + skill commands + PRE/POST_COMMAND hooks |
| Memory / CLAUDE.md | 🟡 | Doc auto-loading + structured journal graph; no local/imports/rules |
| Hooks | 🟡 | 16/~31 events, but near-parity control + drop-in CC command hooks |
| MCP | 🟡 | stdio + http; deferred-load; no sse/ws/OAuth/resources/prompts |
| Subagents | 🟡 | Single+parallel+background, policy/sandbox inheritance, disallowedTools, activity panel; no auto-delegation |
| Agent Teams & Dynamic Workflows | ❌ | Background delegate only; no teams / Workflow runtime |
| Skills | ✅ | Reads CC layout; governable core/utility/agent split; minor frontmatter gaps |
| Permission Modes | 🟡 | Capability-tagged engine + plan + auto-accept-edits + Shift+Tab + first-class args |
| Settings System | 🟡 | EnvField + `config explain` + white-label prefix; env-only, no JSON files |
| Built-in Tools | 🟡 | File/shell/web/LSP/todo/plan/background/worktree + PDF; hardened truncation/offload |
| IDE Integrations | ❌ | Web UI is a different paradigm |
| Session / Checkpoint | 🟡 | Rewind/snapshot, crash-safe writes, partial-run retry, /copy export |
| Web UI | 🔵 | Hardened, self-hosted local web UI not in the CC CLI |
| Auto Mode | ❌ | Policy + sandbox provide enforcement substrate; no classifier |
| GitHub/CI | ❌ | `git changelog generate`, gh/glab detect; no app/triggers |
| Sandboxing | 🟡 | FS+OS sandbox + credential deny-read + `--sandbox`; no network filtering |
| Remote/Cloud | 🟡 | Local server + multi-channel vs cloud |
| Plugins | 🟡 | Consumes CC plugin layout; no packaging/marketplace |
| Rate Limiting / Budget | 🟡 | Req/min + tok/min + retry + token bar exceed CC; no USD budget/cost UI |
| Platform Support | 🟡 | macOS/Linux excellent; Windows unverified; Termux support |
| LSP | ✅ 🔵 | Working wire protocol, rename, workspace symbols, extensible registry |
| Compaction & Prompt Caching | ✅ | Pre+Post hooks, parallel chunks, provider-agnostic byte-stable caching |
| Prompt Composition & Model Adaptation | 🔵 | MECE sections + declared per-model profiles |
| Voice Input | ✅ | Terminal-safe press/press; offline Vosk default + API backends |
| Vim Mode | ❌ | — |
| Diff Viewer | ❌ | In-TUI absent; shell + approval previews exist |
| Task / Todo | ✅ 🔵 | Persistent + live-context + progress cards + DAG framework |
| Scheduling | 🟡 | Robust task-level Scheduler; no in-session LLM tools; no cloud |
| Worktree Isolation | 🟡 | Tools + tracking + stale guard; no CLI flag / agent isolation |
| Multimodal & Attachments | ✅ 🔵 | Describe-then-substitute fallback; unified PDF; no page-range/notebook |
| Provider Resilience & Multi-Model | 🔵 | Any provider + deep resilience layer |
| Side Questions (`/btw`) | ✅ | Functionally identical |
| Channels & Remote Control | 🟡 | MultiUI + HTTP API multiplexing; no plugin contract/protocol |

### Where Zrb is a genuine superset

1. 🔵 **Any provider** via Pydantic AI, with a deep resilience layer (4-stage history sanitization, provider-agnostic opaque-400 recovery, per-model parallel-tool-call guard).
2. 🔵 **Model-adaptive prompt composition**: MECE sections × declared per-model phrasing profiles.
3. 🔵 **Multimodal fallback**: describe-then-substitute for text-only models, image auto-scaling, unified PDF text extraction, explicit drop-with-warning.
4. 🔵 **Self-hosted local web UI** (hardened auth, streaming, task management, browser tool approval) + **HTTP Chat API**.
5. 🔵 **MultiUI + MultiplexApprovalChannel**: one session fanned out over terminal + Telegram + web, first-response-wins.
6. 🔵 **Task Automation Framework**: `CmdTask`, `LLMTask`, `Scaffolder`, `Scheduler`, `HttpCheck`, `TcpCheck` — a DAG engine with cycle detection; any task is callable as an LLM tool ("agent-in-pipeline").
7. 🔵 **AST analysis + RAG**: `AnalyzeFile`/`AnalyzeCode`, `create_rag_from_directory`.
8. 🔵 **Richer LSP**: working wire protocol, `rename_symbol` (dry-run), workspace symbols, preferred-server ordering, extensible registry, post-write diagnostics.
9. 🔵 **Persistent todos** with live-context injection + progress cards.
10. 🔵 **Bidirectional journal graph**: typed Insight/Activity entries, backlinks, `journal-lint.py`, caching-aware index.
11. 🔵 **"Program the agent" surface**: custom tools, lifecycle hooks (both task types), permission policies, approval channels, model routing, dynamic prompt sections, history processors.
12. 🔵 **Capability-tagged permission engine + plan + auto-accept-edits** with first-class `permissions=`/`sandbox=` args.
13. 🔵 **Provider-agnostic byte-stable prompt + `<live-context>` split** for cross-provider prefix caching.
14. 🔵 **Discoverable + white-labelable config**: every knob via `config explain`; the whole env prefix is configurable.
15. 🔵 **Rate limiting + transient retry**: req/min + tok/min, O(n) context fit, backoff + `Retry-After`, classified `STOP_FAILURE`.
16. 🔵 **Terminal-safe voice** with an offline Vosk default; **Android/Termux support** with cold-import optimization and adaptive keybindings.
17. 🔵 **Drop-in Claude Code compatibility**: reads `.claude/` skills, agents, and command hooks (stdin payload + tool-name matchers) as-is.
18. 🔵 **Named themes** (`ZRB_THEME`) covering TUI + markdown + CLI colors from one knob.
19. 🔵 **Developer-utility task library** + LLM-driven `git changelog generate`.
20. 🔵 **Self-hosted, no subscription**: bring your own API key.

### Recommended Priority

#### Phase 1 — high-impact, lower effort (4–6 weeks)

1. Surface named permission modes on the CLI: `dontAsk`/`bypassPermissions` presets + `--permission-mode` (engine, plan, auto-accept-edits, Shift+Tab already exist) (3–5d).
2. Extended CLI flags: `--max-turns`, `--system-prompt`, `--resume`, `--output-format json`, `--name`, `--worktree` (1wk).
3. JSON settings files with scope hierarchy (user/project/local) merged onto env (1wk).
4. `/usage`/`/cost` + a USD budget cap (token tracking already exists) (3–5d).
5. Remaining hook events with natural fire points: `ExitPlanMode`, `WorktreeCreate/Remove`, `TaskCreated/Completed` (3–4d).
6. Additional management commands: `/clear`, `/config`, `/export`, `/permissions`, `/diff`, `/sandbox`, `/mode` (1wk).
7. `/compress [focus]` focus instructions (1–2d).
8. `CronCreate/Delete/List` wrapping the existing `Scheduler` (2–3d).
9. `CLAUDE.local.md` + `@import` (3–4d).
10. Enable rewind by default + Esc+Esc shortcut (2–3d).
11. `NotebookEdit` tool (3–4d).

#### Phase 2 — medium-impact, medium effort (6–10 weeks)

12. Network sandboxing (proxy or bwrap `--unshare-net` + allowlist) + `excludedCommands` (2–3wk).
13. Worktree isolation — `isolation: worktree` in agent defs + `/batch` (2–3wk).
14. Natural-language auto-delegation + `/agents` UI (2–3wk).
15. Per-agent frontmatter: `maxTurns`, `effort`, `mcpServers`, `hooks` (1–2wk).
16. GitHub/GitLab CI templates + `/security-review` from the `review` skill (1wk).
17. Plugin packaging + `zrb plugin add` + `/reload-plugins` (1–2wk).
18. MCP `sse`/`ws` + OAuth + resource tools + prompts-as-commands (2–3wk).
19. `http` hook handler + `if`/`once`/`statusMessage` (1wk).
20. Skill enhancements: `paths`, `shell`, `disallowed-tools`, `` !`command` `` injection (1wk).

#### Phase 3 — lower-priority, higher effort (3–6 months)

21. Auto-mode safety classifier layered onto the policy engine (4–6wk).
22. Dynamic workflows runtime (script-orchestrated fan-out) — the DAG engine + background delegate are building blocks (6–10wk).
23. Agent Teams — persistent coordinated agents with `SendMessage` (2–3mo).
24. IDE integrations (VS Code, JetBrains) (3–4mo).
25. Vim mode (2–3wk); `/diff` viewer (1–2wk).
26. Cloud sessions / cloud scheduling (requires cloud infra).

### Net assessment

Zrb is a genuine **superset in the self-hosted / multi-provider / automation dimensions** and roughly at parity on the *local agent loop* — file/shell/web/LSP tools, plan mode, a capability-tagged permission engine, an opt-in FS+OS sandbox, provider-agnostic prompt caching, persistent todos, snapshot/rewind, voice, and skills that read Claude Code's own `.claude/` layout. Several of its distinctive designs — provider-agnostic caching, model-adaptive prompt profiles, describe-then-substitute multimodal, offline voice, deep 400-recovery — exist precisely *because* it targets any provider, a problem Claude Code's managed platform doesn't have.

Claude Code keeps a clear lead in three clusters that all lean on its managed cloud/desktop footprint: **orchestration at scale** (Agent Teams + the `Workflow` runtime + `/workflows`), **IDE/desktop depth** (editor extensions, visual diff, Dispatch, cloud sessions), and the **auto-mode safety classifier**. It is also ahead on the *breadth* of mechanical surface — CLI flags, ~60 built-in commands, JSON layered settings, network sandboxing — most of which wrap capability Zrb already has and is therefore wiring rather than invention.

The highest-leverage closeable gaps are: exposing the existing engine through CLI flags and JSON settings; a USD budget on top of the existing token tracking; `CronCreate/*` over the existing `Scheduler`; and network sandboxing on top of the existing FS+OS sandbox. The structurally hard gaps — teams, the workflow runtime, IDE integration, cloud sessions, and the safety classifier — are where Claude Code's product shape, not Zrb's engine, is the differentiator.

---

*Zrb version: 2.50.3 · Model lineup: Opus 4.8 / Sonnet 5 / Haiku 4.5 / Fable 5*
