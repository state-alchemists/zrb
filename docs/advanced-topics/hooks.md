🔖 [Home](../../README.md) > [Documentation](../README.md) > [Advanced Topics](README.md) > [Hooks](hooks.md)

# Zrb Hook System

The Zrb Hook System allows you to extend and customize the behavior of LLM agents by executing shell commands or Python functions at specific points in their lifecycle.

This system is compatible with **Claude Code hooks**, allowing you to use your existing Claude configurations with Zrb.

## Lifecycle Events

Hooks can be registered for the following events:

| Event | Description |
|-------|-------------|
| `SessionStart` | Triggered when a new conversation session begins. |
| `UserPromptSubmit` | Triggered after a user submits a prompt, but before LLM processing. |
| `PreToolUse` | Triggered before a tool is executed. Can modify tool arguments or cancel execution. |
| `PostToolUse` | Triggered after a tool executes successfully. |
| `PostToolUseFailure` | Triggered after a tool execution fails. |
| `PreCompact` | Triggered before conversation history is compacted/summarized. |
| `Notification` | Triggered when the agent sends a notification to the UI. |
| `Stop` | Triggered when the agent execution is stopped (e.g., via Esc or Ctrl+C). |
| `SessionEnd` | Triggered when a conversation session ends. |

## Configuration (Claude Code Compatibility)

You can define hooks using JSON or YAML files. Zrb automatically scans for these files in:
1.  `~/.zrb/hooks.json` or `~/.zrb/hooks/*.json`
2.  `./.zrb/hooks.json` or `./.zrb/hooks/*.json`

*(Note: If you have customized `ZRB_ROOT_GROUP_NAME`, replace `.zrb` with your custom name, e.g., `.mycli`)*

### JSON Example (`~/.zrb/hooks.json`)

```json
[
  {
    "name": "git-auto-commit",
    "description": "Auto-commit changes after tool use",
    "events": ["PostToolUse"],
    "type": "command",
    "config": {
      "command": "git add . && git commit -m 'Auto-commit after tool execution'",
      "shell": true
    }
  }
]
```

### Hook Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique name for the hook. |
| `events` | array | List of lifecycle events to trigger this hook. |
| `type` | string | Hook type: `command`, `prompt`, or `agent`. |
| `config` | object | Type-specific configuration (e.g., `command` string). |
| `matchers` | array | Optional list of matchers to filter when the hook runs. |
| `async` | boolean | Whether to run the hook asynchronously (non-blocking). |
| `enabled` | boolean | Whether the hook is active. |
| `priority` | integer | Execution order (lower runs first). |

## Defining Hooks in Python

You can also register Python functions as hooks programmatically in your `zrb_init.py`.

```python
from zrb.llm.hook import hook_manager, HookContext, HookResult, HookEvent

async def my_python_hook(context: HookContext) -> HookResult:
    print(f"Hook triggered for event: {context.event}")
    return HookResult(success=True)

# Register for specific events
hook_manager.register(my_python_hook, events=[HookEvent.SESSION_START])

# Register as a global hook (runs on all events)
hook_manager.register(my_python_hook)
```

## Environment Variables

The following variables control the hook system:

*   `ZRB_HOOKS_ENABLED`: Whether to enable the hook system.
    *   Default: `1` (true)
*   `ZRB_HOOKS_DIRS`: Colon-separated list of additional directories to scan for hook configs.
    *   Default: Empty
*   `ZRB_HOOKS_TIMEOUT`: Default timeout for sync hooks in seconds.
    *   Default: `30`
*   `ZRB_HOOKS_LOG_LEVEL`: Logging level for hook execution.
    *   Default: `INFO`

---
🔖 [Home](../../README.md) > [Documentation](../README.md) > [Advanced Topics](README.md) > [Hooks](hooks.md)
