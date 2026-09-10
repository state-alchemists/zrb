# Claude Code vs Zrb: Feature Discrepancy Analysis

> **Purpose**: Map the current Claude Code feature surface, assess where Zrb stands against each area, name the *substantive* difference even where the two overlap, and estimate the effort to close the gap.
>
> **Method**: Claude Code features are drawn from its shipped tool set, skill catalogue, CLI surface, and public documentation. Zrb features are drawn from a direct read of `src/zrb/`, `docs/adr/`, and `docs/changelog/`.
>
> **Zrb version**: 3.0.0
>
> **Legend**
> - ✅ **Fully supported** — identical or functionally equivalent
> - 🟡 **Partially supported** — exists, with a named gap
> - ❌ **Not supported** — absent
> - 🔵 **Zrb-only** — Zrb has it; Claude Code does not
>
> **Reading note**: a shared ✅ rarely means *identical*. Claude Code is a managed, single-vendor product spanning terminal, desktop, web, IDE, Slack and cloud. Zrb is a self-hosted, any-provider Python framework in which the agent is one task type inside a DAG engine. The same capability is therefore reached by different mechanisms with different edges, and each section names that difference rather than stopping at "both have it".

---

## Table of Contents

1. [Distribution & Surfaces](#1-distribution--surfaces)
2. [CLI Interface & Flags](#2-cli-interface--flags)
3. [Interactive Terminal Mode](#3-interactive-terminal-mode)
4. [Slash Commands & Custom Commands](#4-slash-commands--custom-commands)
5. [Memory & Project Context](#5-memory--project-context)
6. [Hooks](#6-hooks)
7. [MCP & Connectors](#7-mcp--connectors)
8. [Subagents & Delegation](#8-subagents--delegation)
9. [Agent Teams & the Workflow Runtime](#9-agent-teams--the-workflow-runtime)
10. [Skills](#10-skills)
11. [Plugins & Marketplace](#11-plugins--marketplace)
12. [Permission Modes & Approval](#12-permission-modes--approval)
13. [Auto Mode (Safety Classifier)](#13-auto-mode-safety-classifier)
14. [Settings & Configuration](#14-settings--configuration)
15. [Built-in Tools](#15-built-in-tools)
16. [Tool-Definition Weight & Deferred Loading](#16-tool-definition-weight--deferred-loading)
17. [IDE Integration](#17-ide-integration)
18. [Sessions, Checkpointing & Rewind](#18-sessions-checkpointing--rewind)
19. [Web UI & HTTP API](#19-web-ui--http-api)
20. [Artifacts & Published Pages](#20-artifacts--published-pages)
21. [Design & Data Visualization](#21-design--data-visualization)
22. [Code Review & Security Tooling](#22-code-review--security-tooling)
23. [GitHub / CI Integration](#23-github--ci-integration)
24. [Sandboxing](#24-sandboxing)
25. [Remote Control, Cloud & Channels](#25-remote-control-cloud--channels)
26. [Scheduling & Loops](#26-scheduling--loops)
27. [Worktree Isolation](#27-worktree-isolation)
28. [Rate Limiting, Usage & Cost](#28-rate-limiting-usage--cost)
29. [Platform Support](#29-platform-support)
30. [LSP & Code Intelligence](#30-lsp--code-intelligence)
31. [Compaction & Prompt Caching](#31-compaction--prompt-caching)
32. [Prompt Composition & Model Adaptation](#32-prompt-composition--model-adaptation)
33. [Voice Input](#33-voice-input)
34. [Multimodal & Attachments](#34-multimodal--attachments)
35. [Provider Coverage & Resilience](#35-provider-coverage--resilience)
36. [Todos & Background Work](#36-todos--background-work)
37. [Task Automation Framework](#37-task-automation-framework)
38. [Editor Features (Vim, Diff Viewer)](#38-editor-features-vim-diff-viewer)
39. [Feedback, Telemetry & Onboarding](#39-feedback-telemetry--onboarding)
40. [Summary & Roadmap](#40-summary--roadmap)

---

## 1. Distribution & Surfaces

### Claude Code

A managed product with five first-party surfaces: the terminal CLI, a desktop app (macOS/Windows), a web app (`claude.ai/code`), IDE extensions (VS Code, JetBrains), and a Slack integration (Claude Tag, `/install-slack-app`). Sessions can run locally, in a cloud environment, or be dispatched from a phone to the desktop. A subscription or API billing relationship is required; models are Anthropic's only.

### Zrb

Two surfaces: the terminal TUI (`prompt_toolkit`) and a self-hosted web UI (`zrb server start`) with an HTTP/SSE chat API. Distributed as a PyPI package (`pip install zrb`) plus install scripts; runs anywhere Python runs, including Termux. No account, no subscription, no telemetry — the user brings their own API key or points at a local Ollama.

**Status**: 🟡 **Partially supported**

**Difference that matters**: this is the root fork in the road, and most later sections are downstream of it. Claude Code's surfaces are products the vendor operates; Zrb's are code the user runs. Zrb can never match the desktop/IDE/Slack/cloud footprint without becoming a hosted service, and Claude Code can never be `pip install`-ed into a private network with a self-hosted model.

---

## 2. CLI Interface & Flags

### Claude Code

Roughly seventy flags on `claude`: `-p/--print`, `--output-format`, `--input-format`, `--model`, `--fallback-model`, `--resume`, `--continue`, `--max-turns`, `--append-system-prompt`, `--permission-mode`, `--allowedTools`/`--disallowedTools`, `--add-dir`, `--mcp-config`, `--settings`, `--worktree`/`-w`, `--tmux`, `--sandbox`, `--remote-control`, `--channels`, `--agents`, `--session-id`, `--verbose`, `--debug`, plus subcommands (`claude mcp`, `claude config`, `claude plugin`, `claude remote-control`, `claude update`, `claude doctor`).

### Zrb

`zrb llm chat` exposes seven inputs, each of which becomes a `--flag` automatically because Zrb derives CLI flags from a task's `Input` list: `--message`, `--model`, `--session`, `--yolo`, `--attach`, `--interactive`, `--sandbox`. `zrb llm please` is a one-shot variant. The wider CLI is the whole task tree (`zrb <group> <task>`) — `zrb config explain`, `zrb git changelog generate`, `zrb server start`, `zrb cron parse`, and ~25 built-in utility groups. Unrecognized flags now error rather than being silently discarded, and an unresolved subcommand suggests the closest name.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's flag surface is *generated*, so it is narrow by construction — the engine has `max_request_per_run`, permission rulesets, prompt overrides and history processors, but they are reachable only from `zrb_init.py` or the environment, not from a flag. Claude Code's flags are hand-written and cover its whole engine. Closing this is wiring, not invention: each missing flag is an `Input` plus a passthrough.

**Effort to close**: **Low** (1 week) for `--max-turns`, `--system-prompt`/`--append-system-prompt`, `--resume`, `--continue`, `--output-format json`, `--permission-mode`, `--allowed-tools`/`--disallowed-tools`, `--add-dir`.

---

## 3. Interactive Terminal Mode

### Claude Code

Full-screen terminal REPL: streaming output, Shift+Tab permission-mode cycling, Ctrl+T task list, Esc-Esc rewind, `@`-mention file completion, image paste, a thinking-block display, a context/usage indicator, vim mode, and a configurable keybinding file (`~/.claude/keybindings.json`) with chord support.

### Zrb

A `prompt_toolkit` application with streaming output, collapsible thinking and text blocks, markdown rendering, an agent picker, arrow-key choice selection, message editing, a sub-agent activity panel, a token/context indicator (input/output/cache-read/context size), and a `dark`/`light` theme knob (`ZRB_THEME`) that colors the TUI, markdown and CLI from one setting. Keybindings include `s-tab`, `c-c`, `c-d`, `c-j`, `c-k`, `c-o`, `c-v`, `c-y`, `c-space`, `tab`, arrows and `escape`; output-pane bindings handle scrollback. Redirection (`>`), inline shell (`!`), and completion for files, models, skills and commands.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the core loop is at parity and Zrb's thinking/text collapse and sub-agent panel are arguably richer. The gaps are a user-editable keybinding file, vim mode, and a Ctrl+T-style task overview.

**Effort to close**: **Medium** (2–3 weeks) — a keybindings JSON layer over `prompt_toolkit` (1 wk), vim mode via `prompt_toolkit`'s existing vi bindings (1–2 wk).

---

## 4. Slash Commands & Custom Commands

### Claude Code

~60 built-in commands (`/help`, `/clear`, `/compact`, `/config`, `/cost`, `/usage`, `/model`, `/agents`, `/permissions`, `/diff`, `/export`, `/resume`, `/rewind`, `/mcp`, `/hooks`, `/doctor`, `/status`, `/artifacts`, `/tasks`, `/workflows`, `/skill-doctor`, `/loop`, `/schedule`, …) plus user- and project-defined commands as markdown files under `.claude/commands/` with frontmatter (`allowed-tools`, `argument-hint`, `model`, `disable-model-invocation`), `$ARGUMENTS`/`$1` substitution, `@file` references and `` !`cmd` `` shell injection. Plugins contribute namespaced commands.

### Zrb

Sixteen command families, each an alias list configurable via `CFG.LLM_UI_COMMAND_*`, so the whole command vocabulary is rebindable (and white-labelable):

| Family | Default aliases |
| --- | --- |
| summarize | `/compress`, `/compact` |
| attach | `/attach` |
| exit | `/q`, `:q`, `/bye`, `/quit`, `/exit` |
| info | `/info`, `/help` |
| save / load | `/save` — `/load`, `/resume` |
| rewind | `/rewind` |
| yolo | `/yolo` |
| redirect | `>`, `/redirect` |
| exec | `!`, `/exec` |
| model | `/model` |
| btw | `/btw` |
| plan | `/plan` |
| copy | `/copy` |
| voice | `/voice`, `/v` |
| photo | `/photo`, `/p` |

Custom commands are built from skills and markdown files, resolved through `llm/custom_command/`, and wrapped in `PRE_COMMAND`/`POST_COMMAND` hooks. Per ADR-0093 a slash command is always *offered* — an unavailable one explains why rather than silently sending its text to the model.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's set is smaller but every alias is a config knob, which Claude Code's is not. Missing management commands are the ones whose underlying capability already exists and is simply not fronted: `/clear`, `/config`, `/permissions`, `/export`, `/status`, `/mcp`, `/hooks`, `/agents`, `/diff`, `/cost`.

**Effort to close**: **Low** (1 week) — each is a handler over machinery that already exists.

---

## 5. Memory & Project Context

### Claude Code

Two layers. **Project instructions**: `CLAUDE.md` at user (`~/.claude/`), project, and directory scope, with `@import` of other files and a `CLAUDE.local.md` for uncommitted personal notes. **Persistent memory**: a file-based per-project memory directory, one fact per file with typed frontmatter (`user` / `feedback` / `project` / `reference`), `[[wikilink]]` cross-references, and a `MEMORY.md` index loaded into every session; relevant memories are surfaced mid-conversation as system reminders.

### Zrb

**Project instructions**: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `README.md` are discovered by an upward directory walk, split into project-scope (a mandated read) and user-scope (`~`-level docs presented as cross-project preferences, explicitly *not* project rules), and injected as a `Project Context` section. No `@import`, no `.local.md` variant.

**Persistent memory**: 🔵 a structured **journal** (`llm/tool/journal.py`, `journal_write.py`) — typed Insight and Activity entries in a git-backed directory, bidirectional backlinks, an index file with a character cap, `SearchJournal` / `WriteJournalNote` / `LogActivity` / `DeleteJournalNote` tools, an auto-search that surfaces relevant entries per turn (`LLM_JOURNAL_AUTO_SEARCH_ENABLED`), a HUD that renders recent entries into live context, and a compliance hook that checks a turn produced an entry when it should have. The whole subsystem is gated by `LLM_JOURNAL_ENABLED`, enforced by the four tools simply not being registered — there is no prompt section describing the protocol.

**Status**: ✅ **Fully supported** (different shape; Zrb advantage on structure, gap on `@import`/`.local`)

**Difference that matters**: Claude Code's memory is a flat bag of one-fact files whose recall is a relevance match against descriptions. Zrb's journal is a *linked graph* with typed entries, backlinks, git history and an auto-search hook — closer to a lab notebook than a preference store, and it gets version-controlled with the project. Claude Code's advantage is that memory writing is a first-class always-on behavior with an explicit taxonomy; Zrb's is off by default and heavier to adopt.

**Effort to close**: **Low** (3–4 days) for `CLAUDE.local.md` and `@import` expansion in the project-context section.

---

## 6. Hooks

### Claude Code

~14 lifecycle events — `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Notification`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, `PreCompact`, `PostCompact`, `PermissionRequest`, plus worktree and task events — configured in `settings.json` with `command` and `http` handler types, tool-name/glob/regex matchers, `if`/`once` conditions, `statusMessage`, and a JSON stdin payload the hook can answer with a decision object (`allow`/`deny`/`ask`, `additionalContext`).

### Zrb

Sixteen events, defined in `llm/hook/types.py`:

`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `PreCommand`, `PostCommand`, `PreCompact`, `PostCompact`, `SessionStart`, `SessionEnd`, `Stop`, `StopFailure`, `SubagentStart`, `SubagentStop`, `Notification`, `PermissionRequest`.

Matchers cover `equals`, `contains`, `glob`, `regex`, plus `agent`, `command` and `prompt` matcher kinds. Handler types are `command` (Claude-compatible: same JSON stdin payload, same tool-name matchers, so `.claude/` command hooks are drop-in) and `agent` — 🔵 a hook that *is an LLM agent*, wired through a registration seam (`hook/agent_hook_registry.py`) so the hook manager does not import the agent stack it is imported by. Programmatic hooks attach directly to `BaseTask` and `LLMTask`.

**Status**: 🟡 **Partially supported** — arguably a superset on control, a gap on transport

**Difference that matters**: Zrb has three events Claude Code does not (`PostToolUseFailure`, `StopFailure`, `SubagentStart`) and a handler type Claude Code does not (an agent as a hook, used for the journal-compliance check). What is missing is the `http` handler, the `if`/`once`/`statusMessage` modifiers, and worktree/task lifecycle events.

**Effort to close**: **Low–Medium** (1 week) — `http` handler (2 d), modifiers (2 d), the remaining events (2–3 d).

---

## 7. MCP & Connectors

### Claude Code

Full MCP client: `stdio`, `sse`, `streamable-http` and WebSocket transports; OAuth for remote servers; server-provided **resources** (`@server:resource`) and **prompts** (surfaced as slash commands); `claude mcp add/list/remove`, `--mcp-config`, project/user/local scopes, `/mcp` management UI. First-party OAuth connectors ship for Asana, Atlassian, Box, Canva, Figma, HubSpot, Intercom, Linear, Notion and monday.com, and are host-designated as first-party (which grants them privileges a self-described server never gets).

### Zrb

`llm/tool/mcp.py` reads `.mcp.json`-style config from several locations, merges it, expands `${ENV_VAR}` references, and creates one toolset per server. Transports: **stdio** (`command`/`args`/`env`) and **HTTP** (`url`). Every toolset is `defer_loading()`-ed so a large third-party server does not inflate the prompt, and results are capped against a per-request token budget (`cap_mcp_result` / `frame_mcp_result`) with configurable retries.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb covers the two transports that matter for local and self-hosted servers and adds result capping Claude Code does not advertise — a third-party server cannot blow the context window. Missing: OAuth, SSE/WebSocket, resources, prompts-as-commands, a management CLI/UI, and any notion of a trusted first-party connector.

**Effort to close**: **Medium** (2–3 weeks) — SSE/WS (3 d), OAuth (1 wk), resources + prompts (1 wk), `zrb mcp add/list/remove` (2 d).

---

## 8. Subagents & Delegation

### Claude Code

The `Agent` tool with named agent types defined in `.claude/agents/*.md` frontmatter (`description`, `tools`, `model`, `isolation: worktree|remote`). A `fork` type inherits the parent's full context. Agents run in the background with completion notifications; `ListAgents` enumerates reachable agents and `SendMessage` continues one with its context intact. Natural-language auto-delegation routes work to a matching agent without an explicit call, and `/agents` provides a management UI.

### Zrb

`SubAgentManager` loads `*.agent.md` definitions from user, project and plugin roots. Frontmatter: `name`, `description`, `model`, `tools`, `agents` — and the definition object also carries `disallowed_tools`, `inherit_sections`, `agent_instance` and `agent_factory` for programmatic agents.

- **`DelegateToAgent`** — synchronous delegation, and fans out via its `tasks` argument for parallel sub-agents (capped by `LLM_MAX_PARALLEL_DELEGATIONS`). Loaded eagerly rather than deferred, because its schema carries the sub-agent roster and a model that must search before it can see which agents exist mostly does not delegate at all.
- **`DelegateToAgentBackground`** + **`GetDelegationResult`** — background delegation with a live-context provider that reports running delegations every turn.
- **`SearchAgent`** — the on-demand window onto the roster beyond `LLM_MAX_AGENTS_IN_ROSTER` (10).
- Sub-agents inherit the caller's permission policy, sandbox and approval channel through ContextVars; delegate tools are filtered out of sub-agents so they cannot recurse; read-only agents are name-gated at tool resolution; sub-agent history is persisted and pruned; a sub-agent activity panel renders in the TUI.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the delegation *mechanics* are at parity or better — Zrb's policy/sandbox inheritance, `disallowed_tools` subtraction and roster capping have no direct Claude Code analogue. What is missing is **auto-delegation** (the model is told about agents but the harness never routes to one on its own), **`isolation:` per agent**, an inter-agent `SendMessage` channel, and an `/agents` UI.

**Effort to close**: **Medium** (2–3 weeks) — auto-delegation + `/agents` (2 wk), `isolation: worktree` on definitions (1 wk, after §27).

---

## 9. Agent Teams & the Workflow Runtime

### Claude Code

Two orchestration layers above single delegation. **Agent teams**: multiple named agents (local sessions, teammates, or cloud sessions) addressable by name through `SendMessage`, each holding its own context, coordinating on a shared task. **The `Workflow` tool**: a JavaScript orchestration script — `agent()`, `parallel()`, `pipeline()`, `phase()`, typed schemas, `resumeFromRunId` caching — that deterministically fans dozens of agents out and pipelines their results, running in the background with `/workflows` for live progress and a per-session size guideline. Both are explicitly opt-in because of their token cost.

### Zrb

No teams, no workflow runtime, no inter-agent messaging. The building blocks exist and are strong — a DAG engine with cycle detection, `DelegateToAgent(tasks=[...])` for fan-out, `DelegateToAgentBackground` for detached runs, and `LLMTask` so any agent is a node in a pipeline — but there is no script-driven orchestrator and no way for two running agents to address each other.

**Status**: ❌ **Not supported**

**Difference that matters**: this is the largest genuine capability gap. Zrb can *fan out* (parallel delegation) and *chain* (the DAG), but a Zrb pipeline is authored in Python ahead of time by a developer, whereas a Claude Code workflow is authored by the model at request time and resumes from cached agent results. The Zrb DAG is closer to Airflow; the Workflow tool is closer to a map-reduce the agent writes for itself.

**Effort to close**: **High** (6–10 weeks) for a workflow runtime over the existing DAG + background delegate; **Very High** (2–3 months) for teams, which need a session-addressing protocol Zrb has no substrate for.

---

## 10. Skills

### Claude Code

`SKILL.md` files with frontmatter (`name`, `description`, `allowed-tools`, `model`, `user-invocable`, `disable-model-invocation`, `argument-hint`, `paths`, `context`) discovered from `~/.claude/skills/`, `.claude/skills/`, and plugins. A skill loads its instructions into the turn, or runs in a subagent and returns a result. `/skill-doctor` and `claude plugin eval` audit skill quality. First-party skills ship for artifacts, design, dataviz, code review, security review, config, scheduling, and API reference.

### Zrb

`SKILL.md` **or `SKILL.py`** files, discovered from the same `.claude/`-compatible layout plus Zrb's own roots and plugin directories. Recognized frontmatter includes `name`, `description`, `allowed-tools`, `argument-hint`, `model`, `user-invocable`, `disable-model-invocation`, `context`, `agent`, `agents`, `skills`, `hooks`, `plugins`, `fork`. `ActivateSkill` loads one on demand; `SearchSkill` is the window onto the catalogue beyond `LLM_MAX_SKILLS_IN_CATALOG` (10). Skills also become custom slash commands.

Built-in content is split four ways (ADR-0054): `core_skills/` (always-on methodology baseline — `core-coding`, `core-design`, `core-diagram`, `core-research`, `core-writing`), `skills/` (utility, gated by `LLM_ENABLE_BUILTIN_SKILLS` — `debug`, `git-summary`, `init`, `refactor`, `research`, `review`, `skill-creator`, `testing`), `core_agents/` (`generalist`), and `agents/` (gated by `LLM_ENABLE_BUILTIN_AGENTS` — `code-reviewer`, `researcher`). The toggles suppress only *optional built-in* content; user, project and plugin skills always load.

**Status**: ✅ **Fully supported** (Zrb advantage on governance and `SKILL.py`)

**Difference that matters**: Zrb reads Claude Code's skill layout as-is, adds executable Python skills, and adds a governance split Claude Code does not have — a user can disable the vendor's opinionated utility skills without losing their own. What Claude Code has that Zrb does not is `paths` scoping, `` !`cmd` `` injection, and the skill-quality tooling (`/skill-doctor`, `plugin eval`).

**Effort to close**: **Low** (1 week) for the frontmatter gaps.

---

## 11. Plugins & Marketplace

### Claude Code

A packaged plugin format bundling skills, agents, commands, hooks and MCP servers; installable from a marketplace; `claude plugin` CLI with install/list/eval; namespaced invocation (`plugin:skill`); `/reload-plugins`.

### Zrb

Plugin *consumption* only: `scan_plugin_dirs` walks `plugins/` directories and picks up their `skills/` (and agent) content, so a Claude Code plugin's skills and agents load. There is no packaging format, no install command, no marketplace, no namespacing, and no reload.

**Status**: 🟡 **Partially supported**

**Effort to close**: **Medium** (1–2 weeks) — a manifest + `zrb plugin add/list/remove` + reload. A marketplace is a hosting problem, not a code problem.

---

## 12. Permission Modes & Approval

### Claude Code

Named modes cycled with Shift+Tab: `default` (ask), `acceptEdits`, `plan`, `bypassPermissions`. `settings.json` carries `permissions.allow`/`deny`/`ask` rules with tool-and-argument matchers (`Bash(git diff:*)`), `additionalDirectories`, and a `/permissions` UI. Hooks can intercept at `PermissionRequest`. `/fewer-permission-prompts` mines transcripts to propose an allowlist.

### Zrb

A **capability-tagged permission engine**. Every tool is tagged with a `Capability` — `read`, `edit`, `execute`, `network`, `delegate`, `meta`, or `unknown` — and `CFG.LLM_PERMISSIONS` accepts either a shorthand (`allow` / `ask` / `deny`) or a comma-separated `key:action` list where the key is a tool name, a capability, or `*`. Untagged tools resolve to `unknown` and are denied in plan mode, which is deliberately safe-by-default for third-party and MCP tools; a test (`test_every_registered_tool_carries_a_known_capability`) fails if a *built-in* tool is left untagged.

On top of that: two agent modes (`BUILD` / `PLAN`) with `EnterPlanMode`/`ExitPlanMode` tools registered only in interactive sessions; a `yolo` setting that is `true`, `false`, or a *selective* frozenset of tool names (`--yolo Write,Edit`); Shift+Tab mode cycling; tool policies that inspect arguments (`bash_safe_command_policy` auto-approves read-only git subcommands and routes `commit`/`push`/`reset` to the user — which is why that rule never has to appear in the prompt); argument formatters and response handlers; and an approval channel abstraction (`TerminalApprovalChannel`, `NullApprovalChannel`, `MultiplexApprovalChannel`) that sub-agents inherit through a ContextVar. `permissions=` and `sandbox=` are first-class constructor arguments on the task.

**Status**: 🟡 **Partially supported** — a stronger engine, a thinner presentation

**Difference that matters**: Zrb's model is *capability-first*, Claude Code's is *pattern-first*. Zrb can say "deny everything that touches the network" in four characters; Claude Code needs to enumerate tools. Conversely Claude Code can say `Bash(git diff:*)` declaratively, where Zrb needs a tool policy in Python. The gaps are named presets (`acceptEdits`, `bypassPermissions` as words), a `--permission-mode` flag, a `/permissions` UI, and argument-level rules in config rather than code.

**Effort to close**: **Low** (3–5 days) for presets + the flag; **Low–Medium** (1 week) for argument-pattern rules in `LLM_PERMISSIONS`.

---

## 13. Auto Mode (Safety Classifier)

### Claude Code

An operating mode in which a safety classifier evaluates each proposed action, letting low-risk work proceed unprompted while routing genuinely risky actions to the user. It also steers *how* work is done — in auto mode the harness pushes file reads, searches and edits through Bash rather than the dedicated tools.

### Zrb

No classifier. The enforcement substrate exists — the capability engine, tool policies with argument inspection, and the FS/OS sandbox — but the decision is always rule-based, never model-judged.

**Status**: ❌ **Not supported**

**Difference that matters**: rules are predictable and auditable; a classifier is adaptive and catches cases no rule anticipated. Zrb's `bash_safe_command_policy` is the closest thing: a hand-written allowlist doing statically what the classifier does dynamically.

**Effort to close**: **High** (4–6 weeks) — a small-model classifier layered onto `PermissionPolicy`, plus the evaluation set to trust it.

---

## 14. Settings & Configuration

### Claude Code

Layered JSON: enterprise → user (`~/.claude/settings.json`) → project (`.claude/settings.json`) → local (`.claude/settings.local.json`), merged by scope, covering permissions, hooks, env, model, MCP servers, statusline, editor mode, and feature toggles. `/config` for interactive editing, `claude config` on the CLI, and an `update-config` skill for structured edits.

### Zrb

A single `CFG` singleton composed from 20 mixins, exposing **242 `EnvField` knobs** with a flat access surface (`CFG.FOO` regardless of owning mixin). Each field declares a type, a default (or `default_factory`), a doc string, nullability, and optional env aliases. 🔵 `zrb config explain` prints every knob with its doc, current value and source. The whole env prefix is configurable, so the tool can be white-labeled. Configuration channels are three (ADR-0091): environment variables, `zrb_init.py` (Python — where tools, hooks, prompts, policies and UIs are wired), and constructor arguments. `ZRB_INIT_STRICT` makes a failed init source fatal for CI; a broken init file is reported by file, line and exception type. `CFG` assignments fail fast on unknown names.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's config is *discoverable* in a way Claude Code's is not — `config explain` is a genuine advantage, and `zrb_init.py` can express things no JSON file can (a custom tool, a model-routing function, a prompt section). What is missing is scoped JSON files: there is no per-project settings file merged over a user file, so team-shared configuration means committing a `zrb_init.py` and per-user overrides mean environment variables.

**Effort to close**: **Low–Medium** (1 week) — a JSON layer resolved user → project → local and merged *under* the env vars, so precedence stays explicit-over-ambient.

---

## 15. Built-in Tools

### Claude Code

Roughly forty-five tools. File and search: `Read` (images, PDFs with page ranges, notebooks), `Write`, `Edit`, `Glob`, `Grep`, `NotebookEdit`. Execution: `Bash` (with `run_in_background`), `Monitor`, `TaskOutput`, `TaskStop`. Web: `WebFetch`, `WebSearch`. Orchestration: `Agent`, `ListAgents`, `SendMessage`, `Workflow`, `Skill`, `ToolSearch`. Control: `EnterPlanMode`, `ExitPlanMode`, `EnterWorktree`, `ExitWorktree`, `AskUserQuestion`, `EndConversation`, `TodoWrite` (deprecated). Scheduling: `CronCreate`, `CronDelete`, `CronList`, `ScheduleWakeup`. Product surface: `Artifact`, `DesignSync`, `ReportFindings`, `SendFeedback`, `ShareOnboardingGuide`, `PushNotification`, `RemoteTrigger`, `LSP`. Plus MCP connectors.

### Zrb

Forty-one tool names across ~33 modules, registered and capability-tagged in `llm/common_tools.py`:

| Group | Tools |
| --- | --- |
| File | `Read`, `Write`, `Edit`, `LS`, `Glob`, `Grep`, `RM`, `MV` |
| Analysis | `AnalyzeFile`, `AnalyzeCode` |
| Execution | `Shell`, `MonitorProcess`, `RunZrbTask`, `ListZrbTask` |
| Web | `WebSearch`, `WebFetch` |
| LSP (8) | `LspFindDefinition`, `LspFindReferences`, `LspGetDiagnostics`, `LspGetDocumentSymbols`, `LspGetHoverInfo`, `LspGetWorkspaceSymbols`, `LspListServers`, `LspRenameSymbol` |
| Plan / control | `TodoWrite`, `TodoRead`, `EnterPlanMode`, `ExitPlanMode`, `AskUserQuestion`, `ReadToolResult` |
| Worktree | `EnterWorktree`, `ExitWorktree`, `ListWorktrees` |
| Journal | `SearchJournal`, `WriteJournalNote`, `LogActivity`, `DeleteJournalNote` |
| Skills / agents | `ActivateSkill`, `SearchSkill`, `SearchAgent`, `DelegateToAgent`, `DelegateToAgentBackground`, `GetDelegationResult` |

Registration is **conditional and per-run**: LSP tools appear only when a language server is installed (a `shutil.which` scan), worktree tools only inside a git repo, plan-mode and `AskUserQuestion` only in interactive sessions, journal tools only when `LLM_JOURNAL_ENABLED`, and `ReadToolResult` only when spill is on. Every one of those gates is a factory re-evaluated at each agent build, so toggling a knob mid-session takes effect on the next run.

🔵 Beyond the roster: **tool-result spill** (ADR-0089) — a result over `LLM_MAX_TOOL_RESULT_CHARS` is written to a `0700` local store with symlink/`..`/absolute-path escape rejection, and the model gets a preview plus a `ReadToolResult` handle rather than a truncation. MCP results are capped against a token budget. Also a RAG builder (`create_rag_from_directory`) and PDF text extraction shared by `Read`, the attachment pipeline and `WebFetch`.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the *coding-agent* tool surface is at parity, and Zrb's LSP block, spill store, `RunZrbTask` and journal tools have no Claude Code equivalent. The absences are all product-surface tools — `Artifact`, `DesignSync`, `ReportFindings`, `SendFeedback`, `ShareOnboardingGuide`, `PushNotification`, `RemoteTrigger`, `Workflow`, `SendMessage`, `ListAgents` — plus `NotebookEdit` and page-ranged PDF reads.

**Effort to close**: **Low** (3–4 days) for `NotebookEdit` and PDF page ranges. The product-surface tools are covered in their own sections.

---

## 16. Tool-Definition Weight & Deferred Loading

### Claude Code

Deferred tools are listed by name in system reminders with no schema; `ToolSearch` fetches full definitions on demand by keyword or `select:Name` before a tool can be called. This keeps a large tool roster off every request.

### Zrb

The same technique, from the other direction. Since pydantic-ai serializes every registered tool's docstring and parameter schema into every request, Zrb treats the *number of registered tools* as the only lever — hence the conditional registration above — and marks the rest `defer_loading=True` so their schemas materialize only when the provider's native tool search surfaces them: `AnalyzeCode`, `AnalyzeFile`, the worktree trio, all eight LSP tools, all four journal tools, `MonitorProcess`, `ListZrbTask`/`RunZrbTask`, plan-mode tools, and every MCP toolset. `DelegateToAgent` is the deliberate exception — its schema carries the sub-agent roster, and a model that has to search before it can see the roster mostly does not delegate at all. There is no prompt-side tool catalogue at all; what a tool does lives in its docstring, next to the schema.

**Status**: ✅ **Fully supported**

**Difference that matters**: functionally the same mechanism with the same rationale. Zrb additionally reasons about it as a *design constraint* — conditional registration is a token-budget decision documented in `common_tools.py`, and the journal-compliance hook strips `defer_loading` back off for the tools it names explicitly, since a hook that already knows the tool would only pay an extra round trip.

---

## 17. IDE Integration

### Claude Code

VS Code and JetBrains extensions: inline diff review with per-hunk accept/reject, selection context, drag-and-drop attachments, and a panel session tied to the editor's workspace.

### Zrb

None. The web UI is a separate application, not an editor plugin.

**Status**: ❌ **Not supported**

**Effort to close**: **Very High** (3–4 months per IDE) — and it competes directly with a vendor-maintained extension.

---

## 18. Sessions, Checkpointing & Rewind

### Claude Code

`--resume`/`--continue`, `/resume` with a session picker, named sessions (`--session-id`), automatic checkpointing with Esc-Esc rewind and `/rewind`, and a checkpoint-based diff. Cloud sessions persist server-side.

### Zrb

`FileHistoryManager` persists conversations per named session with crash-safe writes; `/save`, `/load`, `/resume` and `--session` address them. `SnapshotManager` is a git-backed filesystem checkpointer — `take_snapshot`, `take_init_snapshot`, `list_snapshots`, `restore_snapshot`, commit messages carrying the message count so a snapshot maps back to a conversation turn, and a copy walk that skips ignored paths. `/rewind` restores one. Partial-run retry (`agent/run/partial_run.py`) resumes an interrupted run rather than restarting it. `/copy` exports the conversation. Session state is logged through `session_state_log*/`.

The one wrinkle: `LLM_ENABLE_REWIND` defaults to `off`.

**Status**: ✅ **Fully supported** (with rewind opt-in rather than default)

**Difference that matters**: mechanically equivalent, and Zrb's partial-run retry has no Claude Code analogue. The gaps are a session *picker* UI (Zrb takes a name), an Esc-Esc shortcut, and rewind being on by default.

**Effort to close**: **Low** (2–3 days).

---

## 19. Web UI & HTTP API

### Claude Code

`claude.ai/code` — a hosted web app. Nothing self-hosted.

### Zrb

🔵 A shipped, self-hosted web application (`zrb server start`): a home/node page for the task tree, a chat page with SSE streaming, task input and session APIs, JWT login/logout/refresh with configurable token expiry, browser-side tool approval, and a docs route. It binds to loopback by default and warns explicitly when bound to a non-loopback address (ADR-0087). The chat layer (`runner/chat/`) exposes `ChatSessionManager`, an SSE stream, and an HTTP API — an authorized external `POST /api/v1/chat/sessions/{id}/messages` pushes a message into a live session.

**Status**: 🔵 **Zrb advantage**

**Difference that matters**: Claude Code's web surface is the vendor's; Zrb's runs on the user's machine or their private network, which is the only option when the code cannot leave the building. The tradeoff is that Zrb's is a local server with no multi-device sync, sharing, or persistence beyond the host.

---

## 20. Artifacts & Published Pages

### Claude Code

The `Artifact` tool publishes an HTML page to a private URL on claude.ai and redeploys to the same URL on update. Published pages can carry runtime capabilities: a small shared document database (get/list/query/set/update/str_replace/delete/batch with optimistic `if_version` concurrency and per-viewer private subtrees), an asset store for images/PDFs/fonts/text, viewer identity, the ability to ask Claude a question from the page, and the ability for the page to save new versions of itself. Around that: comment threads viewers can send to Claude, reply and resolve actions, live-update watches that wake the session on a republish, listing and reading of the user's own and shared artifacts, and pinning to the sidebar.

### Zrb

Nothing equivalent. The closest surface is the self-hosted web UI (§19), which serves the *agent*, not agent-produced pages. An agent can write an HTML file; there is no hosting, no versioned URL, no page-side database, no comments.

**Status**: ❌ **Not supported**

**Difference that matters**: this is the second-largest gap after orchestration, and it is a hosting gap rather than an engine gap. Artifacts turn a terminal answer into a shareable, stateful, commentable page — an output *channel*, not a capability of the model. Zrb could serve pages from its own web server (it already runs one), but the sharing, identity and durability story requires infrastructure a self-hosted tool does not have by default.

**Effort to close**: **High** (6–8 weeks) for a local equivalent — serving versioned pages from the existing web server with a SQLite-backed page database and an asset store. Sharing beyond the host machine is out of scope without hosting.

---

## 21. Design & Data Visualization

### Claude Code

A `design` skill producing multi-artboard design canvases as published artifacts with a visual editor (click-to-select, properties panel, inline editing, undo/redo, PNG/PDF export), a `DesignSync` tool, a `dataviz` skill carrying a validated palette and chart-form heuristics, and `artifact-design` / `artifact-diagramming` skills governing page design and inline-SVG diagrams. Mermaid renders natively in artifacts.

### Zrb

A `core-design` and a `core-diagram` core skill supply methodology — how to reason about a design or a diagram — with no rendering surface, no canvas, and no chart tooling.

**Status**: 🟡 **Partially supported** (methodology only)

**Difference that matters**: Zrb ships the *thinking*, Claude Code ships the thinking plus the canvas. Without §20 there is nowhere for a canvas to live, so this gap is downstream of Artifacts.

---

## 22. Code Review & Security Tooling

### Claude Code

A `code-review` skill with effort levels, PR/branch/path targeting, `--comment` to post inline PR comments and `--fix` to apply findings; a `ReportFindings` tool that renders typed findings in the host UI with severity, category, verdict and per-finding outcome; a `security-review` skill; a `simplify` skill for quality-only cleanups.

### Zrb

A `review` skill (built-in, gated by `LLM_ENABLE_BUILTIN_SKILLS`) and a `code-reviewer` sub-agent (gated by `LLM_ENABLE_BUILTIN_AGENTS`). Findings come back as prose. 🔵 The repo also runs an LLM code-review step in its own CI. No structured finding type, no PR comment posting, no apply-fixes mode, no dedicated security review.

**Status**: 🟡 **Partially supported**

**Effort to close**: **Low–Medium** (1 week) — a structured findings schema plus `gh`/`glab` comment posting, over the review skill that already exists.

---

## 23. GitHub / CI Integration

### Claude Code

A GitHub App with `@claude` PR/issue triggers, `/install-github-app`, official GitHub Actions, PR creation and review flows, and a Slack integration for the same.

### Zrb

Detects `gh` and `glab` and can drive them through `Shell`. 🔵 `zrb git changelog generate` is an LLM-driven changelog task, and `zrb git subtree` wraps subtree operations. No app, no triggers, no shipped Action templates.

**Status**: ❌ **Not supported**

**Effort to close**: **Low–Medium** (1 week) for GitHub/GitLab CI templates that run `zrb llm please` on a PR — which is most of the practical value. The hosted app is a product, not a feature.

---

## 24. Sandboxing

### Claude Code

`--sandbox` and a `/sandbox` command; OS-level isolation with filesystem and **network** restrictions, an `excludedCommands` escape list, and a bash-first execution posture in auto mode.

### Zrb

An opt-in sandbox (`llm/sandbox/`) with two layers: a **filesystem policy** (`fs_policy.py`) enforced inside the file tools, and an **OS sandbox** (`os_sandbox.py`) using `bwrap` on Linux and `seatbelt` on macOS for shell commands. Knobs: `LLM_SANDBOX_ENABLED`, `LLM_SANDBOX_WRITABLE_PATHS`, `LLM_SANDBOX_DENY_READ_PATHS` (credential files denied by default), `LLM_SANDBOX_ALLOW_ESCAPE`, `LLM_SANDBOX_FALLBACK`, `LLM_SANDBOX_OS_SHELL`. Exposed as `--sandbox` on the chat task and as a `sandbox=` constructor argument, and inherited by sub-agents.

**Status**: 🟡 **Partially supported**

**Difference that matters**: filesystem and process isolation are at parity, including a deny-read list for credentials that Claude Code does not advertise. The missing piece is **network filtering** — a sandboxed Zrb shell can still reach the internet.

**Effort to close**: **Medium** (2–3 weeks) — `bwrap --unshare-net` plus an allowlisting proxy on Linux; the macOS seatbelt profile can express network rules directly.

---

## 25. Remote Control, Cloud & Channels

### Claude Code

**Remote Control**: drive a local session from claude.ai (`--remote-control`, `claude remote-control`), with `RemoteTrigger` and `PushNotification` tools reaching the user's other devices. **Cloud sessions**: agents running in a hosted environment, addressable from the local session, surviving the machine being off. **Channels**: MCP channel plugins push external events into a session (Telegram, Discord, iMessage, webhooks) via `--channels`, `channelsEnabled`, `allowedChannelPlugins`. **Dispatch**: phone → desktop.

### Zrb

🔵 `MultiUI` fans one session out over several UI backends simultaneously (terminal + web, and any user-written backend), broadcasting output and merging input first-response-wins; `MultiplexApprovalChannel` routes an approval request to several channels and denies only after every channel has finished without a result, so a slow human at the terminal is not pre-empted by a fast erroring channel. The HTTP chat API pushes external messages into a live session. Two extension ladders are documented (`SimpleUI` / `EventDrivenUI` / `BaseUI`) for writing new backends — the Telegram bot that used to ship is now only a documented example, not shipped code.

No remote-control protocol, no cloud tier, no channel plugin contract, no push notifications.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb has the *multiplexing substrate* Channels needs and lacks the *contract* — adding a channel means writing a `BaseUI` subclass in Python, not dropping in a plugin. Cloud and Remote Control need infrastructure Zrb has no equivalent of.

**Effort to close**: **Medium** (2–3 weeks) for a WebSocket remote-control endpoint on the existing web server plus a declarative channel-plugin contract over `MultiUI`. Cloud is **Very High**.

---

## 26. Scheduling & Loops

### Claude Code

`CronCreate`/`CronDelete`/`CronList` as model-callable tools for in-session recurring or one-shot prompts; `ScheduleWakeup` for self-paced loops with a `stop` action and noop-streak tracking; a `/loop [interval] <prompt>` skill; a `/schedule` skill for cloud routines that run on a cron schedule whether or not the machine is on.

### Zrb

🔵 A `Scheduler` task type with validated cron parsing — wildcard steps inside lists, out-of-range rejection, `7` as Sunday, correct weekday/day-of-month semantics — deduped fired-minute ticks and drift-clamped sleeps, plus a `zrb cron parse` utility. Scheduling is a *task-engine primitive* wired up in Python.

No `CronCreate`-style tools the model can call, no `/loop`, no self-pacing wakeup, no cloud tier.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's cron implementation is more rigorous; Claude Code's is more *reachable* — the agent creates a schedule mid-conversation. Wrapping `Scheduler` as three tools closes most of it.

**Effort to close**: **Low** (2–3 days) for in-session cron tools; **Low–Medium** (1 week) for a `/loop` equivalent; **Very High** for cloud.

---

## 27. Worktree Isolation

### Claude Code

`--worktree`/`-w` and `--tmux` flags; `isolation: worktree` (and `isolation: remote`) in agent frontmatter so parallel agents cannot collide; `EnterWorktree`/`ExitWorktree` tools; `WorktreeCreate`/`WorktreeRemove` hooks; `worktree.symlinkDirectories`, `sparsePaths`, `bgIsolation`, `baseRef`; `.worktreeinclude`.

### Zrb

`EnterWorktree(branch_name)`, `ExitWorktree(worktree_path, keep_branch)` and `ListWorktrees()`, registered only inside a git repo and deferred-loaded, with structured `{"error": …}` results. `EnterWorktree` sets an `active_worktree` ContextVar injected into every system context and delegate message, so the model is reminded to pass `cwd`/absolute paths; `.zrb/worktree/` is auto-added to `.gitignore`; a stale-worktree guard clears the var when the path vanishes. Storage: `{git_root}/.zrb/worktree/{branch_name}`.

**Status**: 🟡 **Partially supported**

**Difference that matters**: the *tools* and the tracking are at parity. What is missing is worktree as a **policy** — pinning a sub-agent into its own worktree so a fan-out cannot collide — plus the CLI flag and the worktree hooks.

**Effort to close**: **Medium** (2–3 weeks) — `--worktree` (1–2 d), `isolation:` on agent definitions (~1 wk, follows §8), worktree hook events (2 d).

---

## 28. Rate Limiting, Usage & Cost

### Claude Code

`/usage` and `/cost` report token consumption and spend against a subscription or API budget; a context indicator in the TUI; automatic fallback and overage handling; prompt-cache TTL awareness surfaced to the agent.

### Zrb

🔵 A rate limiter (`llm/config/limiter.py`) enforcing requests-per-minute, tokens-per-minute and tokens-per-request with an O(n) context fit, a configurable throttle sleep, and backoff honoring `Retry-After`; `LLM_MAX_REQUEST_PER_RUN` caps a single run's tool loop; `LLM_API_MAX_RETRIES`/`LLM_API_MAX_WAIT` bound transient retries; a failure that survives them is classified and surfaced through the `StopFailure` hook. The TUI tracks session input/output tokens, cache-read tokens and current context size.

No monetary cost tracking, no per-model pricing table, no budget cap, no `/cost`.

**Status**: 🟡 **Partially supported**

**Difference that matters**: Zrb's throttling is more capable than Claude Code exposes — it protects a self-hosted or low-tier provider from being hammered, which a managed platform handles server-side. What it lacks is the money view, and that is genuinely harder for Zrb: pricing is per-provider and changes, so a table would need maintaining across a dozen vendors.

**Effort to close**: **Low–Medium** (3–5 days) for `/usage` plus a configurable per-model price map and a soft budget cap over the token counters that already exist.

---

## 29. Platform Support

### Claude Code

macOS, Linux, Windows (native and WSL), with a desktop app on macOS and Windows.

### Zrb

macOS and Linux are first-class. Windows is supported and actively hardened — the default shell is a real POSIX shell selected and compared by name (ADR-0095), path config uses a `path_list` parser instead of colon-splitting, `is_tty` handles stdin redirected from `NUL`, journal links use forward slashes, and the CI runs a Windows test matrix. 🔵 Android/Termux is supported, with cold-import optimization and adaptive keybindings for that environment.

**Status**: ✅ **Fully supported** (Termux is a Zrb-only surface)

---

## 30. LSP & Code Intelligence

### Claude Code

An `LSP` tool for language-server-backed navigation.

### Zrb

🔵 A full LSP client stack with a working wire protocol and eight tools — definitions, references, diagnostics, document symbols, hover, **workspace symbols**, server listing, and **rename with a dry-run** — over a registry of 21 server configurations (`pyright`, `pylsp`, `jedi`, `typescript-language-server`, `gopls`, `rust-analyzer`, `clangd`, `jdtls`, `metals`, `kotlin-language-server`, `solargraph`, `ruby-lsp`, `intelephense`, `omnisharp`, `csharp-ls`, `lua-language-server`, `sourcekit-lsp`, and the json/yaml/html/css servers), with preferred-server ordering, an extensible registry, and post-write diagnostics that report errors introduced by an edit. Registration is gated on a server actually being installed.

**Status**: ✅ 🔵 **Fully supported, Zrb advantage**

---

## 31. Compaction & Prompt Caching

### Claude Code

Automatic context compaction when the window fills, `/compact [focus]` with optional focus instructions, `PreCompact`/`PostCompact` hooks, and provider-side prompt caching with a 1-hour TTL on this session's requests (5 minutes under overage).

### Zrb

Two-tier summarization (`llm/summarizer/`): a history splitter chooses the boundary, a chunk processor summarizes in parallel, and separate summarizer prompts exist for conversation, message, repo, file and web content. `/compress` and `/compact` trigger it manually; `PreCompact` and `POST_COMPACT` hooks fire around it; the summarizer model follows the main model's provider on a `/model` switch, and an unbuildable summarizer no longer fails the turn.

🔵 **Provider-agnostic prefix caching**: the system prompt is byte-stable and everything volatile is isolated into a `<live-context>` block, so the cacheable prefix does not change between turns regardless of which provider is behind it.

**Status**: ✅ **Fully supported**

**Difference that matters**: Claude Code gets caching from its provider; Zrb has to *earn* it by construction, because a dozen providers cache differently and only a byte-stable prefix works for all of them. The one gap is `/compress <focus>` — Zrb's compaction takes no focus instruction.

**Effort to close**: **Low** (1–2 days).

---

## 32. Prompt Composition & Model Adaptation

### Claude Code

A single tuned system prompt for a single vendor's models, with `--append-system-prompt` for additions and output-style presets.

### Zrb

🔵 `PromptManager` composes the prompt from ordered, individually-toggleable sections — `persona`, `principle`, `workflow`, `example`, `profile`, `system_context`, `project_context` — each a markdown file in `llm/prompt/markdown/` that is the single source of truth for its wording (no generator). The `profile` section resolves per model: three declared profiles (`minimal`, `standard`, `capable`) plus an `auto` model-id ladder, so a small local model gets more explicit phrasing than a frontier model. Project-level overrides live in `.zrb/llm/prompt/` as `.md` or `.py`. Live context (`live_context.py`) injects volatile state — pending todos, running background delegations, the active worktree, journal HUD entries — separately from the stable prefix. Skill and agent catalogues are capped (10 each) with search tools for the overflow.

**Status**: 🔵 **Zrb advantage**

**Difference that matters**: Claude Code writes one prompt for models it controls. Zrb writes a *composition* because it does not know what model is behind it — the profile ladder exists precisely because a 7B local model and a frontier model need different phrasing of the same rule.

---

## 33. Voice Input

### Claude Code

Voice dictation in the desktop and mobile surfaces.

### Zrb

🔵 Terminal-safe press-to-talk (`/voice`, `/v`) with an offline Vosk default so no audio leaves the machine, plus API-backed STT backends. Terminal state is restored correctly around the capture.

**Status**: ✅ 🔵 **Fully supported, offline by default**

---

## 34. Multimodal & Attachments

### Claude Code

Native image input on vision models; clipboard paste (including WSL screenshot paste); drag-as-attachment in the IDE; `@`-mention files; PDF reads with page ranges; Jupyter notebook reads and `NotebookEdit`.

### Zrb

🔵 A multimodal pipeline built for the case where the main model *cannot* see:
- `LLM_MULTIMODAL_MODEL` designates a vision model to describe attachments when the main model is text-only; the description is substituted into the message.
- Audio follows the same describe/transcribe fallback; video is kept for Gemini-class models and dropped-with-warning otherwise.
- If no fallback model is configured, the attachment is dropped with an explicit `⚠️ Dropped <modality>` warning rather than being sent to a provider that will reject it.
- Images auto-scale to `LLM_MAX_IMAGE_DIMENSION` (1568) at `LLM_IMAGE_JPEG_QUALITY` (85); opaque → JPEG, alpha → PNG.
- A per-model capability registry drives all of this; `/model multimodal <name>` sets the vision model at runtime.
- PDF text extraction is shared by `Read`, the attachment pipeline and `WebFetch`, with a binary fallback when extraction fails.
- Clipboard paste (Ctrl+V), `/attach`, and `/photo` for camera capture.

**Status**: ✅ 🔵 **Fully supported, Zrb advantage**

**Difference that matters**: Claude Code assumes a vision model. Zrb assumes it might not have one — the describe-then-substitute path and the explicit drop warning are direct consequences of §35. The absences are page-ranged PDF reads and notebook support.

---

## 35. Provider Coverage & Resilience

### Claude Code

One vendor (Anthropic), reached directly or through Bedrock/Vertex/Foundry, with a `--fallback-model` chain on overload. Provider quirks are invisible because the platform absorbs them.

### Zrb

🔵 Any model pydantic-ai can reach — OpenAI, Anthropic, Gemini, Ollama, xAI, Groq, HuggingFace, Cohere, Bedrock, Mistral, DeepSeek, GLM and more — with a resilience layer built for that reality:

- **Four-stage history sanitization**: filter nil content → strip orphaned tool calls → drop empty messages → ensure alternating roles.
- **Provider-specific 400 recovery**: DeepSeek's `reasoning_content` rejection retried with thinking parts stripped; GLM's empty `ValidationException` retried; Bedrock's nil-content rejection patched with a placeholder; and a **generic opaque-400** path that collapses the history to text-only and retries once, which works for providers nobody has characterized yet.
- **Empty-completion guard**: a blank or leaked `"(tool call)"` completion is regenerated.
- **Parallel-tool-call guard**: models known to malform parallel calls get `parallel_tool_calls=False` injected from the capability registry.
- **Credential scoping** (ADR-0094): `ZRB_LLM_API_KEY` reaches only the provider it was configured for, so a stray exported vendor key cannot silently displace an explicit setting.
- `request_limit=None` overrides pydantic-ai's 50-request tool-loop cap; `ModelRetry` is re-raised so the retry protocol works; a mid-session `/model` switch resolves through `ModelResolver` and reaches every consumer including the summarizer.

**Status**: 🔵 **Zrb advantage**

**Difference that matters**: this is Zrb's defining axis, and it *causes* several of the designs above — provider-agnostic caching (§31), model-adaptive prompts (§32), offline voice (§33), describe-then-substitute multimodal (§34). Claude Code never pays for this layer because it never needs it. The one thing Claude Code has that Zrb does not is an automatic fallback-model chain on overload.

---

## 36. Todos & Background Work

### Claude Code

`TodoWrite` (a session checklist, now deprecated) and background bash tasks via `Bash(run_in_background)` with `TaskOutput`, `TaskStop`, `Monitor` for waiting on a condition, and Ctrl+T to list them. Background work re-invokes the session on completion.

### Zrb

🔵 A `TodoManager` persisting to `~/.zrb/todos/{session}.json` with `pending`/`in_progress`/`completed`/`cancelled` states, auto IDs, timestamps and progress. The tool surface is `TodoWrite` (replace-semantics, subsuming update and clear) plus `TodoRead` (ADR-0068). Sessions are isolated via ContextVar; a **todo progress card** pushes to every active UI after each change (TUI, stdout, web SSE); and pending todos are **re-injected into live context every turn**, so the plan survives across turns and summarization.

Background execution: `Shell` supports background processes with a registry, and `MonitorProcess` polls one. There is no first-class background *task object* with its own lifecycle.

**Status**: ✅ **Fully supported** (Zrb advantage on todos)

**Difference that matters**: Claude Code's todos are ephemeral; Zrb's are persistent, re-injected and broadcast to every UI simultaneously. Conversely Claude Code's background tasks are first-class objects that wake the session on completion, where Zrb's are shell PIDs the model has to poll.

**Effort to close**: **Low–Medium** (3–5 days) for a completion-notification path so a finished background process re-enters the turn rather than being polled.

---

## 37. Task Automation Framework

### Claude Code

No equivalent. Claude Code is an agent; automation is delegated to the shell, CI, or the workflow runtime.

### Zrb

🔵 The other half of the product. `BaseTask`, `Task`, `CmdTask`, `LLMTask`, `HttpCheck`, `TcpCheck`, `Scheduler`, `Scaffolder`, `RsyncTask` and a `make_task` decorator, composed into a DAG with dependencies, retries, cycle detection (which now reports a clear error rather than a `RecursionError`), env/input inheritance resolved as one stateless upstream-first walk, per-task status tracking, an XCom-style FIFO queue for passing values between tasks, callbacks, and a session/context three-tier model. Every task is runnable from the CLI (`zrb <group> <task>`), from the web UI, and 🔵 **as an LLM tool** — `ListZrbTask` and `RunZrbTask` let the agent invoke the user's own task graph, which is "agent-in-pipeline" and "pipeline-in-agent" at the same time. A failed task names the environment variable that reveals its traceback, and `zrb <task>` exits with the command's own exit code.

**Status**: 🔵 **Zrb-only**

**Difference that matters**: this is why Zrb is not simply a Claude Code clone. The agent is one task type among many, so the same tool that chats can also run a deploy DAG, and the agent can call into that DAG.

---

## 38. Editor Features (Vim, Diff Viewer)

### Claude Code

Full Vim mode (`editorMode: "vim"`) with NORMAL/INSERT, navigation, text objects and `/` search; a `/diff` interactive viewer for uncommitted and per-turn changes with keyboard scrolling; IDE per-hunk accept/reject.

### Zrb

No Vim mode — standard `prompt_toolkit` input with multiline, history and reverse search. No in-TUI diff viewer; changes apply directly, `git diff` is available through `Shell`, and tool-approval dialogs render formatted edit previews at true terminal width (detected via fd 0, so diffs render correctly even when stdout is captured).

**Status**: ❌ **Not supported**

**Effort to close**: **Medium** (2–3 weeks) — Vim mode is mostly wiring `prompt_toolkit`'s existing vi bindings (1–2 wk); a `/diff` viewer over `unified_diff` + `rich` is 1–2 wk.

---

## 39. Feedback, Telemetry & Onboarding

### Claude Code

`SendFeedback` queues a structured local draft (type, area, failure mode, task category, labeled evidence bullets) that the user approves before anything is sent. `ShareOnboardingGuide` uploads an `ONBOARDING.md` and returns a link teammates open in Claude Code. `claude plugin eval` and `/skill-doctor` audit plugin and skill quality. `/fewer-permission-prompts` mines transcripts to propose a permission allowlist.

### Zrb

None of these. Zrb collects no telemetry by design and has no team-sharing surface, no plugin evaluation harness, and no transcript mining. 🔵 The repository does maintain a behavioural evaluation harness for the agent itself, but it lives outside the package.

**Status**: ❌ **Not supported**

**Difference that matters**: most of this cluster only makes sense for a vendor with users to hear from and a team surface to share into. The two pieces that would transfer are a skill/plugin linter and transcript-mined permission suggestions — both are local, both are useful without a cloud.

**Effort to close**: **Low–Medium** (1 week) for a `zrb llm skill lint` and a permission-suggestion pass over the session logs Zrb already writes.

---

## 40. Summary & Roadmap

### Coverage at a glance

| # | Area | Status | Note |
|---|------|--------|------|
| 1 | Distribution & Surfaces | 🟡 | Terminal + self-hosted web vs five vendor-operated surfaces |
| 2 | CLI Flags | 🟡 | 7 generated inputs vs ~70 hand-written flags |
| 3 | Interactive TUI | 🟡 | Parity on the loop; no keybinding file, no vim |
| 4 | Slash Commands | 🟡 | 16 rebindable families vs ~60 built-ins |
| 5 | Memory & Project Context | ✅ | Journal graph vs flat memory files; no `@import`/`.local` |
| 6 | Hooks | 🟡 | 16 events + agent-as-hook; no `http` handler |
| 7 | MCP & Connectors | 🟡 | stdio + http, deferred, result-capped; no OAuth/resources/prompts |
| 8 | Subagents | 🟡 | Policy/sandbox inheritance, fan-out, background; no auto-delegation |
| 9 | Teams & Workflow Runtime | ❌ | The largest engine gap |
| 10 | Skills | ✅ | Reads `.claude/` layout, adds `SKILL.py` + governance split |
| 11 | Plugins | 🟡 | Consumes plugin layout; no packaging or marketplace |
| 12 | Permissions | 🟡 | Capability-tagged engine; no named presets or arg-pattern config |
| 13 | Auto Mode | ❌ | Rule-based enforcement only |
| 14 | Settings | 🟡 | 242 documented knobs + `config explain`; no scoped JSON files |
| 15 | Built-in Tools | 🟡 | 41 tools, conditionally registered, with spill; no product-surface tools |
| 16 | Deferred Tool Loading | ✅ | Same mechanism, treated as a design constraint |
| 17 | IDE Integration | ❌ | — |
| 18 | Sessions & Rewind | ✅ | Git-backed snapshots + partial-run retry; rewind off by default |
| 19 | Web UI & HTTP API | 🔵 | Self-hosted, loopback-by-default, JWT-authed |
| 20 | Artifacts | ❌ | Second-largest gap; a hosting gap, not an engine gap |
| 21 | Design & Dataviz | 🟡 | Methodology skills, no canvas |
| 22 | Code Review Tooling | 🟡 | Review skill + agent; no structured findings or PR comments |
| 23 | GitHub / CI | ❌ | `gh`/`glab` via shell; no app or triggers |
| 24 | Sandboxing | 🟡 | FS + bwrap/seatbelt + credential deny-read; no network filtering |
| 25 | Remote, Cloud & Channels | 🟡 | MultiUI + multiplexed approvals + HTTP API; no protocol or cloud |
| 26 | Scheduling | 🟡 | Rigorous `Scheduler`; not model-callable; no cloud |
| 27 | Worktree Isolation | 🟡 | Tools + tracking + stale guard; no per-agent isolation |
| 28 | Rate Limiting & Cost | 🟡 | Richer throttling than CC exposes; no money view |
| 29 | Platform Support | ✅ | macOS/Linux/Windows-hardened + Termux |
| 30 | LSP | ✅ 🔵 | 8 tools over 21 servers, rename with dry-run |
| 31 | Compaction & Caching | ✅ | Two-tier summarization + byte-stable cacheable prefix |
| 32 | Prompt Composition | 🔵 | Ordered sections × per-model profiles |
| 33 | Voice | ✅ 🔵 | Offline Vosk by default |
| 34 | Multimodal | ✅ 🔵 | Describe-then-substitute fallback; no page ranges/notebooks |
| 35 | Provider Coverage | 🔵 | Any provider + a deep resilience layer |
| 36 | Todos & Background | ✅ 🔵 | Persistent, re-injected, broadcast; background is poll-based |
| 37 | Task Automation Framework | 🔵 | DAG engine; agent-in-pipeline both ways |
| 38 | Vim & Diff Viewer | ❌ | — |
| 39 | Feedback & Onboarding | ❌ | No telemetry by design |

### Where Zrb is a genuine superset

1. **Any provider**, with a resilience layer no single-vendor tool needs: four-stage history sanitization, provider-specific and generic opaque-400 recovery, an empty-completion guard, a parallel-tool-call guard, and credential scoping.
2. **A task automation framework** the agent lives inside — DAG, dependencies, retries, cycle detection, scheduling — with every task callable as an LLM tool and every LLM run callable as a task.
3. **Model-adaptive prompt composition**: ordered sections × declared per-model profiles, with project-level overrides.
4. **A capability-tagged permission engine** (`read`/`edit`/`execute`/`network`/`delegate`/`meta`) with selective yolo, argument-inspecting tool policies, and inheritance into sub-agents.
5. **A self-hosted web UI + HTTP chat API**, loopback by default, JWT-authed, with browser-side tool approval.
6. **MultiUI + MultiplexApprovalChannel**: one session fanned across several backends, first-response-wins input, approvals raced correctly.
7. **A structured journal**: typed entries, backlinks, git-backed, auto-searched per turn, HUD-rendered, with a compliance hook.
8. **A richer LSP client**: 8 tools over 21 server configurations, workspace symbols, rename with dry-run, post-write diagnostics.
9. **Lossless tool-result spill** to a `0700` escape-checked store instead of truncation, plus MCP result capping against a token budget.
10. **Conditional tool registration** — LSP, worktree, journal, plan-mode and spill tools appear only when they can do anything — re-evaluated on every agent build.
11. **Discoverable, white-labelable config**: 242 documented knobs, `zrb config explain`, a configurable env prefix, and a fail-fast init loader.
12. **Rate limiting the caller controls**: req/min, tok/min, tok/request, `Retry-After`-aware backoff, and a classified `StopFailure`.
13. **Persistent todos** re-injected into live context and broadcast to every UI.
14. **Provider-agnostic prefix caching** via a byte-stable prompt and an isolated `<live-context>` block.
15. **Offline voice** (Vosk by default) and **Termux support**.
16. **Drop-in Claude Code compatibility**: reads `.claude/` skills, agents and command hooks — including the JSON stdin payload and tool-name matchers — as-is.
17. **Self-hosted, no subscription, no telemetry**: bring your own key, or point at Ollama.

### Recommended priority

#### Phase 1 — high leverage, low effort (4–6 weeks)

1. Named permission presets (`acceptEdits`, `bypassPermissions`) + `--permission-mode` (3–5 d).
2. CLI flags over engine capability that already exists: `--max-turns`, `--system-prompt`, `--resume`, `--continue`, `--output-format json`, `--allowed-tools`/`--disallowed-tools`, `--add-dir` (1 wk).
3. Scoped JSON settings files merged *under* the env vars (1 wk).
4. `CronCreate`/`CronDelete`/`CronList` wrapping the existing `Scheduler` (2–3 d).
5. Management commands over existing machinery: `/clear`, `/config`, `/permissions`, `/export`, `/status`, `/mcp`, `/hooks`, `/agents`, `/cost` (1 wk).
6. `/usage` + a per-model price map + a soft budget cap (3–5 d).
7. `CLAUDE.local.md` + `@import` expansion (3–4 d).
8. Rewind on by default + an Esc-Esc shortcut (2–3 d).
9. `/compress <focus>` (1–2 d).
10. `NotebookEdit` + page-ranged PDF reads (3–4 d).
11. Background-process completion notification instead of polling (3–5 d).

#### Phase 2 — medium effort (6–10 weeks)

12. Network sandboxing (`bwrap --unshare-net` + allowlisting proxy; seatbelt rules on macOS) (2–3 wk).
13. Natural-language auto-delegation + an `/agents` UI (2–3 wk).
14. Worktree isolation as policy: `isolation:` on agent definitions, `--worktree`, worktree hook events (2–3 wk).
15. Structured code-review findings + `gh`/`glab` PR comment posting (1 wk).
16. MCP: SSE/WebSocket, OAuth, resources, prompts-as-commands, `zrb mcp` CLI (2–3 wk).
17. Plugin packaging + `zrb plugin add/list/remove` + reload (1–2 wk).
18. `http` hook handler + `if`/`once`/`statusMessage` + worktree/task events (1 wk).
19. Skill frontmatter gaps: `paths`, `` !`cmd` `` injection (1 wk).
20. A keybindings JSON layer + vim mode (2–3 wk).
21. GitHub/GitLab CI templates running `zrb llm please` on a PR (1 wk).
22. A WebSocket remote-control endpoint + a declarative channel-plugin contract over `MultiUI` (2–3 wk).

#### Phase 3 — structural (3–6 months)

23. A workflow runtime — script-orchestrated fan-out and pipelining over the existing DAG and background delegate (6–10 wk).
24. Locally-hosted artifacts: versioned pages served from the existing web server, a SQLite page database, an asset store (6–8 wk).
25. An auto-mode safety classifier layered onto `PermissionPolicy` (4–6 wk).
26. Agent teams with inter-agent messaging (2–3 mo).
27. IDE extensions (3–4 mo per IDE).
28. Cloud sessions and cloud scheduling (infrastructure, not code).

### Net assessment

**Zrb is at parity on the local agent loop and a superset on everything that follows from being self-hosted and provider-agnostic.** File, shell, web and LSP tools; plan mode; a capability-tagged permission engine; an opt-in FS/OS sandbox; snapshot and rewind; two-tier summarization; deferred tool loading; skills that read Claude Code's own `.claude/` layout — all present, several better. Its distinctive designs are not decoration: provider-agnostic caching, per-model prompt profiles, describe-then-substitute multimodal, offline voice and deep 400-recovery all exist *because* Zrb targets a dozen providers, which is a problem Claude Code's managed platform does not have. On top of that sits a task automation framework with no Claude Code counterpart at all.

**Claude Code leads in three clusters, and all three lean on its being a vendor-operated product rather than a library.** *Orchestration at scale*: agent teams and the `Workflow` runtime, where Zrb has the building blocks (DAG, parallel delegation, background runs) but no script-driven orchestrator and no inter-agent addressing. *Output surfaces*: artifacts, the design canvas, IDE extensions, Slack, cloud sessions, remote control — a published, shareable, stateful page is not something a `pip install` can offer without hosting. *Adaptive safety*: the auto-mode classifier, against which Zrb's `bash_safe_command_policy` is a hand-written static approximation.

**The rest of the gap is breadth of mechanical surface, not capability** — CLI flags, ~60 slash commands, layered JSON settings, network sandboxing, in-session cron tools, a cost view. Nearly every item in Phase 1 wraps machinery Zrb already has, which is why that phase is measured in days per item.

The honest summary: the two tools are converging on the same agent loop from opposite ends. Claude Code is a product growing an engine; Zrb is an engine growing a product. Zrb's remaining work in Phases 1–2 is almost entirely *exposure* — and its Phase 3 items are the places where Claude Code's product shape, not its engine, is the real differentiator.

---

*Zrb 3.0.0 · Compared against the current Claude Code surface*
