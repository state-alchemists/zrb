🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Hook System

# Zrb Hook System (Claude Code Compatible)

The Zrb Hook System provides a powerful way to intercept and modify the execution of LLM agents. You can execute shell commands, run LLM prompts, or trigger specific scripts at key lifecycle events.

Zrb's hook system is **100% compatible with Claude Code hooks**.

---

## Table of Contents

- [Lifecycle Events](#1-lifecycle-events)
- [Configuration via JSON](#2-configuration-via-json)
- [Defining Hooks Programmatically](#3-defining-hooks-programmatically-python)
- [Environment Variables](#4-environment-variables)
- [Quick Reference](#quick-reference)

---

## 1. Lifecycle Events

Hooks can attach to the following agent events:

| Event | Description | Can Block? |
|-------|-------------|------------|
| `SessionStart` | Session begins | No |
| `SessionEnd` | Session ends | No |
| `UserPromptSubmit` | Before LLM processes text | No |
| `PreToolUse` | Before a tool executes | **Yes** |
| `PostToolUse` | After tool succeeds | No |
| `PostToolUseFailure` | After tool fails | No |
| `PreCompact` | Before history summarization | No |

---

## 2. Configuration via JSON

Hooks are defined declaratively in JSON/YAML. Zrb discovers them automatically in:

| Location | Purpose |
|----------|---------|
| `~/.zrb/hooks.json` | User-level hooks |
| `~/.zrb/hooks/*.json` | User-level hooks directory |
| `./.zrb/hooks.json` | Project-specific hooks |
| `~/.claude/hooks.json` | Claude compatibility |

### Example 1: Simple Command Hook

Log every time a session starts.

```json
[
  {
    "name": "session-logger",
    "events": ["SessionStart"],
    "type": "command",
    "config": {
      "command": "echo 'Started session $CLAUDE_SESSION_ID at $(date)' >> session.log",
      "shell": true
    }
  }
]
```

### Example 2: Blocking Dangerous Tools (Security Hook)

Prevent the LLM from executing destructive bash commands by intercepting `PreToolUse`. Hooks that return exit code `2` block the execution.

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

> 💡 **Tip:** The `matchers` array ensures the hook only runs when the tool being called is `run_shell_command`.

### Example 3: Prompt-based Hook

Use an LLM to review user prompts before execution.

```json
[
  {
    "name": "safety-review",
    "events": ["UserPromptSubmit"],
    "type": "prompt",
    "config": {
      "user_prompt_template": "Review this prompt for safety: {{prompt}}",
      "system_prompt": "You are a safety filter.",
      "model": "openai:gpt-4o-mini"
    }
  }
]
```

---

## 3. Defining Hooks Programmatically (Python)

If JSON isn't enough, you can define hooks directly in your `zrb_init.py` using Python.

```python
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def block_production_writes(context: HookContext) -> HookResult:
    # Check context event data
    if context.event_data.get("tool") == "write_file":
        path = context.event_data.get("path", "")
        if "prod_config" in path:
            # Block the tool execution!
            return HookResult(
                success=False, 
                blocked=True, 
                reason="Cannot modify production config."
            )
            
    return HookResult(success=True)

# Register the hook to the event
hook_manager.register(block_production_writes, events=[HookEvent.PRE_TOOL_USE])
```

---

## 4. Environment Variables

Command hooks receive a rich set of environment variables injected automatically:

| Variable | Description |
|----------|-------------|
| `CLAUDE_HOOK_EVENT` | The event name (e.g., `PreToolUse`) |
| `CLAUDE_TOOL_NAME` | Name of the tool being executed |
| `CLAUDE_TOOL_INPUT` | JSON string of tool arguments |
| `CLAUDE_PROMPT` | User's input text (for `UserPromptSubmit`) |
| `CLAUDE_SESSION_ID` | Unique session identifier |

---

## Quick Reference

| Hook Type | Use Case |
|-----------|----------|
| `command` | Run shell scripts |
| `prompt` | Invoke LLM for analysis |

| Matcher Operator | Description |
|------------------|-------------|
| `equals` | Exact match |
| `contains` | Substring match |
| `regex` | Pattern match |

---