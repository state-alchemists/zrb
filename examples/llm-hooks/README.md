# LLM Hook Examples

This example demonstrates the zrb hook system for LLM chat sessions.

## What Are Hooks?

Hooks allow you to intercept and modify LLM behavior at specific points in the conversation lifecycle:

- **SESSION_START** - When a session begins
- **SESSION_END** - Before a session ends
- **USER_PROMPT_SUBMIT** - When user sends a message
- **PRE_TOOL_USE** - Before tool execution (can block)
- **POST_TOOL_USE** - After tool execution
- **POST_TOOL_USE_FAILURE** - After tool execution fails
- **NOTIFICATION** - System notifications
- **STOP** - Session stopped (Ctrl+C)
- **PRE_COMPACT** - Before history compaction

## Hook Types

### 1. Python Hook (Programmatic)

Define hooks in `zrb_init.py` using `add_hook_factory()`:

```python
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def my_hook(context: HookContext) -> HookResult:
    if context.event == HookEvent.SESSION_END:
        return HookResult.with_system_message("Don't forget to journal!")
    return HookResult()

def register_hooks(hook_manager):
    hook_manager.register(my_hook, events=[HookEvent.SESSION_END])

# In zrb_init.py:
from zrb import llm_chat
llm_chat.add_hook_factory(lambda mgr: mgr.register(my_hook, events=[HookEvent.SESSION_END]))
```

### 2. JSON/YAML Hook Files

Place `hooks.json` or `hooks.yaml` in `.zrb/` or `~/.zrb/`:

```json
[
  {
    "name": "block-dangerous-commands",
    "events": ["PreToolUse"],
    "type": "command",
    "config": {
      "command": "echo '{\"decision\": \"block\", \"reason\": \"Dangerous command blocked\"}'"
    },
    "matchers": [
      {"field": "tool_name", "operator": "equals", "value": "Bash"}
    ]
  }
]
```

### 3. Python Hook Module

Create `*.hook.py` files with `register(manager)` function:

```python
# ~/.zrb/hooks/my_hook.hook.py
from zrb.llm.hook.interface import HookContext, HookResult

async def session_logger(context: HookContext) -> HookResult:
    print(f"Session ended: {context.session_id}")
    return HookResult()

def register(manager):
    manager.register(session_logger, events=["SessionEnd"])
```

## Hook Results

Hooks return `HookResult` with these effects:

| Method | Effect |
|--------|--------|
| `HookResult()` | No effect, continue normally |
| `HookResult.with_system_message(msg)` | Inject message into conversation, return original response |
| `HookResult.with_system_message(msg, replace_response=True)` | Inject message, return extended session's response |
| `HookResult.block(reason, context)` | Block execution (exit code 2) |
| `HookResult.allow(decision, reason)` | Allow tool execution |
| `HookResult.deny(reason)` | Deny tool execution |
| `HookResult.ask(reason)` | Ask user for permission |

### SESSION_END System Messages

When a SESSION_END hook returns `with_system_message()`, the session extends with that message:

```python
# Side effects only (default) - extended session invisible to user
# Use for logging, journaling, notifications
return HookResult.with_system_message("Do something in background")

# Replace response - extended session's response becomes the final response
# Use for post-processing, summarization, transformation
return HookResult.with_system_message("Summarize the conversation.", replace_response=True)
```

## Example Files

- `zrb_init.py` - Programmatic hook registration
- `.zrb/hooks.json` - JSON-based command hooks
- `.zrb/hooks.yaml` - YAML-based command hooks
- `custom_hook.hook.py` - Python hook module

## Running

```bash
cd examples/llm-hooks
zrb llm-chat
```

Then interact with the LLM and observe hook behavior:

1. **SESSION_START**: Hook prints session ID
2. **PRE_TOOL_USE**: Hook logs tool usage, can block dangerous tools
3. **POST_TOOL_USE**: Hook logs tool results
4. **SESSION_END**: Hook reminds to journal

## See Also

- `src/zrb/llm/hook/types.py` - HookEvent enum
- `src/zrb/llm/hook/interface.py` - HookResult class
- `src/zrb/llm/hook/journal.py` - Built-in journaling hook