🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Hooks

# Zrb Hook System (Claude Code Compatible)

The Zrb Hook System provides a powerful way to intercept and modify the execution of LLM agents. You can execute shell commands, run LLM prompts, or trigger specific scripts at key lifecycle events.

Zrb's hook system is **100% compatible with Claude Code hooks**.

---

## Table of Contents

- [Quick Start](#quick-start)
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

## Hook Locations

Hooks are discovered automatically in these locations (in order of precedence):

| Location | Purpose |
|----------|---------|
| `~/.zrb/hooks.json` | User-level hooks (single file) |
| `~/.zrb/hooks/*.json` | User-level hooks directory |
| `./.zrb/hooks.json` | Project-specific hooks (single file) |
| `./.zrb/hooks/*.json` | Project-specific hooks directory |
| `~/.claude/hooks.json` | Claude Code compatibility (single file) |
| `~/.claude/hooks/*.json` | Claude Code compatibility (directory) |
| `~/.claude/settings.json` | Claude Code compatibility — the nested `hooks` block |
| `~/.claude/settings.local.json` | Claude Code compatibility — the nested `hooks` block |
| `./.claude/hooks.json` | Claude Code compatibility, project (single file) |
| `./.claude/hooks/*.json` | Claude Code compatibility, project (directory) |
| `./.claude/settings.json` | Claude Code compatibility, project — the nested `hooks` block |
| `./.claude/settings.local.json` | Claude Code compatibility, project — the nested `hooks` block |
| Plugin `hooks/` dirs | Inside `ZRB_LLM_PLUGIN_DIRS` entries |

Hooks Claude Code (and drop-in tools like [peon-ping](https://peonping.com)) register
inside `settings.json`/`settings.local.json` are picked up automatically — only the
nested `hooks` block is read; other settings keys are ignored.

---

## Lifecycle Events

Hooks can attach to these lifecycle events:

| Event | Description | Can Block? |
|-------|-------------|------------|
| `SessionStart` | Chat session begins. `source` is `startup` (fresh history) or `resume` (continued). Can inject `additionalContext` | No |
| `SessionEnd` | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn. Use `Stop` for per-turn work | No |
| `UserPromptSubmit` | Before the LLM processes text. Can inject `additionalContext` | **Yes** |
| `PreCommand` | Before a UI command runs (chat TUI) | **Yes** |
| `PostCommand` | After a recognized UI command runs | No |
| `PreToolUse` | Before a tool executes (**every** tool call). Can deny (`permissionDecision: "deny"`), auto-allow, or rewrite args (`updatedInput`) | **Yes** |
| `PostToolUse` | After a tool succeeds. Can block the result (`decision: "block"`) or replace it (`updatedToolOutput`) | **Yes** |
| `PostToolUseFailure` | After a tool raises | No |
| `PermissionRequest` | A tool call reaches an interactive approval prompt (fires only when the user is actually asked — not for auto-approved/YOLO/policy-allowed calls). Can auto-resolve via `decision.behavior` (`allow`/`deny`) | No |
| `Notification` | System notifications. `AskUserQuestion` fires one with `notification_type='elicitation_dialog'` when it blocks for an answer | No |
| `Stop` | A turn finishes and control returns to the user. The per-turn "done" signal. Can **block-to-continue** (`decision: "block"` + `reason`) to force another turn, and carries the `systemMessage` turn-extension (e.g. journaling) | **Yes** |
| `PreCompact` | Before history summarization (`trigger: "auto"`). Can inject `additionalContext` | No |

`PreCommand` / `PostCommand` fire in the interactive chat TUI when the user
runs a built-in or custom command (any configured token — `/save`, `/exit`, a
custom `>` redirect, etc.; not just `/`-prefixed). The command name and
arguments are exposed as `command_name` / `command_args` (see [Environment
Variables](#environment-variables)). A blocking `PreCommand` hook cancels the
command before it runs; plain chat messages do **not** fire these events.

A `PreCommand` hook can also **rewrite the command's argument** by returning a
`command_args` value — the command token is preserved, the argument is
swapped. For example, redirect a model switch:

```python
async def downgrade_opus(ctx):
    if ctx.command_name == "/model" and "opus" in (ctx.command_args or "").lower():
        return HookResult(modifications={"command_args": "sonnet"})  # opus -> sonnet
    return HookResult()
```

A shell command hook does the same by printing JSON on stdout:
`echo '{"command_args": "sonnet"}'`. The highest-priority hook that sets
`command_args` wins.

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
| `async` | boolean | No | Run asynchronously (default: false) |
| `enabled` | boolean | No | Hook is active (default: true) |
| `timeout` | number | No | Timeout in seconds (default: 30) |
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

**Input: env vars _and_ stdin.** A command hook receives its event two ways, so it
works with both styles of Claude-Code hook. The `CLAUDE_*` [environment
variables](#environment-variables) are set, and the full Claude-Code event payload
is also written to the command's **stdin** as JSON (`hook_event_name`, `session_id`,
`cwd`, `tool_name`, …). Stdin-driven hooks read it like:

```bash
event=$(cat)                                    # read the JSON payload from stdin
name=$(echo "$event" | jq -r .hook_event_name)  # e.g. "Stop"
```

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
    "tools": ["file_read", "network_check"],
    "model": "openai:gpt-4o"
  }
}
```

**Agent Hook Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `system_prompt` | string | System prompt for the agent |
| `tools` | array | List of tool names available to agent |
| `model` | string | Model to use (e.g., `openai:gpt-4o`) |

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

### JSON Output

Output JSON with `"decision": "block"`:

```json
{
  "decision": "block",
  "reason": "Operation requires manual approval"
}
```

### Blocking Decisions

| Decision | Description |
|----------|-------------|
| `block` | Stop execution, show reason to user |
| `ask` | Prompt user for approval |
| `allow` | Continue execution (implicit) |

### Permission / Approval Hook Example

```json
{
  "name": "require-approval",
  "events": ["PreToolUse"],
  "type": "command",
  "config": {
    "command": "echo '{\"decision\": \"ask\", \"reason\": \"Requires manual approval\"}'"
  }
}
```

This hook triggers before every tool call, asking for user approval. The `block`, `ask`, and `allow` decisions above work with any `PreToolUse` hook.

---

## Extending a Turn with System Messages (Stop)

`Stop` hooks can extend a turn by returning a system message. This lets hooks
trigger additional LLM actions when a turn finishes (e.g. journaling). It fires
on **`Stop`**, the per-turn signal — not on `SessionEnd`, which is terminal.

> **Migrating from `SessionEnd`:** before, this extension and the built-in
> journaling reminder lived on `SessionEnd` (which used to fire per turn). They
> now live on `Stop`. If you wrote a journaling/summarization hook keyed on
> `SessionEnd`, move it to `Stop`. `SessionEnd` now fires once, when the chat
> session ends.

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

A `Stop` command hook can also force another turn the Claude way — exit 2 (or
`decision: "block"`) with a `reason`. The reason is injected as the next prompt
and the agent runs again. A consecutive-block cap (8) prevents infinite loops;
`stop_hook_active` is set on the payload once a continuation is in progress so
the hook can detect it.

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
| `CLAUDE_SESSION_ID` | Unique session identifier |
| `CLAUDE_TOOL_NAME` | Tool name (for tool events) |
| `CLAUDE_TOOL_INPUT` | Tool input as JSON string |
| `CLAUDE_PROMPT` | User prompt (for prompt events) |
| `CLAUDE_COMMAND_NAME` | Command token, e.g. `/save` or `>` (for `PreCommand`/`PostCommand`) |
| `CLAUDE_COMMAND_ARGS` | Text after the command token (for `PreCommand`/`PostCommand`) |
| `CLAUDE_EVENT_DATA` | Full event data as JSON string |
| `CLAUDE_TRANSCRIPT_PATH` | Path to transcript file |
| `CLAUDE_PERMISSION_MODE` | Current permission mode |

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

For complex logic, define hooks directly in `zrb_init.py`:

```python
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def block_production_writes(context: HookContext) -> HookResult:
    """Block writes to production config files."""
    if context.event_data.get("tool") == "write_file":
        path = context.event_data.get("path", "")
        if "prod_config" in path:
            return HookResult.block("Cannot modify production config.")
    return HookResult(success=True)

# Register the hook
hook_manager.register(block_production_writes, events=[HookEvent.PRE_TOOL_USE])
```

### Programmatic Hook with Priority

```python
async def critical_security_check(context: HookContext) -> HookResult:
    # ... security check logic ...
    return HookResult(success=True)

hook_manager.register(
    critical_security_check,
    events=[HookEvent.PRE_TOOL_USE],
    config=HookConfig(
        name="critical-security",
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
# See examples/llm-hooks/.zrb/hooks.yaml for YAML-based hooks
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
| `SessionStart` | Chat session begins | No | Can inject `additionalContext`; `source` startup/resume; `model` |
| `UserPromptSubmit` | Before LLM processes text | Yes | Can inject `additionalContext`; `prompt` field |
| `PreCommand` | Before command processing | No | `command_args` rewriting via `updatedInput` |
| `PostCommand` | After command completes | No | `command_handled` field |
| `PreToolUse` | Before every tool execution | Yes | `updatedInput` rewrites args; `permissionDecision` allow/deny + reason |
| `PostToolUse` | After tool success | Yes | `updatedToolOutput` replaces the result |
| `PostToolUseFailure` | After tool failure | No | `error` context field |
| `PermissionRequest` | LLM requests auto-permission | Yes | Resolve via `hookSpecificOutput.decision.behavior` |
| `Notification` | LLM sends notification to UI | No | `message`, `title`, `notification_type` |
| `Stop` | Turn finishes (per-turn signal) | Yes | Block-to-continue; `systemMessage` turn-extension; `replaceResponse` |
| `PreCompact` | Before conversation compact | No | Can inject `additionalContext`; `trigger` auto/manual |
| `SessionEnd` | Chat session ends (terminal, once) | No | `reason` context field |

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
| `HookResult(success=True, modifications={"permissionDecision": "allow", ...})` | (PreToolUse) Allow tool execution |
| `HookResult(success=True, modifications={"permissionDecision": "deny", "permissionDecisionReason": "..."})` | (PreToolUse) Deny tool execution with reason |
| `HookResult(success=True, modifications={"updatedInput": {...}})` | (PreToolUse) Rewrite tool arguments |
| `HookResult(success=True, modifications={"command_args": "..."})` | (PreCommand) Rewrite command arguments |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"additionalContext": "..."}})` | (SessionStart/UserPromptSubmit/PreCompact) Inject additional context |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"updatedToolOutput": "..."}})` | (PostToolUse) Replace the tool result |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"decision": {"behavior": "allow"/"deny"}}})` | (PermissionRequest) Auto-resolve permission |