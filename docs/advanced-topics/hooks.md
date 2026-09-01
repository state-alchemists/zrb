🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Hooks

# Zrb Hook System (Claude Code Compatible)

The Zrb Hook System provides a powerful way to intercept and modify the execution of LLM agents. You can execute shell commands, run LLM prompts, or trigger specific scripts at key lifecycle events.

Zrb's hook system is **modeled on Claude Code hooks** and aims for drop-in compatibility: hooks register in the same files, read the same stdin payload and `CLAUDE_*` env vars, and use the same matcher/decision JSON. Most single-hook Claude configurations work unchanged.

It is **not** a 100% reimplementation. Several behaviors diverge — most notably the multi-hook execution model and the `exit 2` feedback channel — and a Claude hook that relies on them will behave differently here. Read [Differences from Claude Code](#differences-from-claude-code) before porting a non-trivial hook.

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
- [Environment Variables](#environment-variables)
- [Defining Hooks Programmatically](#defining-hooks-programmatically-python)
- [Examples](#examples)

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

---

## Differences from Claude Code

Zrb reads Claude's hook config and payload format, so most hooks port over. But the runtime is a separate implementation, and the differences below **change outcomes**, not just cosmetics. If you are porting a Claude hook that relies on any of these, adjust it.

### Behavioral differences (these can change what a hook does)

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

> The `exit 2` reason channel (stderr), `PostToolUse` `additionalContext`, and the `Notification` matcher field (`notification_type`) **were** divergences and are now Claude-compatible — see the [changelog](../changelog.md).

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
| `CFG.HOOKS_DIRS` | Additional colon-separated custom directories |

Hooks Claude Code (and drop-in tools like [peon-ping](https://peonping.com)) register inside `settings.json`/`settings.local.json` are picked up automatically — only the nested `hooks` block is read; other settings keys are ignored.

### Hooks Subsystem Configuration

The hooks subsystem itself is controlled by a small set of `CFG`/env knobs, independent of any individual hook's own `enabled`/`timeout` fields:

| `CFG` field | Env var | Default | Description |
|-------------|---------|---------|--------------|
| `HOOKS_ENABLED` | `ZRB_HOOKS_ENABLED` | `on` | Master on/off switch for the entire hooks subsystem |
| `HOOKS_DIRS` | `ZRB_HOOKS_DIRS` | `""` | Colon-separated additional directories to scan for hook scripts |
| `HOOKS_TIMEOUT` | `ZRB_HOOKS_TIMEOUT` | `30000` | Timeout in milliseconds for hook execution |
| `LLM_HOOKS` | `ZRB_LLM_HOOKS` | `""` | Name allowlist for the hooks zrb dispatches (ADR-0091). Empty = run every registered hook; non-empty restricts dispatch to the named hooks (e.g. `journal-compliance-judge`). Programmatic registration is unchanged — see [LLM Component Collections](../configuration/llm-collections.md) |

Setting `HOOKS_ENABLED` to `off` disables the hooks subsystem entirely, regardless of what is configured in `hooks.json` files. `LLM_HOOKS` is a visibility twin layered on top: with `HOOKS_ENABLED` off, nothing fires even if a hook's name is allowed.

---

## Lifecycle Events

Hooks can attach to these lifecycle events:

| Event | Description | Can Block? |
|-------|-------------|------------|
| `SessionStart` | Chat session begins. `source` is `startup` (fresh history) or `resume` (continued). Can inject `additionalContext` | No |
| `SessionEnd` | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn. Use `Stop` for per-turn work. Matches on `source` | No |
| `UserPromptSubmit` | Before the LLM processes text. Can inject `additionalContext`; can halt the turn (`continue: false`) | **Yes** |
| `PreCommand` | Before a UI command runs (chat TUI) | **Yes** |
| `PostCommand` | After a recognized UI command runs | No |
| `PreToolUse` | Before a tool executes (**every** tool call). `permissionDecision` is `deny` (block), `allow` (auto-approve), `ask` (force the approval prompt), or `defer` (no opinion); can also rewrite args (`updatedInput`) | **Yes** |
| `PostToolUse` | After a tool succeeds. Can block the result (`decision: "block"`) or replace it (`updatedToolOutput`) | **Yes** |
| `PostToolUseFailure` | After a tool raises | No |
| `PermissionRequest` | A tool call reaches an interactive approval prompt (fires only when the user is actually asked — not for auto-approved/YOLO/policy-allowed calls). Can auto-resolve via `decision.behavior` (`allow`/`deny`) | **Yes** |
| `Notification` | System notifications. `AskUserQuestion` fires one with `notification_type='elicitation_dialog'` when it blocks for an answer | No |
| `Stop` | A turn finishes and control returns to the user. The per-turn "done" signal. Can **block-to-continue** (`decision: "block"` + `reason`) to force another turn, and carries the `systemMessage` turn-extension (e.g. journaling) | **Yes** |
| `StopFailure` | A turn ends on an unrecoverable API error. Observe-only; matches on `error_type` (`rate_limit`, `overloaded`, `server_error`, `context_length`, `authentication_failed`, `invalid_request`, `model_not_found`, `unknown`) | No |
| `PreCompact` | Before history summarization (`trigger: "auto"`). Can inject `additionalContext`; can **block** compaction (`decision: "block"` / exit 2) to skip summarization for the turn | **Yes** |
| `PostCompact` | After history summarization completes (`trigger: "auto"`). Can inject `additionalContext` | No |
| `SubagentStart` | A sub-agent (delegation) begins. Matches on `agent_type` (the delegated agent's name); also carries `agent_id` | No |
| `SubagentStop` | A sub-agent finishes (success or error). Same `agent_type`/`agent_id` as its `SubagentStart` | No |

`PreCommand` / `PostCommand` fire in the interactive chat TUI when the user runs a built-in or custom command (any configured token — `/save`, `/exit`, a custom `>` redirect, etc.; not just `/`-prefixed). The command name and arguments are exposed as `command_name` / `command_args` (see [Environment Variables](#environment-variables)). A blocking `PreCommand` hook cancels the command before it runs; plain chat messages do **not** fire these events.

A `PreCommand` hook can also **rewrite the command's argument** by returning a `command_args` value — the command token is preserved, the argument is swapped. For example, redirect a model switch:

```python
async def downgrade_opus(ctx):
    if ctx.command_name == "/model" and "opus" in (ctx.command_args or "").lower():
        return HookResult(modifications={"command_args": "sonnet"})  # opus -> sonnet
    return HookResult()
```

A shell command hook does the same by printing JSON on stdout: `echo '{"command_args": "sonnet"}'`. The highest-priority hook that sets `command_args` wins.

---

## Hook Configuration

Hooks are defined in JSON or YAML format. Each hook has the following structure:

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
| `async` | boolean | No | Run fire-and-forget in the background, without blocking the event (default: false). Only `command` hooks honor this — `prompt`/`agent` hooks always run synchronously, since their results (e.g. modifications) often need to feed back into the blocking flow. |
| `enabled` | boolean | No | Hook is active (default: true) |
| `timeout` | number | No | Timeout in seconds. Default is type-dependent: `command` hooks default to 600s, `prompt` hooks default to 30s, and `agent` hooks default to 60s |
| `env` | object | No | Environment variables to inject |
| `priority` | number | No | Execution priority (higher = earlier) |

---

## Hook Types

### 1. Command Hooks

Execute shell commands or scripts.

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

**Command Hook Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Shell command to execute |
| `shell` | boolean | Use shell interpreter (default: true) |
| `working_dir` | string | Working directory (optional) |

> The example above omits an explicit `timeout`, so it runs at the `command` hook default of 600 seconds, not 30.

**Input: env vars _and_ stdin.** A command hook receives its event two ways, so it works with both styles of Claude-Code hook. The `CLAUDE_*` [environment variables](#environment-variables) are set, and the full Claude-Code event payload is also written to the command's **stdin** as JSON (`hook_event_name`, `session_id`, `cwd`, …). Tool events carry `tool_name` and `tool_input` (and `tool_response` on `PostToolUse`), so both stdin reads and `tool_name` matchers work. Stdin-driven hooks read it like:

```bash
event=$(cat)                                    # read the JSON payload from stdin
name=$(echo "$event" | jq -r .hook_event_name)  # e.g. "Stop"
```

**Output: stdout.** A command hook controls behavior by printing a JSON object on stdout (`{"decision": ...}`, `{"permissionDecision": ...}`, etc.). For `SessionStart` and `UserPromptSubmit`, **plain (non-JSON) stdout is injected as `additionalContext`** — so a simple `echo "Current branch: $(git branch --show-current)"` hook adds that line to the model's context, matching Claude Code.

### 2. Prompt Hooks

Run LLM prompts with context for analysis or decision-making.

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

**Template Variables:**

Available in `user_prompt_template`:

- `{{prompt}}` - User's input text
- `{{session_id}}` - Session identifier
- `{{metadata}}` - Context metadata
- `{{tool_name}}` - Tool name (for tool events)
- `{{tool_input}}` - Tool input JSON (for tool events)

### 3. Agent Hooks

Run agents with tools for complex analysis.

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
| `tools` | array | Tool names, Claude-compatible aliases honored (`"Bash"` → `Shell`) — resolved against zrb's own tool set, including config-gated tools like the journal ones (`LogActivity`, `WriteJournalNote`, `SearchJournal`) that only exist when their feature is enabled. Each resolved tool gets the same error containment as the main agent's tools: a `[SYSTEM SUGGESTION]` error comes back as a tool result the hook's own model can react to, not an exception that aborts the hook run |
| `model` | string | Model to use (e.g., `openai:gpt-4o`); omit to fall back to `ZRB_LLM_MODEL` |

If every name in `tools` fails to resolve — most commonly because the feature they belong to is off (e.g. the journal tools while `LLM_JOURNAL_ENABLED` is `false`) — the hook skips its LLM call entirely rather than run an agent that has nothing it can do. A hook that genuinely wants no tools just leaves `tools` empty and is unaffected.

This `agent-review` snippet is a runnable worked example, not just documentation: see `security-review-agent-example` in `examples/llm-hooks/.zrb/hooks.json` (shipped `enabled: false` — an agent hook on `PreToolUse` adds a model round-trip to every matching tool call).

### Built-in example: the journal-compliance judge

A small dedicated sub-agent that looks at a completed turn and decides — on its own, using `LogActivity`/`WriteJournalNote`'s own documented criteria — whether the turn needs a journal entry, and writes one itself if so. It only spends an LLM call on turns that actually changed a file, via the `event_data.wrote_files` matcher (computed in plain Python at the `Stop` call site, no model involved), and `async: true` keeps it from blocking the user's response while it decides.

**This one ships built-in and active** (`llm/hook/journal_compliance.py`, registered as a hook factory on the default `hook_manager` singleton) — it has no `enabled` flag of its own. It is tied entirely to `LLM_JOURNAL_ENABLED` (default on): while journaling is enabled, this hook runs; while it's off, `tools` resolves to nothing (the journal tools aren't registered either) and the hook skips its LLM call as a no-op. There is deliberately no separate switch to remember. By default it runs on `default_llm_config.small_model` — set `ZRB_LLM_SMALL_MODEL` if you want it on something other than your main model, since an unset small model falls back to the main one, which defeats the point of a cheap judge.

Its system prompt lives at `llm/prompt/markdown/journal_compliance.md`, not inline in Python, so it goes through the normal prompt-override chain: drop a `journal_compliance.md` under your project's `LLM_PROMPT_DIR` (or set `ZRB_LLM_PROMPT_JOURNAL_COMPLIANCE`) to change what the judge looks for, without forking the hook itself.

The shape of its `HookConfig`, for reference (built in Python by `build_journal_compliance_hook_config()`, not JSON):

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

Duplicating this exact hook in `examples/llm-hooks/.zrb/hooks.json` would teach nothing new, so the shipped example (`security-review-agent-example`, shipped `enabled: false`) demonstrates a different agent-hook use case instead — a `PreToolUse` review agent rather than a `Stop` one. See [llm-chat-lifecycle.md](./llm-chat-lifecycle.md#tracing-an-agent-type-hook-journal-compliance) for how this built-in one is actually wired end-to-end (the registration seam, the `HookType.AGENT` builder, and where the LLM call happens).

---

## Matchers

Matchers allow hooks to run only when specific conditions are met. Use them to filter when a hook executes.

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

Fields can use dot notation to access nested context:

```json
{
  "matchers": [
    {
      "field": "tool_name",
      "operator": "equals",
      "value": "run_shell_command"
    }
  ]
}
```

### Tool names (Claude-compatible)

Zrb's built-in tools expose Claude-compatible names (`Read`, `Write`, `Edit`, `Grep`, `Glob`, `LS`, `Shell`, `WebFetch`, `WebSearch`, `TodoWrite`, `TodoRead`, …), so a Claude hook matcher keyed on a tool name — e.g. `{"matcher": "Edit"}` or a `tool_name` matcher — works as-is. A few zrb tools keep a name that differs from Claude's; for those, the Claude name is accepted as an **alias** on `tool_name` matchers:

| zrb tool | also matches |
|----------|--------------|
| `Shell` (the default shell tool) | `Bash` |
| `DelegateToAgent`, `DelegateToAgentBackground` | `Task` |

Aliases apply to positive operators (`equals`, `regex`, `contains`, …); a `not_equals` matcher compares against the literal name only, so an exclusion is never silently widened.

**Common Fields:**

| Field | Description |
|-------|-------------|
| `tool_name` | Name of the tool being called |
| `tool_input` | Tool input data |
| `metadata.project` | Project name from metadata |
| `metadata.environment` | Environment (e.g., production) |
| `event_data.file_path` | File path from event data |

### Case Sensitivity

By default, string comparisons are case-sensitive. Set `case_sensitive: false` for case-insensitive matching:

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

Hooks execute in priority order (higher priority first). Use this to ensure critical hooks run before others.

**Priority Order:** Higher numbers execute first.

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

In this example, `security-check` runs before `logging` because it has a higher priority.

**Default Priority:** 0

---

## Blocking Decisions

Hooks can block execution by returning specific outputs.

### Exit Code 2

Return exit code `2` to block:

```bash
#!/bin/bash
echo '{"decision": "block", "reason": "Dangerous operation blocked"}'
exit 2
```

> **Reason channel:** zrb accepts the block reason on **either** stream — an explicit `reason` in a stdout JSON object, or stderr (the Claude convention, e.g. `echo "reason" >&2; exit 2`), or plain stdout text — in that precedence. Claude-style stderr hooks therefore carry their reason correctly.

Exit 2 (and `decision: "block"`) is honored only for the **blocking-capable** events — those marked **Yes** in the [lifecycle table](#lifecycle-events) (`UserPromptSubmit`, `PreCommand`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `Stop`, `PreCompact`). On an observe-only event (e.g. `Notification`, `SessionStart`, `SubagentStop`) a block is ignored and the remaining hooks for that event still run.

### Halting the run (`continue: false`)

Distinct from a per-event block, `continue: false` is an unconditional request to stop all processing. Return it (with an optional `stopReason`) to end the run regardless of event:

```bash
echo '{"continue": false, "stopReason": "Quota exhausted"}'
```

On `UserPromptSubmit` the turn ends before the model runs; on `Stop` it ends the turn, overriding any block-to-continue or `systemMessage` extension.

### JSON Output

Output JSON with `"decision": "block"`:

```json
{
  "decision": "block",
  "reason": "Operation requires manual approval"
}
```

### `PreToolUse` permission decisions

`PreToolUse` hooks control a tool call via `permissionDecision` (top-level or nested under `hookSpecificOutput`):

| `permissionDecision` | Description |
|----------------------|-------------|
| `deny` | Block the call; show `permissionDecisionReason` to the model |
| `allow` | Auto-approve; skip the approval prompt entirely |
| `ask` | Force the interactive approval prompt, overriding any tool-policy/permission ALLOW or YOLO auto-approve (an explicit DENY still wins) |
| `defer` | No opinion — let the normal approval flow decide |

> `ask` forces the prompt only on the deferred-approval path (tools that go through the approval cascade). On the direct execution-time path there is no prompt to show, so `ask` degrades to proceed.

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

`Stop` hooks can extend a turn by returning a system message. This lets hooks trigger additional LLM actions when a turn finishes (e.g. journaling). It fires on **`Stop`**, the per-turn signal — not on `SessionEnd`, which is terminal.

> **Key it on `Stop`, not `SessionEnd`.** `SessionEnd` fires once, when the chat session ends, so a per-turn journaling or summarization hook keyed on it runs exactly once instead of every turn.

### Two Modes

When a `Stop` hook returns a result with a `systemMessage` modification, there are two modes:

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

A `Stop` command hook can also force another turn the Claude way — exit 2 (or `decision: "block"`) with a `reason`. The reason is injected as the next prompt and the agent runs again. A consecutive-block cap (8) prevents infinite loops; `stop_hook_active` is set on the payload once a continuation is in progress so the hook can detect it.

### How It Works

1. Hook returns `systemMessage` (or `decision: "block"` + `reason`) at `Stop`
2. The turn extends with that message as a new user prompt
3. LLM processes the message (e.g., writes journal, summarizes, continues)
4. If `replace_response=False`: Original response returned
5. If `replace_response=True` (and always for block-to-continue): Extended response returned

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

Registering directly on `hook_manager` (below) affects every agent in the process. To scope hooks to one `LLMTask`/`LLMChatTask` instance, use its `append_hook_factory(*factory)` builder method instead, where each factory is `Callable[[HookManager], None]`:

```python
def register_my_hooks(hm: HookManager) -> None:
    hm.register(my_hook, events=[HookEvent.SESSION_START])

chat.append_hook_factory(register_my_hooks)
```

The two task classes isolate differently (ADR-0072):

- **`LLMChatTask`** builds a **fresh** `HookManager` per execution and replays every registered factory onto it each time, so one chat session's hooks never leak into the next.
- **`LLMTask`** holds a **persistent** manager. The *first* `append_hook_factory` call swaps the process-wide default for a fresh task-local manager (later calls apply to that same manager) — unless a manager was passed explicitly to the constructor's `hook_manager=` argument, which is never swapped. This keeps per-task hooks from silently mutating global state, at the cost that such a task no longer participates in the global filesystem hook set unless it was explicitly constructed with the global manager.

For complex logic, you can also define hooks directly in `zrb_init.py`:

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
hook_manager.register(block_production_writes, events=[HookEvent.PRE_TOOL_USE])
```

### Programmatic Hook with Priority

`HookConfig` here is metadata only (priority/matchers) — the hook itself is the
Python callable you already registered, not something built from `config`. Its
`type`/`config` fields are still required by the constructor, so pass an inert
placeholder (mirroring the same pattern `hook_manager` uses internally for
manually-registered hooks with no command):

```python
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.types import HookType

async def critical_security_check(context: HookContext) -> HookResult:
    # ... security check logic ...
    return HookResult(success=True)

hook_manager.register(
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

Example hook configurations are in the `llm-hooks` example:

```bash
# See examples/llm-hooks/.zrb/hooks.json for JSON-based hooks
```

### Example: Simple Logging Hook

```json
[
  {
    "name": "log-session-start",
    "events": ["SessionStart"],
    "type": "command",
    "config": {
      "command": "echo 'Session started at $(date)' >> /tmp/zrb-hooks.log",
      "shell": true
    },
    "priority": 10
  }
]
```

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
        "value": "run_shell_command"
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

## Quick Reference

| Hook Type | Use Case |
|-----------|----------|
| `command` | Run shell scripts, system commands |
| `prompt` | LLM-based analysis, content filtering |
| `agent` | Multi-step analysis with tools |

| Event | When It Fires | Can Block? | Special |
|-------|---------------|------------|---------|
| `SessionStart` | Chat session begins | No | Can inject `additionalContext`; `source` startup/resume |
| `UserPromptSubmit` | Before LLM processes text | Yes | Can inject `additionalContext`; matches on the `prompt` field; `continue:false` halts the turn |
| `PreCommand` | Before command processing | Yes | Blocks the command; rewrite the argument by returning `command_args` |
| `PostCommand` | After command completes | No | `command_handled` field |
| `PreToolUse` | Before every tool execution | Yes | `updatedInput` rewrites args; `permissionDecision` allow/deny/ask/defer + reason |
| `PostToolUse` | After tool success | Yes | `updatedToolOutput` replaces the result |
| `PostToolUseFailure` | After tool failure | No | `error` context field |
| `PermissionRequest` | LLM requests auto-permission | Yes | Resolve via `hookSpecificOutput.decision.behavior` |
| `Notification` | LLM sends notification to UI | No | `message`, `title`, `notification_type` |
| `Stop` | Turn finishes (per-turn signal) | Yes | Block-to-continue; `systemMessage` turn-extension; `replaceResponse`; `continue:false` ends the turn |
| `StopFailure` | Turn ends on an unrecoverable API error | No | observe-only; `error_type` matcher |
| `PreCompact` | Before conversation compact | Yes | Can inject `additionalContext`; can block compaction; `trigger` matcher |
| `PostCompact` | After conversation compact | No | Can inject `additionalContext`; `trigger` matcher |
| `SubagentStart` | A delegated sub-agent begins | No | observe-only; `agent_type`/`agent_id` |
| `SubagentStop` | A delegated sub-agent finishes | No | observe-only; `agent_type`/`agent_id` |
| `SessionEnd` | Chat session ends (terminal, once) | No | `reason` context field; matches on `source` |

| Matcher Operator | Description |
|------------------|-------------|
| `equals` | Exact match |
| `not_equals` | Negated exact match |
| `contains` | Substring match |
| `starts_with` | Prefix match |
| `ends_with` | Suffix match |
| `regex` | Regular expression |
| `glob` | Glob pattern |

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

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Hooks
