🔖 [Documentation Home](../../README.md) > [LLM](./) > Hooks

# Zrb Hook System (Claude Code Compatible)

Hooks intercept and modify an LLM agent's run: at key lifecycle events they execute a shell command, an LLM prompt, or a tool-using agent.

The system is **modeled on Claude Code hooks**: the same files, stdin payload, `CLAUDE_*` env vars, and matcher/decision JSON, so most single-hook Claude configurations work unchanged. It is **not** a full reimplementation — the multi-hook execution model in particular differs. Read [Differences from Claude Code](#differences-from-claude-code) before porting a non-trivial hook.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Differences from Claude Code](#differences-from-claude-code)
- [Hook Locations](#hook-locations)
- [Lifecycle Events](#lifecycle-events)
- [Hook Configuration](#hook-configuration)
- [Hook Types](#hook-types)
- [Matchers](#matchers)
- [Priority System](#priority-system)
- [Blocking Decisions](#blocking-decisions)
- [Extending a Turn (Stop)](#extending-a-turn-with-system-messages-stop)
- [Environment Variables](#environment-variables)
- [Defining Hooks Programmatically](#defining-hooks-programmatically-python)
- [Examples](#examples)
- [HookResult Reference](#hookresult-reference)

---

## Quick Start

Create a hook file in `~/.zrb/hooks.json` or `./.zrb/hooks.json`:

```json
[
  {
    "name": "log-session-start",
    "events": ["SessionStart"],
    "type": "command",
    "config": {
      "command": "echo 'Session started at $(date)' >> /tmp/zrb-hooks.log",
      "shell": true
    }
  }
]
```

More examples are in [Examples](#examples) and `examples/llm-hooks/.zrb/hooks.json`.

---

## Differences from Claude Code

The runtime is a separate implementation; the differences below **change outcomes**, so adjust a ported hook that relies on any of them.

### Behavioral differences

| # | Area | Claude Code | Zrb |
|---|------|-------------|-----|
| 1 | **Multi-hook execution** | All matching hooks run **in parallel**; identical commands are deduplicated | Hooks run **sequentially**, ordered by the zrb-only `priority` field |
| 2 | **Conflict resolution** | **Most-restrictive wins** (`deny` > `defer` > `ask` > `allow`) regardless of order | **First decisive result wins** (highest priority first) |
| 3 | **`additionalContext` from multiple hooks** | Merged from **all** hooks | Only the **first** non-empty value is used; the rest are dropped |
| 4 | **`PostToolUse` block** | Tool already ran; block halts the turn and feeds the reason back — **the tool result stays** in context | Block **discards** the tool result and replaces it with a "Tool result blocked…" message |
| 5 | **`PreToolUse` `permissionDecision: "ask"`** | Always shows the approval prompt | Forces the prompt **only on the approval path** (tools that require approval). For auto-approved tools it degrades to "proceed" — there is no prompt to show |
| 6 | **`SubagentStop` blocking** | Supports `decision: "block"` to force the subagent to continue | **Observe-only** — a block is ignored |
| 7 | **`Notification` firing** | Fires for permission prompts, 60s idle, auth, elicitation, etc. | Fires only for elicitation (`notification_type='elicitation_dialog'`, from the ask/question tool). No permission-prompt or idle notifications — permission prompts route to the `PermissionRequest` event instead, and there is no idle timer |
| 8 | **Legacy `decision: "approve"`** | Auto-approves a `PreToolUse` call (deprecated form) | Ignored — auto-approve only via `permissionDecision: "allow"` |

> The `exit 2` reason channel (stderr), `PostToolUse` `additionalContext`, and the `Notification` matcher field (`notification_type`) **were** divergences and are now Claude-compatible — see the [changelog](../changelog/README.md).

### Matcher value coverage (matchers fire on a subset of Claude's values)

| Event | Claude values | Zrb values |
|-------|---------------|------------|
| `SessionStart` (`source`) | `startup`, `resume`, `clear`, `compact` | `startup`, `resume` only |
| `PreCompact` / `PostCompact` (`trigger`) | `manual`, `auto` | `auto` only |
| `StopFailure` (`error_type`) | includes `max_output_tokens`, `oauth_org_not_allowed`, `billing_error` | uses `context_length` (not `max_output_tokens`); lacks `oauth_org_not_allowed` / `billing_error` |

A matcher keyed on a value zrb never emits simply never fires.

### Events and types zrb does not implement

- **Claude-only events** (no zrb counterpart): `Setup`, `UserPromptExpansion`, `PostToolBatch`, `PermissionDenied`, `TeammateIdle`, `Elicitation` / `ElicitationResult`, `FileChanged`, `CwdChanged`, `ConfigChange`, `InstructionsLoaded`, `TaskCreated` / `TaskCompleted`, `WorktreeCreate` / `WorktreeRemove`, `MessageDisplay`.
- **Claude-only hook types / options**: `http` and `mcp_tool` hook types, the `if` argument-level filter (e.g. `Bash(git *)`), `async` / `asyncRewake` / `once`, command exec-form `args`, and `disableAllHooks`. Zrb supports the `command`, `prompt`, and `agent` types only.

### Zrb-only events (no Claude counterpart)

- `PreCommand` / `PostCommand` — bracket a UI command in the chat TUI (Claude's nearest analogue is `UserPromptExpansion`, with a different contract).

### What ports cleanly

Single-hook configurations using the common contract behave the same in both: `PreToolUse` deny / allow / `updatedInput` / `permissionDecisionReason`, `UserPromptSubmit` block + `continue: false` + `additionalContext`, `SessionStart` `additionalContext` (including plain-stdout-as-context), `Stop` block-to-continue (8-block cap, `stop_hook_active`) and `systemMessage` extension (its own separate 8-message cap), `PermissionRequest` `decision.behavior`, `PreCompact` block, and tool-name matchers (including the `Bash` / `Task` aliases).

---

## Hook Locations

Hooks are discovered automatically in these locations (in order of precedence, highest first):

| Location | Purpose |
|----------|---------|
| Plugin `hooks/` dirs | The bundled `llm_plugin` hooks, plus entries under `ZRB_LLM_PLUGIN_DIRS` |
| `~/.zrb/hooks.json` | User-level hooks (single file) |
| `~/.zrb/hooks/*.json` | User-level hooks directory |
| `~/.claude/hooks.json` | Claude Code compatibility (single file) |
| `~/.claude/hooks/*.json` | Claude Code compatibility (directory) |
| `~/.claude/settings.json` | Claude Code compatibility — the nested `hooks` block |
| `~/.claude/settings.local.json` | Claude Code compatibility — the nested `hooks` block |
| `./.zrb/hooks.json` | Project-specific hooks (single file) |
| `./.zrb/hooks/*.json` | Project-specific hooks directory |
| `./.claude/hooks.json` | Claude Code compatibility, project (single file) |
| `./.claude/hooks/*.json` | Claude Code compatibility, project (directory) |
| `./.claude/settings.json` | Claude Code compatibility, project — the nested `hooks` block |
| `./.claude/settings.local.json` | Claude Code compatibility, project — the nested `hooks` block |
| `CFG.HOOKS_DIRS` | Additional colon-separated (semicolon on Windows) custom directories |

Hooks Claude Code (and drop-in tools like [peon-ping](https://peonping.com)) register inside `settings.json`/`settings.local.json` are picked up automatically — only the nested `hooks` block is read; other settings keys are ignored.

### Hooks Subsystem Configuration

These `CFG`/env knobs control the subsystem as a whole, independent of each hook's own `enabled`/`timeout` fields:

| `CFG` field | Env var | Default | Description |
|-------------|---------|---------|--------------|
| `HOOKS_ENABLED` | `ZRB_HOOKS_ENABLED` | `on` | Master on/off switch for the entire hooks subsystem |
| `HOOKS_DIRS` | `ZRB_HOOKS_DIRS` | `""` | Colon-separated (semicolon on Windows) additional directories to scan for hook scripts |
| `HOOKS_TIMEOUT` | `ZRB_HOOKS_TIMEOUT` | `30000` | Timeout in milliseconds for hook execution |
| `HOOKS_EXIT_TIMEOUT` | `ZRB_HOOKS_EXIT_TIMEOUT` | `10000` | Milliseconds the chat TUI waits, as it exits, for hooks still running before cancelling them |
| `LLM_HOOKS` | `ZRB_LLM_HOOKS` | `""` | Name allowlist for the hooks zrb dispatches (ADR-0091). Empty = run every registered hook; non-empty restricts dispatch to the named hooks (e.g. `journal-compliance-judge`). Programmatic registration is unchanged — see [LLM Component Collections](../configuration/llm-collections.md) |

`HOOKS_ENABLED=off` disables the subsystem regardless of any `hooks.json`. `LLM_HOOKS` filters on top of it: with `HOOKS_ENABLED` off, nothing fires even if a hook's name is allowed.

---

## Lifecycle Events

| Event | When it fires / what it can do | Can Block? |
|-------|-------------------------------|------------|
| `SessionStart` | Chat session begins. `source` is `startup` (fresh history) or `resume` (continued). Can inject `additionalContext` | No |
| `SessionEnd` | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn; use `Stop` for per-turn work. Matches on `source`; carries `reason` | No |
| `UserPromptSubmit` | Before the LLM processes text. Matches on the `prompt` field. Can inject `additionalContext`; can halt the turn (`continue: false`) | **Yes** |
| `PreCommand` | Before a UI command runs (chat TUI). A block cancels the command; can rewrite its argument via `command_args` | **Yes** |
| `PostCommand` | After a recognized UI command runs. Carries `command_handled` | No |
| `PreToolUse` | Before **every** tool call. `permissionDecision` is `deny` (block), `allow` (auto-approve), `ask` (force the approval prompt), or `defer` (no opinion), plus a reason; `updatedInput` rewrites args | **Yes** |
| `PostToolUse` | After a tool succeeds. Can block the result (`decision: "block"`) or replace it (`updatedToolOutput`) | **Yes** |
| `PostToolUseFailure` | After a tool raises. Carries `error` | No |
| `PermissionRequest` | A tool call reaches an interactive approval prompt (only when the user is actually asked — not for auto-approved/YOLO/policy-allowed calls). Can auto-resolve via `hookSpecificOutput.decision.behavior` (`allow`/`deny`) | **Yes** |
| `Notification` | System notifications (`message`, `title`, `notification_type`). `AskUserQuestion` fires one with `notification_type='elicitation_dialog'` when it blocks for an answer | No |
| `Stop` | A turn finishes and control returns to the user — the per-turn "done" signal. Can **block-to-continue** (`decision: "block"` + `reason`), extend the turn with `systemMessage` (+ `replaceResponse`), or end it with `continue: false`. See [Extending a Turn](#extending-a-turn-with-system-messages-stop) | **Yes** |
| `StopFailure` | A turn ends on an unrecoverable API error. Observe-only; matches on `error_type` (`rate_limit`, `overloaded`, `server_error`, `context_length`, `authentication_failed`, `invalid_request`, `model_not_found`, `unknown`) | No |
| `PreCompact` | Before history summarization (`trigger: "auto"`). Can inject `additionalContext`; can **block** compaction (`decision: "block"` / exit 2) to skip summarization for the turn | **Yes** |
| `PostCompact` | After history summarization completes (`trigger: "auto"`). Can inject `additionalContext` | No |
| `SubagentStart` | A sub-agent (delegation) begins. Observe-only; matches on `agent_type` (the delegated agent's name); also carries `agent_id` | No |
| `SubagentStop` | A sub-agent finishes (success or error). Observe-only; same `agent_type`/`agent_id` as its `SubagentStart` | No |

`PreCommand` / `PostCommand` fire when the user runs any built-in or custom command token (`/save`, `/exit`, a custom `>` redirect, …; not only `/`-prefixed), exposed as `command_name` / `command_args` (see [Environment Variables](#environment-variables)). Plain chat messages do **not** fire them.

A `PreCommand` hook **rewrites the command's argument** by returning `command_args` — the token is kept, the argument swapped. For example, redirect a model switch:

```python
async def downgrade_opus(ctx):
    if ctx.command_name == "/model" and "opus" in (ctx.command_args or "").lower():
        return HookResult(modifications={"command_args": "sonnet"})  # opus -> sonnet
    return HookResult()
```

A command hook does the same by printing `{"command_args": "sonnet"}` on stdout. The highest-priority hook that sets `command_args` wins.

---

## Hook Configuration

Hooks are defined in JSON or YAML:

```json
{
  "name": "hook-name",
  "events": ["EventName"],
  "type": "command|prompt|agent",
  "config": {
    // Type-specific configuration
  },
  "description": "Optional description",
  "matchers": [
    {
      "field": "field.path",
      "operator": "equals|not_equals|contains|regex|glob|starts_with|ends_with",
      "value": "value to match",
      "case_sensitive": true
    }
  ],
  "async": false,
  "enabled": true,
  "timeout": 30,
  "env": {
    "KEY": "value"
  },
  "priority": 0
}
```

### Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique hook identifier |
| `events` | array | Yes | List of events to attach to |
| `type` | string | Yes | Hook type: `command`, `prompt`, or `agent` |
| `config` | object | Yes | Type-specific configuration |
| `description` | string | No | Human-readable description |
| `matchers` | array | No | Conditions to filter when hook runs |
| `async` | boolean | No | Fire-and-forget in the background without blocking the event (default: false). Only `command` hooks honor it; `prompt`/`agent` hooks always run synchronously, since their modifications often feed back into the blocking flow |
| `enabled` | boolean | No | Hook is active (default: true) |
| `timeout` | number | No | Seconds; a synchronous hook past it is cancelled (a `command` hook's process killed) and waited for up to 5 seconds. A hook still running when the chat exits — a Stop fired by Ctrl+C — gets up to `ZRB_HOOKS_EXIT_TIMEOUT` (10000 ms) more before it is cancelled. Default: `command` 600s, `prompt` 30s, `agent` 60s |
| `env` | object | No | Environment variables to inject |
| `priority` | number | No | Execution priority (higher = earlier; default 0) — see [Priority System](#priority-system) |

---

## Hook Types

| Type | Use case |
|------|----------|
| `command` | Shell scripts, system commands |
| `prompt` | LLM-based analysis, content filtering |
| `agent` | Multi-step analysis with tools |

### 1. Command Hooks

```json
{
  "name": "security-check",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "python3 /path/to/security_check.py",
    "shell": true,
    "working_dir": "/optional/working/dir"
  },
  "matchers": [
    {
      "field": "tool_name",
      "operator": "equals",
      "value": "dangerous_tool"
    }
  ],
  "priority": 100
}
```

With no explicit `timeout`, this runs at the `command` default of 600 seconds.

**Command Hook Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Shell command to execute |
| `shell` | boolean | Use shell interpreter (default: true) |
| `working_dir` | string | Working directory (optional) |

**Input: env vars _and_ stdin.** Both Claude-Code hook styles work: the `CLAUDE_*` [environment variables](#environment-variables) are set, and the full event payload is written to **stdin** as JSON (`hook_event_name`, `session_id`, `cwd`, …; tool events add `tool_name`, `tool_input`, and `tool_response` on `PostToolUse`):

```bash
event=$(cat)                                    # read the JSON payload from stdin
name=$(echo "$event" | jq -r .hook_event_name)  # e.g. "Stop"
```

**Output: stdout.** Print a JSON object (`{"decision": ...}`, `{"permissionDecision": ...}`, …) to control behavior. For `SessionStart` and `UserPromptSubmit`, **plain (non-JSON) stdout is injected as `additionalContext`**, as in Claude Code — `echo "Current branch: $(git branch --show-current)"` adds that line to the model's context.

### 2. Prompt Hooks

Run an LLM prompt for analysis or a decision.

```json
{
  "name": "safety-review",
  "events": ["UserPromptSubmit"],
  "type": "prompt",
  "config": {
    "user_prompt_template": "Review this user prompt for safety: {{prompt}}",
    "system_prompt": "You are a safety reviewer. Check for harmful content.",
    "model": "openai:gpt-4o-mini",
    "temperature": 0.0
  }
}
```

**Prompt Hook Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `user_prompt_template` | string | Template with `{{variable}}` substitution |
| `system_prompt` | string | System prompt for the LLM |
| `model` | string | Model to use (e.g., `openai:gpt-4o-mini`) |
| `temperature` | number | Sampling temperature (default: 0.0) |

**Template variables** in `user_prompt_template`:

- `{{prompt}}` - User's input text
- `{{session_id}}` - Session identifier
- `{{metadata}}` - Context metadata
- `{{tool_name}}` - Tool name (for tool events)
- `{{tool_input}}` - Tool input JSON (for tool events)

### 3. Agent Hooks

Run a tool-using agent for complex analysis.

```json
{
  "name": "agent-review",
  "events": ["PreToolUse"],
  "type": "agent",
  "config": {
    "system_prompt": "You are a security agent. Review tool calls for safety.",
    "tools": ["Read", "WebFetch"],
    "model": "openai:gpt-4o"
  }
}
```

**Agent Hook Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `system_prompt` | string | System prompt for the agent |
| `tools` | array | Tool names, Claude-compatible aliases honored (`"Bash"` → `Shell`), resolved against zrb's own tool set — including config-gated tools such as the journal ones (`LogActivity`, `WriteJournalNote`, `SearchJournal`) that exist only while their feature is enabled. A tool's `[SYSTEM SUGGESTION]` error comes back as a tool result the hook's model can react to, as for the main agent, rather than aborting the hook run |
| `model` | string | Model to use (e.g., `openai:gpt-4o`); omit to fall back to `ZRB_LLM_MODEL` |

If every name in `tools` fails to resolve — usually because their feature is off (e.g. journal tools while `LLM_JOURNAL_ENABLED` is `false`) — the hook skips its LLM call. A hook that wants no tools leaves `tools` empty and is unaffected.

A runnable version of this snippet is `security-review-agent-example` in `examples/llm-hooks/.zrb/hooks.json`, shipped `enabled: false` because an agent hook on `PreToolUse` adds a model round-trip to every matching tool call.

### Built-in example: the journal-compliance judge

A small sub-agent that reviews a completed turn, decides — using `LogActivity`/`WriteJournalNote`'s own documented criteria — whether it needs a journal entry, and writes one if so. The `event_data.wrote_files` matcher (computed in plain Python at the `Stop` call site) limits the LLM call to turns that changed a file, and `async: true` keeps it from blocking the response.

- **Built-in and active** (`llm/hook/journal_compliance.py`, registered as a hook factory on the default `hook_manager` singleton), with no `enabled` flag of its own: it follows `LLM_JOURNAL_ENABLED` (default on). With journaling off, `tools` resolves to nothing and the hook is a no-op.
- **Model:** `CFG.LLM_SMALL_MODEL` (via `resolve_configured_small_model()`). Set `ZRB_LLM_SMALL_MODEL` — an unset small model falls back to your main one, which defeats the point of a cheap judge.
- **Prompt:** `llm/prompt/markdown/journal_compliance.md`, overridable through the normal chain — a `journal_compliance.md` under your project's `LLM_PROMPT_DIR`, or `ZRB_LLM_PROMPT_JOURNAL_COMPLIANCE`.

Its `HookConfig`, for reference (built in Python by `build_journal_compliance_hook_config()`, not JSON):

```json
{
  "name": "journal-compliance-judge",
  "events": ["Stop"],
  "type": "agent",
  "config": {
    "system_prompt": "You are a journal-compliance judge, not the main assistant. You will be shown one completed turn's transcript. Decide, using exactly the criteria in LogActivity's and WriteJournalNote's own tool descriptions, whether this turn produced something worth recording. If so, call the appropriate tool now. If not, do nothing and reply: skip.",
    "tools": ["LogActivity", "WriteJournalNote", "SearchJournal"],
    "model": "<ZRB_LLM_SMALL_MODEL, or your main model if unset>"
  },
  "matchers": [
    { "field": "event_data.wrote_files", "operator": "equals", "value": true }
  ],
  "async": true
}
```

For how it is wired end-to-end (the registration seam, the `HookType.AGENT` builder, where the LLM call happens), see [llm-chat-lifecycle.md](./llm-chat-lifecycle.md#tracing-an-agent-type-hook-journal-compliance).

### Built-in: the self-review gate

Off by default; `ZRB_LLM_SELF_REVIEW_ENABLED=on` turns it on (ADR-0100). At the start of each turn it snapshots your working directory into a private temporary git store, and at Stop it snapshots it again and diffs the two. A snapshot holds every git repository under the directory, each by its own `.gitignore` — nested clones, submodules, and repositories the parent ignores, such as the worktrees `EnterWorktree` creates, included — and the files outside any repository (ADR-0101). So the review covers exactly what the turn changed — edits made through `Shell` and changes committed mid-turn included, your own earlier uncommitted work excluded — and a reviewer agent with a fresh context reads that diff, using read-only `Read`/`Grep`/`Glob` to check the code around it. It ends its report with `Request changes` or `LGTM`.

A repository that appears during the turn — a worktree, a clone — is diffed against the commit it started from, so the review shows what the turn changed in it rather than its whole checkout.

Paths the file tools named that the diff does not cover — ignored, or outside the working directory — are listed for the reviewer to read. Without a snapshot — it failed, or the directory holds more than 5,000 files or 200 MB outside any repository, which is reported once per session — the reviewer gets those paths with no diff, never `git diff HEAD`, which would include your earlier uncommitted work. A file git cannot read at Stop is listed as unreadable instead of showing as deleted.

A delegated sub-agent's turn is not reviewed on its own: its changes land in your working directory, or in a worktree under it, so they are part of the parent turn's diff, which is. A live sub-agent continuation you message after the parent turn has ended is the exception — no parent review covers it, so it is reviewed on its own.

Snapshots write their index and objects into a private, owner-only temporary store deleted when the turn ends — never into any repository's `.git/objects`, so untracked secrets such as a `.env` are not copied there.

`Request changes` blocks the Stop: the findings become the agent's next prompt, with the instruction to check each against the code, fix the real ones, say why any is not a defect, and restate the final answer. Anything else — `LGTM`, an unclear verdict, a failed review — lets the turn end.

| Env var | Default | Effect |
|---------|---------|--------|
| `ZRB_LLM_SELF_REVIEW_MAX_ROUNDS` | `2` | Caps consecutive blocking reviews; a review that lets the turn end resets the count |
| `ZRB_LLM_SELF_REVIEW_TIMEOUT` | `240` (seconds) | Bounds each review; on expiry the reviewer is cancelled, model request included, and the turn ends unreviewed |
| `ZRB_LLM_SELF_REVIEW_MAX_TRACKED_TURNS` | `64` | Turns whose round count is kept at once; the oldest past it are dropped |
| `ZRB_LLM_SELF_REVIEW_MODEL` | empty | The reviewer's model (empty uses the run's own). This model receives the turn's diff |

It is a Python hook (`llm/hook/self_review.py`), not a JSON one, because it needs things a JSON agent hook cannot express: a turn-start snapshot (the Stop payload's `turn_start_snapshot`, taken only while the gate is on and only for a top-level run — `nested_run` in the payload marks a sub-agent's) and `changed_paths` as its scope, a round counter per turn (`turn_id` — unique, unlike `run_scope`, which is the conversation's name), and the diff instead of the transcript as its input. The reviewer's instructions live in `llm/prompt/markdown/self_review.md`; override them through `LLM_PROMPT_DIR` like the other internal prompts.

---

## Matchers

Matchers restrict when a hook runs.

### Matcher Operators

| Operator | Description |
|----------|-------------|
| `equals` | Exact match |
| `not_equals` | Not equal to value |
| `contains` | Contains substring |
| `starts_with` | Starts with string |
| `ends_with` | Ends with string |
| `regex` | Matches regular expression |
| `glob` | Matches glob pattern |

### Matcher Fields

`field` uses dot notation for nested context (e.g. `event_data.file_path`):

| Field | Description |
|-------|-------------|
| `tool_name` | Name of the tool being called |
| `tool_input` | Tool input data |
| `metadata.project` | Project name from metadata |
| `metadata.environment` | Environment (e.g., production) |
| `event_data.file_path` | File path from event data |

### Tool names (Claude-compatible)

Built-in tools use Claude-compatible names (`Read`, `Write`, `Edit`, `Grep`, `Glob`, `LS`, `Shell`, `WebFetch`, `WebSearch`, `TodoWrite`, `TodoRead`, …), so a Claude matcher keyed on a tool name — `{"matcher": "Edit"}` or a `tool_name` matcher — works as-is. Where a zrb name differs, the Claude name is accepted as an **alias** on `tool_name` matchers:

| zrb tool | also matches |
|----------|--------------|
| `Shell` (the default shell tool) | `Bash` |
| `DelegateToAgent`, `DelegateToAgentBackground` | `Task` |

Aliases apply to positive operators (`equals`, `regex`, `contains`, …); a `not_equals` matcher compares against the literal name only, so an exclusion is never silently widened.

### Case Sensitivity

Comparisons are case-sensitive unless `case_sensitive: false`:

```json
{
  "field": "tool_name",
  "operator": "contains",
  "value": "admin",
  "case_sensitive": false
}
```

### Multiple Matchers

Multiple matchers use AND logic (all must match):

```json
{
  "matchers": [
    {
      "field": "tool_name",
      "operator": "equals",
      "value": "delete_files"
    },
    {
      "field": "metadata.environment",
      "operator": "equals",
      "value": "production"
    }
  ]
}
```

---

## Priority System

Hooks run sequentially, higher `priority` first (default `0`), so critical hooks run before others. Here `security-check` runs before `logging`:

```json
[
  {
    "name": "security-check",
    "priority": 100,
    ...
  },
  {
    "name": "logging",
    "priority": 10,
    ...
  }
]
```

---

## Blocking Decisions

### Exit code 2 or `decision: "block"`

Block by exiting `2`, or by printing a JSON object with `"decision": "block"` (e.g. `{"decision": "block", "reason": "Operation requires manual approval"}`):

```bash
#!/bin/bash
echo '{"decision": "block", "reason": "Dangerous operation blocked"}'
exit 2
```

The block reason is taken, in this precedence, from a `reason` in stdout JSON, from stderr (the Claude convention, e.g. `echo "reason" >&2; exit 2`), or from plain stdout text.

A block is honored only on the events marked **Yes** in the [lifecycle table](#lifecycle-events) (`UserPromptSubmit`, `PreCommand`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `Stop`, `PreCompact`). On an observe-only event (e.g. `Notification`, `SessionStart`, `SubagentStop`) it is ignored and the remaining hooks for that event still run.

### Halting the run (`continue: false`)

Unlike a per-event block, `continue: false` (with an optional `stopReason`) unconditionally stops all processing, on any event:

```bash
echo '{"continue": false, "stopReason": "Quota exhausted"}'
```

On `UserPromptSubmit` the turn ends before the model runs; on `Stop` it ends the turn, overriding any block-to-continue or `systemMessage` extension.

### `PreToolUse` permission decisions

`PreToolUse` hooks control a tool call via `permissionDecision` (top-level or nested under `hookSpecificOutput`):

| `permissionDecision` | Description |
|----------------------|-------------|
| `deny` | Block the call; show `permissionDecisionReason` to the model |
| `allow` | Auto-approve; skip the approval prompt entirely |
| `ask` | Force the interactive approval prompt, overriding any tool-policy/permission ALLOW or YOLO auto-approve (an explicit DENY still wins) |
| `defer` | No opinion — let the normal approval flow decide |

`ask` only forces a prompt for tools that go through the approval cascade; elsewhere it degrades to proceed (see [Differences](#differences-from-claude-code), row 5).

### Permission / Approval Hook Example

```json
{
  "name": "require-approval",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "echo '{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"permissionDecision\": \"ask\", \"permissionDecisionReason\": \"Requires manual approval\"}}'"
  }
}
```

This hook triggers before every tool call, forcing user approval.

---

## Extending a Turn with System Messages (Stop)

A `Stop` hook can return a `systemMessage` to trigger more LLM work when a turn finishes (e.g. journaling).

> **Key it on `Stop`, not `SessionEnd`.** `SessionEnd` fires once, when the chat session ends, so a per-turn hook keyed on it runs exactly once instead of every turn.

### Two Modes

| Mode | `replace_response` | Behavior |
|------|-------------------|----------|
| **Side Effects** | `False` (default) | Extended turn runs, original response returned to user |
| **Transform** | `True` | Extended turn's response becomes the final response |

### Side Effects Mode (Default)

Use for actions that should happen invisibly to the user:

```python
async def journal_hook(context: HookContext) -> HookResult:
    """Remind LLM to journal - user sees original response."""
    if context.event == HookEvent.STOP:
        # Extended turn runs for journaling
        # User receives the ORIGINAL response, not the journal acknowledgment
        return HookResult(
            success=True,
            modifications={
                "systemMessage": "Review the turn for learnings worth documenting.",
                # replace_response=False is the default
            },
        )
    return HookResult()
```

**Use cases:** Logging, journaling, notifications, background tasks

### Transform Mode

Use when you want to modify the final response:

```python
async def summarize_hook(context: HookContext) -> HookResult:
    """Summarize long responses - user sees the summary."""
    if context.event == HookEvent.STOP:
        output = context.event_data.get("output", "")
        if len(str(output)) > 1000:
            # Extended turn's response replaces original
            return HookResult(
                success=True,
                modifications={
                    "systemMessage": f"Summarize this response under 500 chars: {output[:500]}",
                    "replaceResponse": True,
                },
            )
    return HookResult()
```

**Use cases:** Summarization, formatting, sanitization, post-processing

### Block-to-continue (Claude-compatible)

A `Stop` command hook can also force another turn the Claude way — exit 2 (or `decision: "block"`) with a `reason`, which is injected as the next prompt. A consecutive-block cap (8) prevents infinite loops; `stop_hook_active` is set on the payload once a continuation is in progress so the hook can detect it.

### How It Works

1. At `Stop`, a hook returns `systemMessage` (or `decision: "block"` + `reason`).
2. The turn extends with that message as a new user prompt, and the LLM acts on it.
3. The user gets the original response if `replace_response=False`, or the extended one if `replace_response=True` (always, for block-to-continue).

### JSON Configuration

```json
{
  "name": "turn-summary",
  "events": ["Stop"],
  "type": "prompt",
  "config": {
    "user_prompt_template": "Summarize the key points from: {{output}}",
    "modifications": {
      "replaceResponse": true
    }
  }
}
```

---

## Environment Variables

Command hooks receive these environment variables automatically:

| Variable | Description |
|----------|-------------|
| `CLAUDE_HOOK_EVENT` | The hook event name (e.g., `PreToolUse`) |
| `CLAUDE_CWD` | Current working directory |
| `CLAUDE_TRANSCRIPT_PATH` | Path to transcript file |
| `CLAUDE_PERMISSION_MODE` | Current permission mode |
| `CLAUDE_PROJECT_DIR` | Best-guess project root directory |
| `CLAUDE_EVENT_DATA` | Full event data as JSON string |
| `CLAUDE_TOOL_NAME` | Tool name (for tool events) |
| `CLAUDE_TOOL_INPUT` | Tool input as JSON string |
| `CLAUDE_PROMPT` | User prompt (for prompt events) |
| `CLAUDE_COMMAND_NAME` | Command token, e.g. `/save` or `>` (for `PreCommand`/`PostCommand`) |
| `CLAUDE_COMMAND_ARGS` | Text after the command token (for `PreCommand`/`PostCommand`) |

The session identifier is available in the stdin JSON payload (`session_id`) but is not exposed as an environment variable.

### Using Environment Variables

```json
{
  "config": {
    "command": "echo 'Tool $CLAUDE_TOOL_NAME called with: $CLAUDE_TOOL_INPUT' >> /tmp/audit.log"
  }
}
```

---

## Defining Hooks Programmatically (Python)

### Scoped to one task: `append_hook_factory`

Registering on `hook_manager` (below) affects every agent in the process. To scope hooks to one `LLMTask`/`LLMChatTask`, use its `append_hook_factory(*factory)` method, where each factory is `Callable[[HookManager], None]`:

```python
def register_my_hooks(hm: HookManager) -> None:
    hm.add_hook(my_hook, events=[HookEvent.SESSION_START])

chat.append_hook_factory(register_my_hooks)
```

The two task classes isolate differently (ADR-0072):

- **`LLMChatTask`** builds a **fresh** `HookManager` per execution and replays every registered factory onto it each time, so one chat session's hooks never leak into the next.
- **`LLMTask`** holds a **persistent** manager. The *first* `append_hook_factory` call swaps the process-wide default for a fresh task-local manager (later calls apply to that same manager) — unless a manager was passed explicitly to the constructor's `hook_manager=` argument, which is never swapped. This keeps per-task hooks from silently mutating global state, at the cost that such a task no longer participates in the global filesystem hook set unless it was explicitly constructed with the global manager.

### Process-wide: `hook_manager` in `zrb_init.py`

```python
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def block_production_writes(context: HookContext) -> HookResult:
    """Block writes to production config files."""
    # `event_data`'s shape for PRE_TOOL_USE is {"tool": name, "args": {...}, "call_id": ...}.
    # `tool` is the display name the agent sees, e.g. "Write" for write_file, not the
    # Python function name.
    if context.event_data.get("tool") == "Write":
        path = context.event_data.get("args", {}).get("path", "")
        if "prod_config" in path:
            return HookResult.block("Cannot modify production config.")
    return HookResult(success=True)

# Register the hook
hook_manager.add_hook(block_production_writes, events=[HookEvent.PRE_TOOL_USE])
```

### Programmatic Hook with Priority

Here `HookConfig` carries only metadata (priority, matchers); the callable is the hook. Its required `type`/`config` fields take an inert placeholder, as `hook_manager` does internally for manually registered hooks:

```python
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.types import HookType

async def critical_security_check(context: HookContext) -> HookResult:
    # ... security check logic ...
    return HookResult(success=True)

hook_manager.add_hook(
    critical_security_check,
    events=[HookEvent.PRE_TOOL_USE],
    config=HookConfig(
        name="critical-security",
        events=[HookEvent.PRE_TOOL_USE],
        type=HookType.COMMAND,
        config=CommandHookConfig(command=""),  # unused: the callable above is the hook
        priority=100,  # Run first
        timeout=5,
    )
)
```

---

## Examples

More JSON hooks are in `examples/llm-hooks/.zrb/hooks.json`. For a simple logging hook, see [Quick Start](#quick-start).

### Example: Block Dangerous Tools

```json
[
  {
    "name": "block-rm-rf",
    "events": ["PreToolUse"],
    "type": "command",
    "priority": 100,
    "matchers": [
      {
        "field": "tool_name",
        "operator": "equals",
        "value": "Shell"
      }
    ],
    "config": {
      "command": "if [[ \"$CLAUDE_TOOL_INPUT\" == *\"rm -rf\"* ]]; then echo '{\"decision\": \"block\", \"reason\": \"Destructive command blocked\"}'; exit 2; fi",
      "shell": true
    }
  }
]
```

---

## HookResult Reference

| HookResult Method | Effect |
|-------------------|--------|
| `HookResult()` | No effect, continue normally |
| `HookResult(success=True, modifications={"systemMessage": msg})` | (Stop) Extend turn, original response returned |
| `HookResult(success=True, modifications={"systemMessage": msg, "replaceResponse": True})` | (Stop) Extend turn, extended response returned |
| `HookResult.block(reason)` | Block execution (exit code 2); on `Stop`, continue the turn with `reason` |
| `HookResult.block(reason, additional_context=...)` | Block with additional context |
| `HookResult(success=True, modifications={"continue": False, "stopReason": "..."})` | Halt the whole run (any event); ends the turn on `UserPromptSubmit`/`Stop` |
| `HookResult(success=True, modifications={"permissionDecision": "allow", ...})` | (PreToolUse) Allow tool execution |
| `HookResult(success=True, modifications={"permissionDecision": "deny", "permissionDecisionReason": "..."})` | (PreToolUse) Deny tool execution with reason |
| `HookResult(success=True, modifications={"permissionDecision": "ask"})` | (PreToolUse) Force the approval prompt; `"defer"` = no opinion |
| `HookResult(success=True, modifications={"updatedInput": {...}})` | (PreToolUse) Rewrite tool arguments |
| `HookResult(success=True, modifications={"command_args": "..."})` | (PreCommand) Rewrite command arguments |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"additionalContext": "..."}})` | (SessionStart/UserPromptSubmit/PreCompact) Inject additional context |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"updatedToolOutput": "..."}})` | (PostToolUse) Replace the tool result |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"decision": {"behavior": "allow"/"deny"}}})` | (PermissionRequest) Auto-resolve permission |

🔖 [Documentation Home](../../README.md) > [LLM](./) > Hooks
