# LLM Hook Examples

This example demonstrates the zrb hook system for LLM chat sessions.

## What Are Hooks?

Hooks allow you to intercept and modify LLM behavior at specific points in the conversation lifecycle:

| Event | Description | Can Block? |
|-------|-------------|------------|
| **SESSION_START** | Chat session begins. `source` is `startup` (fresh) or `resume` (continued). Can inject `additionalContext` | No |
| **SESSION_END** | **Terminal** — fires once when the chat session ends (`/exit`, EOF, Ctrl+C), not per turn. Matches on `source` | No |
| **USER_PROMPT_SUBMIT** | Before the LLM processes text. Can inject `additionalContext`; can halt the turn (`continue: false`) | **Yes** |
| **PRE_COMMAND** | Before a UI command runs (chat TUI) | **Yes** |
| **POST_COMMAND** | After a recognized UI command runs | No |
| **PRE_TOOL_USE** | Before **every** tool call. `permissionDecision` `deny`/`allow`/`ask` (force prompt)/`defer` (no opinion); can rewrite args (`updatedInput`) | **Yes** |
| **POST_TOOL_USE** | After a tool succeeds. Can block the result or replace it (`updatedToolOutput`) | **Yes** |
| **POST_TOOL_USE_FAILURE** | After a tool raises | No |
| **PERMISSION_REQUEST** | A tool call reaches an interactive approval prompt (fires only when the user is actually asked). Can auto-resolve via `hookSpecificOutput.decision.behavior` (`allow`/`deny`) | **Yes** |
| **NOTIFICATION** | System notifications. `AskUserQuestion` fires one with `notification_type='elicitation_dialog'` | No |
| **STOP** | A turn finishes and control returns to the user. Per-turn "done" signal. Can **block-to-continue** (`decision: "block"` + `reason`) to force another turn, and carries the `systemMessage` turn-extension | **Yes** |
| **STOP_FAILURE** | A turn ends on an unrecoverable API error. Observe-only; matches on `error_type` | No |
| **PRE_COMPACT** | Before history summarization (`trigger: "auto"`). Can inject `additionalContext`; can **block** compaction | **Yes** |
| **POST_COMPACT** | After history summarization completes. Can inject `additionalContext` | No |
| **SUBAGENT_START** / **SUBAGENT_STOP** | Around a sub-agent delegation. Observe-only; matches on `agent_type` | No |

## Hook Types

### 1. Python Hook (Programmatic)

Define hooks in `zrb_init.py` using `append_hook_factory()`:

```python
# zrb_init.py
from zrb.builtin.llm.chat import llm_chat
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def my_hook(context: HookContext) -> HookResult:
    if context.event == HookEvent.STOP:
        return HookResult(
            success=True,
            modifications={"systemMessage": "Did you learn anything worth documenting?"}
        )
    return HookResult()

def register_hooks(manager):
    manager.add_hook(my_hook, events=[HookEvent.STOP])

llm_chat.append_hook_factory(register_hooks)
```

The factory runs when a chat session starts, against that session's own `HookManager`.

### 2. JSON/YAML Hook Files

Place a `hooks.json` file in `.zrb/` or `~/.zrb/`, or any number of `*.json` / `*.yaml` / `*.yml` files in a `.zrb/hooks/` or `~/.zrb/hooks/` directory:

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
      {"field": "tool_name", "operator": "equals", "value": "Shell"}
    ]
  }
]
```

### 3. Python Hook Module

Create `*.hook.py` files with a `register(manager)` function in a `.zrb/hooks/` or `~/.zrb/hooks/` directory:

```python
# ~/.zrb/hooks/my_hook.hook.py
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

async def turn_logger(context: HookContext) -> HookResult:
    print(f"Turn ended: {context.session_id}")
    return HookResult()

def register(manager):
    manager.add_hook(turn_logger, events=[HookEvent.STOP])
```

## Hook Results

Hooks return `HookResult` with these effects:

| Method | Event | Effect |
|--------|-------|--------|
| `HookResult()` | Any | No effect, continue normally |
| `HookResult.block(reason)` | Any event marked **Yes** under "Can Block?" | Block execution (exit code 2). On Stop, continues the turn with `reason` |
| `HookResult(success=True, modifications={"continue": False, "stopReason": "..."})` | Any | Halt the whole run; ends the turn on UserPromptSubmit / Stop |
| `HookResult(success=True, modifications={"systemMessage": msg})` | **Stop** | Extend turn (side effects mode), original response returned |
| `HookResult(success=True, modifications={"systemMessage": msg, "replaceResponse": True})` | **Stop** | Extend turn (transform mode), extended response returned |
| `HookResult(success=True, modifications={"permissionDecision": "allow"})` | **PreToolUse** | Allow tool execution (skip the prompt) |
| `HookResult(success=True, modifications={"permissionDecision": "deny"})` | **PreToolUse** | Deny tool execution |
| `HookResult(success=True, modifications={"permissionDecision": "ask"})` | **PreToolUse** | Force the approval prompt; `"defer"` = no opinion |
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
- `.zrb/hooks.json` — JSON-based command hooks (several ship with `"enabled": false`), plus a worked agent-hook example (YAML is also supported — see [hooks.md](../../docs/llm/hooks.md))
- `.zrb/hooks/custom_hook.hook.py` — Python hook module (file-write logger, a 60-calls-per-minute tool rate limit, and an audit log appended to `~/.zrb/logs/audit.log` that records tool argument names, not values)

## Running

```bash
cd examples/llm-hooks
zrb llm chat
```

Then interact with the LLM and observe hook behavior.

## See Also

- `src/zrb/llm/hook/types.py` — HookEvent enum
- `src/zrb/llm/hook/interface.py` — HookContext and HookResult classes
- `docs/llm/hooks.md` — Full hooks documentation
