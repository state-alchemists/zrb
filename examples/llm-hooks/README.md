# LLM Hook Examples

This example demonstrates the zrb hook system for LLM chat sessions.

## What Are Hooks?

Hooks allow you to intercept and modify LLM behavior at specific points in the conversation lifecycle:

| Event | Description | Can Block? |
|-------|-------------|------------|
| **SESSION_START** | Chat session begins. `source` is `startup` (fresh) or `resume` (continued). Can inject `additionalContext` | No |
| **SESSION_END** | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn | No |
| **USER_PROMPT_SUBMIT** | Before the LLM processes text. Can inject `additionalContext` | **Yes** |
| **PRE_COMMAND** | Before a UI command runs (chat TUI) | **Yes** |
| **POST_COMMAND** | After a recognized UI command runs | No |
| **PRE_TOOL_USE** | Before **every** tool call. Can deny (`permissionDecision: "deny"`), auto-allow, or rewrite args (`updatedInput`) | **Yes** |
| **POST_TOOL_USE** | After a tool succeeds. Can block the result or replace it (`updatedToolOutput`) | **Yes** |
| **POST_TOOL_USE_FAILURE** | After a tool raises | No |
| **PERMISSION_REQUEST** | A tool call reaches an interactive approval prompt (fires only when the user is actually asked). Can auto-resolve via `decision.behavior` (`allow`/`deny`) | No |
| **NOTIFICATION** | System notifications. `AskUserQuestion` fires one with `notification_type='elicitation_dialog'` | No |
| **STOP** | A turn finishes and control returns to the user. Per-turn "done" signal. Can **block-to-continue** (`decision: "block"` + `reason`) to force another turn, and carries the `systemMessage` turn-extension | **Yes** |
| **PRE_COMPACT** | Before history summarization (`trigger: "auto"`). Can inject `additionalContext` | No |

## Hook Types

### 1. Python Hook (Programmatic)

Define hooks in `zrb_init.py` using `add_hook_factory()`:

```python
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def my_hook(context: HookContext) -> HookResult:
    if context.event == HookEvent.STOP:
        return HookResult(
            success=True,
            modifications={"systemMessage": "Did you learn anything worth documenting?"}
        )
    return HookResult()

def register_hooks(hook_manager):
    hook_manager.register(my_hook, events=[HookEvent.STOP])

# In zrb_init.py:
from zrb import llm_chat
llm_chat.add_hook_factory(lambda mgr: mgr.register(my_hook, events=[HookEvent.STOP]))
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

async def turn_logger(context: HookContext) -> HookResult:
    print(f"Turn ended: {context.session_id}")
    return HookResult()

def register(manager):
    manager.register(turn_logger, events=["Stop"])
```

## Hook Results

Hooks return `HookResult` with these effects:

| Method | Event | Effect |
|--------|-------|--------|
| `HookResult()` | Any | No effect, continue normally |
| `HookResult.block(reason)` | Stop / UserPromptSubmit / PreToolUse | Block execution (exit code 2). On Stop, continues the turn with `reason` |
| `HookResult(success=True, modifications={"systemMessage": msg})` | **Stop** | Extend turn (side effects mode), original response returned |
| `HookResult(success=True, modifications={"systemMessage": msg, "replaceResponse": True})` | **Stop** | Extend turn (transform mode), extended response returned |
| `HookResult(success=True, modifications={"permissionDecision": "allow"})` | **PreToolUse** | Allow tool execution |
| `HookResult(success=True, modifications={"permissionDecision": "deny"})` | **PreToolUse** | Deny tool execution |
| `HookResult(success=True, modifications={"updatedInput": {...}})` | **PreToolUse** | Rewrite tool arguments |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"decision": {"behavior": "allow"}}})` | **PermissionRequest** | Auto-allow approval prompt |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"decision": {"behavior": "deny"}}})` | **PermissionRequest** | Auto-deny approval prompt |
| `HookResult(success=True, modifications={"hookSpecificOutput": {"updatedToolOutput": "..."}})` | **PostToolUse** | Replace the tool result |

### STOP System Messages (turn extension)

When a `Stop` hook returns a `systemMessage` modification, the turn extends:

```python
# Side effects only (default) — extended turn invisible to user
# Use for journaling, notifications, logging
return HookResult(
    success=True,
    modifications={"systemMessage": "Review the turn for learnings worth documenting."}
)

# Replace response — extended turn's response becomes the final response
# Use for summarization, transformation, post-processing
return HookResult(
    success=True,
    modifications={
        "systemMessage": "Summarize the conversation.",
        "replaceResponse": True
    }
)
```

### Block-to-Continue (Stop)

A `Stop` hook can force another turn by blocking with a reason:

```python
# The reason is injected as the next prompt and the agent runs again
# A consecutive-block cap (8) prevents infinite loops
return HookResult.block(reason="I need more information before concluding.")
```

> **Migrating from `SessionEnd`:** `SessionEnd` is now **terminal** (fires once when the chat ends). If you had a hook on `SessionEnd` for per-turn journaling, summarization, or turn-extension, move it to `Stop`.

## Example Files

- `zrb_init.py` — Programmatic hook registration
- `.zrb/hooks.json` — JSON-based command hooks
- `.zrb/hooks.yaml` — YAML-based command hooks
- `custom_hook.hook.py` — Python hook module

## Running

```bash
cd examples/llm-hooks
zrb llm-chat
```

Then interact with the LLM and observe hook behavior.

## See Also

- `src/zrb/llm/hook/types.py` — HookEvent enum
- `src/zrb/llm/hook/interface.py` — HookResult class
- `src/zrb/llm/hook/journal.py` — Built-in journaling hook
- `docs/advanced-topics/hooks.md` — Full hooks documentation
