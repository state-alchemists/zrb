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
| `~/.claude/hooks.json` | Claude Code compatibility |
| `./.claude/hooks.json` | Claude Code compatibility (project) |

---

## Lifecycle Events

Hooks can attach to these lifecycle events:

| Event | Description | Can Block? |
|-------|-------------|------------|
| `SessionStart` | Session begins | No |
| `SessionEnd` | Session ends | No |
| `UserPromptSubmit` | Before LLM processes text | No |
| `PreToolUse` | Before a tool executes | **Yes** |
| `PostToolUse` | After tool succeeds | No |
| `PostToolUseFailure` | After tool fails | No |
| `PermissionRequest` | When permission is requested | **Yes** |
| `Notification` | System notifications | No |
| `SubagentStart` | When a subagent starts | No |
| `SubagentStop` | When a subagent stops | No |
| `Stop` | When execution stops | No |
| `TeammateIdle` | When a teammate becomes idle | No |
| `TaskCompleted` | When a task completes | No |
| `PreCompact` | Before history summarization | No |

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

### Permission Hook Example

```json
{
  "name": "require-approval",
  "events": ["PermissionRequest"],
  "type": "command",
  "config": {
    "command": "echo '{\"decision\": \"ask\", \"reason\": \"Requires manual approval\"}'"
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
            return HookResult(
                success=False,
                blocked=True,
                reason="Cannot modify production config."
            )
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

Example hook configurations are available in [examples/hooks/](../../examples/hooks/):

| File | Description |
|------|-------------|
| `basic-command-hook.json` | Simple command hooks for logging and notifications |
| `security-hook.json` | Security checks and approval workflows |
| `prompt-review-hook.json` | LLM-based prompt safety review |
| `logging-hook.json` | Audit logging and analytics |

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

| Event | When It Fires | Can Block? |
|-------|---------------|------------|
| `PreToolUse` | Before tool execution | Yes |
| `PermissionRequest` | During permission request | Yes |
| `PostToolUse` | After tool success | No |
| `PostToolUseFailure` | After tool failure | No |
| `SessionStart/End` | Session lifecycle | No |

| Matcher Operator | Description |
|------------------|-------------|
| `equals` | Exact match |
| `contains` | Substring match |
| `regex` | Regular expression |
| `glob` | Glob pattern |