🔖 [Documentation Home](../README.md) > [LLM](./) > Hooks

# Zrb Hook System (Claude Code Compatible)

Hooks intercept and modify an LLM agent's run: at key lifecycle events they execute a shell command, an LLM prompt, or a tool-using agent.

The system is **modeled on Claude Code hooks**: the same files, stdin payload, `CLAUDE_*` env vars, and matcher/decision JSON, so most single-hook Claude configurations work unchanged. It is **not** a full reimplementation — the multi-hook execution model in particular differs. Read [Differences from Claude Code](./claude-compatibility.md#differences-from-claude-code) before porting a non-trivial hook.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Hook Locations](#hook-locations)
- [Lifecycle Events](#lifecycle-events)
- [Hook Configuration](#hook-configuration)
- [Hook Types](#hook-types)
- [Built-in Hooks](#built-in-hooks)
- [Matchers](#matchers)
- [Priority System](#priority-system)
- [Blocking Decisions](#blocking-decisions)
- [Extending a Turn (Stop)](#extending-a-turn-with-system-messages-stop)
- [Environment Variables](#environment-variables)
- [Defining Hooks Programmatically](#defining-hooks-programmatically-python)
- [Examples](#examples)
- [HookResult Reference](#hookresult-reference)
- [Differences from Claude Code](./claude-compatibility.md#differences-from-claude-code)

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
      "command": "echo \"Session started at $(date)\" >> /tmp/zrb-hooks.log",
      "shell": true
    }
  }
]
```

More examples are in [Examples](#examples) and `examples/llm-hooks/.zrb/hooks.json`.

---

## Hook Locations

Hooks are discovered automatically in these locations, loaded in this order. Nothing overrides anything — every hook found is registered — and load order only breaks ties between hooks of equal [priority](#priority-system):

| Location | Purpose |
|----------|---------|
| Plugin dirs: `hooks.json` and `hooks/` | Under each `ZRB_LLM_PLUGIN_DIRS` entry (the bundled `llm_plugin` is checked too, but ships no hooks) |
| `~/.claude/hooks.json`, `~/.claude/hooks/` | Claude Code compatibility, user level |
| `~/.claude/settings.json`, `~/.claude/settings.local.json` | Claude Code compatibility — the nested `hooks` block |
| `~/.zrb/hooks.json`, `~/.zrb/hooks/` | User-level hooks |
| The same six locations in every directory from the filesystem root down to the current directory | Project-specific hooks (`./.claude/...`, `./.zrb/hooks.json`, `./.zrb/hooks/`) |
| `ZRB_HOOKS_DIRS` | Additional colon-separated (semicolon on Windows) custom directories |

A directory location is scanned for `.json`, `.yaml`/`.yml`, and `*.hook.py` files. A `*.hook.py` module defines `register(manager)` (or `register_hooks(manager)`), which is called with the `HookManager` so it can `manager.add_hook(...)` Python hooks — see `examples/llm-hooks/.zrb/hooks/custom_hook.hook.py` for the shape.

Hooks Claude Code (and drop-in tools like peon-ping) register inside `settings.json`/`settings.local.json` are picked up automatically — only the nested `hooks` block is read; other settings keys are ignored. To hear replies and approval prompts, zrb's own [speech](voice-camera.md#speech) reads them aloud without an external tool.

### Hooks Subsystem Configuration

Five `CFG`/env knobs control the subsystem as a whole, independent of each hook's own `enabled`/`timeout` fields: the `HOOKS_ENABLED` master switch, extra `HOOKS_DIRS`, the default `HOOKS_TIMEOUT`, the TUI's `HOOKS_EXIT_TIMEOUT`, and the `LLM_HOOKS` name allowlist. Their env names and defaults are in [LLM Configuration → LLM Hooks Configuration](../configuration/llm-config.md#11-llm-hooks-configuration).

---

## Lifecycle Events

| Event | When it fires / what it can do | Can Block? |
|-------|-------------------------------|------------|
| `SessionStart` | Chat session begins. `source` is `startup` (fresh history) or `resume` (continued). Can inject `additionalContext` | No |
| `SessionEnd` | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn; use `Stop` for per-turn work. Matches on `source` (always `other`); `event_data.reason` is `exit` | No |
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
| `async` | boolean | No | Fire-and-forget in the background without blocking the event (default: false). `command` and `agent` hooks honor it — a background hook cannot block or return modifications; `prompt` hooks always run synchronously |
| `enabled` | boolean | No | Hook is active (default: true) |
| `timeout` | number | No | Seconds; a synchronous hook past it is cancelled (a `command` hook's process killed) and waited for up to 5 seconds. A hook still running when the chat exits — a Stop fired by Ctrl+C — gets up to `ZRB_HOOKS_EXIT_TIMEOUT` (10000 ms) more before it is cancelled. Default: `command` 600s, `prompt` 30s, `agent` 60s in zrb's own hook files; a hook loaded from a Claude-format `settings.json` without a `timeout` gets `ZRB_HOOKS_TIMEOUT` (30000 ms) instead |
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
| `shell` | boolean | Accepted for compatibility (default: true); the command always runs through the shell |
| `working_dir` | string | Working directory (optional; defaults to the session's working directory) |

**Input: env vars _and_ stdin.** Both Claude-Code hook styles work: the `CLAUDE_*` [environment variables](#environment-variables) are set, and the Claude-shaped payload is written to **stdin** as JSON (`hook_event_name`, `session_id`, `cwd`, …; tool events and `PermissionRequest` add `tool_name` and `tool_input`, `PostToolUse` adds `tool_response`, and `Stop` adds `last_assistant_message`, the turn's response text):

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
    "system_prompt": "You are a safety reviewer. If the prompt is harmful, reply only with {\"decision\": \"block\", \"reason\": \"<why>\"}; otherwise reply only with {}.",
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
| `model` | string | Model to use (e.g., `openai:gpt-4o-mini`); omit to use the current run's model, else `ZRB_LLM_MODEL` |
| `temperature` | number | Accepted (default: 0.0) but not currently passed to the model |

**Template variables** in `user_prompt_template`: any string, number, or boolean field of the hook context, as `{{field}}`. The useful ones:

- `{{prompt}}` - User's input text (`UserPromptSubmit`)
- `{{session_id}}`, `{{cwd}}`, `{{hook_event_name}}`
- `{{tool_name}}` - Tool name (for tool events)
- `{{last_assistant_message}}` - The turn's response text (`Stop`)
- `{{command_name}}` / `{{command_args}}` (`PreCommand`/`PostCommand`)

Dict fields such as `tool_input` and `metadata` are **not** substituted; the placeholder stays as written.

**Output:** the hook's effect comes from the model's reply. When the reply is a JSON object, it is read as the hook's decision (`{"decision": "block", "reason": "..."}`, `{"systemMessage": "..."}`, …), exactly like a command hook's stdout; any other reply has no effect.

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
| `model` | string | Model to use (e.g., `openai:gpt-4o`); omit to use the current run's model, else `ZRB_LLM_MODEL` |

The agent's user turn is the event payload: for `Stop`, the turn's transcript; otherwise the event data as text. Its reply is read like a prompt hook's — a JSON object is the hook's decision, anything else has no effect.

If every name in `tools` fails to resolve — usually because their feature is off (e.g. journal tools while `LLM_JOURNAL_ENABLED` is `false`) — the hook skips its LLM call. A hook that wants no tools leaves `tools` empty and is unaffected.

A runnable version of this snippet is `security-review-agent-example` in `examples/llm-hooks/.zrb/hooks.json`, shipped `enabled: false` because an agent hook on `PreToolUse` adds a model round-trip to every matching tool call.

---

## Built-in Hooks

Two hooks ship with zrb. Both are registered in Python on every chat session, so they appear in no `hooks.json`. Their prompts are ordinary prompt files (`journal_compliance`, `self_review`), overridable like any other — a file under `ZRB_LLM_PROMPT_DIR`, or a variable such as `ZRB_LLM_PROMPT_JOURNAL_COMPLIANCE`.

### The journal-compliance judge

After a turn that changed a file or seemed to state a preference, a small sub-agent decides whether the turn deserves a journal entry and writes one if so. It runs asynchronously, so it never delays the response.

- **On** whenever the journal is on (`ZRB_LLM_JOURNAL_ENABLED`, default on); it has no switch of its own (its hook name is `journal-compliance-judge`).
- **Model:** the small model (`ZRB_LLM_SMALL_MODEL`, or a `/model small …` override). Set one — an unset small model falls back to your main model, which defeats the point of a cheap judge.
- **Tools:** `LogActivity`, `WriteJournalNote`, `SearchJournal`; timeout 60 seconds.

How an agent-type hook like this one is wired internally is traced in [LLM Chat Request Lifecycle](./llm-chat-lifecycle.md#tracing-an-agent-type-hook-journal-compliance) (a contributor page).

### The self-review gate

Off by default; `ZRB_LLM_SELF_REVIEW_ENABLED=on` turns it on. On a turn that changed files, a reviewer agent with a fresh context reads exactly what the turn changed and the code around it (read-only), then ends its report with `Request changes` or `LGTM`.

- **What it reviews:** the difference between a snapshot taken when the turn started and one taken at Stop. That covers edits made through `Shell`, changes committed mid-turn, and every git repository under the working directory (nested clones, submodules and worktrees included), but not your own earlier uncommitted work. A sub-agent's changes are part of its parent turn's review.
- **What happens on `Request changes`:** the Stop is blocked, and the findings become the agent's next prompt: check each against the code, fix the real ones, say why any is not a defect, and restate the final answer. Anything else (`LGTM`, an unclear verdict, a failed review) lets the turn end.
- **Privacy:** snapshots go to a private, owner-only temporary store deleted when the turn ends — never into your `.git/objects` — so untracked secrets such as `.env` are not copied into a repository. The reviewer's model does receive the turn's diff.
- **Limits:** a directory holding more than `ZRB_LLM_SNAPSHOT_LOOSE_MAX_FILES` files or `ZRB_LLM_SNAPSHOT_LOOSE_MAX_MB` MB outside any repository cannot be snapshotted; the reviewer then gets the list of paths the turn touched, without a diff, and zrb says so once per session.

| Env var | Default | Effect |
|---------|---------|--------|
| `ZRB_LLM_SELF_REVIEW_MAX_ROUNDS` | `2` | Caps consecutive blocking reviews; a review that lets the turn end resets the count |
| `ZRB_LLM_SELF_REVIEW_TIMEOUT` | `240` (seconds) | Bounds each review; on expiry the reviewer is cancelled, model request included, and the turn ends unreviewed |
| `ZRB_LLM_SELF_REVIEW_MAX_TRACKED_TURNS` | `64` | Turns whose round count is kept at once; the oldest past it are dropped |
| `ZRB_LLM_SELF_REVIEW_MODEL` | empty | The reviewer's model (empty uses the run's own). A different model shares fewer blind spots |

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

`field` is any hook-context field, with dot notation into nested values (e.g. `tool_input.path`). A field that does not exist resolves to nothing, so the matcher fails:

| Field | Description |
|-------|-------------|
| `tool_name` | Name of the tool being called |
| `tool_input.<arg>` | One tool argument, e.g. `tool_input.path` for `Read`/`Write`/`Edit` |
| `prompt`, `source`, `trigger`, `notification_type`, `agent_type`, `error_type`, `command_name` | The per-event fields named in the [lifecycle table](#lifecycle-events) |
| `metadata.<key>` | A key of the `metadata` dict — empty in zrb's own runs; set only when you call `execute_hooks(metadata=...)` yourself |
| `event_data.<key>` | A key of the raw event payload, e.g. `event_data.wrote_files` on `Stop` |

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
      "value": "Write"
    },
    {
      "field": "tool_input.path",
      "operator": "starts_with",
      "value": "/etc/"
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

`ask` only forces a prompt for tools that go through the approval cascade; elsewhere it degrades to proceed (see [Differences from Claude Code](./claude-compatibility.md#differences-from-claude-code), row 5).

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

| Mode | `replaceResponse` | Behavior |
|------|-------------------|----------|
| **Side Effects** | `False` (default) | Extended turn runs, original response returned to user |
| **Transform** | `True` | Extended turn's response becomes the final response |

### Side Effects Mode (Default)

Use for actions that should happen invisibly to the user:

```python
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

_extended_turns: set[str] = set()


async def journal_hook(context: HookContext) -> HookResult:
    """Remind LLM to journal - user sees original response."""
    if context.event != HookEvent.STOP:
        return HookResult()
    # Stop fires again when the extended turn ends; extend only once per turn.
    turn_id = context.event_data.get("turn_id")
    if turn_id in _extended_turns:
        return HookResult()
    _extended_turns.add(turn_id)
    # User receives the ORIGINAL response, not the journal acknowledgment
    return HookResult(
        success=True,
        modifications={
            "systemMessage": "Review the turn for learnings worth documenting.",
            # "replaceResponse": False is the default
        },
    )
```

`Stop` fires again when the extended turn finishes, so a hook that returns a `systemMessage` every time re-extends the turn until the cap of 8 consecutive extensions. `event_data["turn_id"]` stays the same across one turn's extensions, which makes it the guard.

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
3. The user gets the original response if `replaceResponse` is false (the default), or the extended one if it is true (always, for block-to-continue).

### JSON Configuration

A JSON hook returns the same keys: a command hook prints `{"systemMessage": "...", "replaceResponse": true}` on stdout, and a prompt or agent hook's model replies with that object. A JSON hook has no per-turn state to guard with, though, so it re-extends every `Stop` up to the cap. For a JSON hook, block-to-continue is the better fit — `stop_hook_active` in the stdin payload tells it a continuation is already running:

```json
{
  "name": "turn-summary",
  "events": ["Stop"],
  "type": "command",
  "config": {
    "command": "jq -e '.stop_hook_active' >/dev/null || { echo 'Summarize your last answer in three bullet points.' >&2; exit 2; }"
  }
}
```

---

## Environment Variables

Command hooks receive these environment variables automatically:

| Variable | Description |
|----------|-------------|
| `CLAUDE_HOOK_EVENT`, `CLAUDE_HOOK_EVENT_NAME` | The hook event name (e.g., `PreToolUse`) |
| `CLAUDE_CWD` | Current working directory |
| `CLAUDE_TRANSCRIPT_PATH` | Path to transcript file |
| `CLAUDE_PERMISSION_MODE` | Current permission mode |
| `CLAUDE_PROJECT_DIR` | Best-guess project root directory (the session's working directory) |
| `CLAUDE_PLUGIN_ROOT` | The plugin directory the hook was loaded from; empty for non-plugin hooks |
| `CLAUDE_EVENT_DATA` | Full event data as JSON string. Dropped when over 16 KiB, which a `Stop` payload (it carries the history) usually is; read `last_assistant_message` instead |
| `CLAUDE_LAST_ASSISTANT_MESSAGE` | The turn's response text (for `Stop`) |
| `CLAUDE_TOOL_NAME` | Tool name (for tool events) |
| `CLAUDE_TOOL_INPUT` | Tool input as JSON string |
| `CLAUDE_PROMPT` | User prompt (for prompt events) |
| `CLAUDE_COMMAND_NAME` | Command token, e.g. `/save` or `>` (for `PreCommand`/`PostCommand`) |
| `CLAUDE_COMMAND_ARGS` | Text after the command token (for `PreCommand`/`PostCommand`) |
| `CLAUDE_COMMAND_HANDLED` | Whether a handler consumed the command (for `PostCommand`) |
| `CLAUDE_MESSAGE`, `CLAUDE_TITLE`, `CLAUDE_NOTIFICATION_TYPE` | Notification fields (for `Notification`) |
| `CLAUDE_AGENT_ID` | Sub-agent id (for `SubagentStart`/`SubagentStop`) |

Every value is capped at 16 KiB; a longer one is left unset rather than truncated. Event-specific variables are set only when the event carries that field.

The session identifier is available in the stdin JSON payload (`session_id`) but is not exposed as an environment variable.

### Using Environment Variables

```json
{
  "config": {
    "command": "echo \"Tool $CLAUDE_TOOL_NAME called with: $CLAUDE_TOOL_INPUT\" >> /tmp/audit.log"
  }
}
```

---

## Defining Hooks Programmatically (Python)

### Scoped to one task: `append_hook_factory`

To attach hooks to one `LLMTask`/`LLMChatTask`, use its `append_hook_factory(*factory)` method, where each factory is `Callable[[HookManager], None]`. For the built-in `zrb llm chat`, that task is `llm_chat`:

```python
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


async def my_hook(context: HookContext) -> HookResult:
    print(f"Session {context.source}")
    return HookResult()


def register_my_hooks(hm: HookManager) -> None:
    hm.add_hook(my_hook, events=[HookEvent.SESSION_START])


llm_chat.append_hook_factory(register_my_hooks)
```

The two task classes isolate differently:

- **`LLMChatTask`** builds a **fresh** `HookManager` per execution and replays every registered factory onto it each time, so one chat session's hooks never leak into the next.
- **`LLMTask`** holds a **persistent** manager. The *first* `append_hook_factory` call swaps the process-wide default for a fresh task-local manager (later calls apply to that same manager) — unless a different manager was passed to the constructor's `hook_manager=` argument, which is never swapped. This keeps per-task hooks from silently mutating global state. The task-local manager still loads the filesystem hooks (every manager scans the [hook locations](#hook-locations)), but no longer sees hooks registered in code on the global `hook_manager`.

### Shared: the global `hook_manager`

The `hook_manager` singleton is the default manager of every `LLMTask` that has no task-local one. It is **not** used by `LLMChatTask` — `zrb llm chat` included — which builds a fresh manager per session unless given `hook_manager=`. To reach every chat session and task alike, put the hook in a `*.hook.py` file under a [hook location](#hook-locations), since every manager loads those, or in a skill's frontmatter `hooks:` block, which every manager replays. A hook registered in code on the singleton (`hook_manager.add_hook(...)`) reaches the `LLMTask` runs that use it, and no chat session.

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
      "command": "case \"$CLAUDE_TOOL_INPUT\" in *'rm -rf'*) echo '{\"decision\": \"block\", \"reason\": \"Destructive command blocked\"}'; exit 2;; esac",
      "shell": true
    }
  }
]
```

Commands run under `/bin/sh`, which is often not bash, so stick to POSIX syntax (`case`, `[ ]`) rather than `[[ ]]`.

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

---

🔖 [Documentation Home](../README.md) > [LLM](./) > Hooks
