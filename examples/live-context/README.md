# Programmable Live Context Example

This example demonstrates `prompt_manager.add_live_context(name, provider)` — injecting volatile, per-turn runtime state into the agent's `<live-context>` block.

## System Prompt vs Live Context

Zrb composes two distinct prompt regions, and choosing the right one is the whole point of this example:

| | `register_section` | `add_live_context` |
|---|---|---|
| **Goes into** | the cached **system prompt** | the `<live-context>` block on each **user message** |
| **Runs** | at prompt-compose time | **every turn** |
| **Use for** | stable-ish context (persona, project facts, current sprint) | **volatile** state that changes turn to turn |
| **Caching** | changing it invalidates the cacheable prefix | changes freely **without** breaking prompt caching |

The built-in live-context block already carries time, git status, todos, worktree, and mode. `add_live_context` lets you append your own lines to it.

## How It Works

A provider is `Callable[[AnyContext], str]`. It runs once per turn; return `""` or `None` to emit nothing. Providers run in registration order, after the built-in lines. Re-registering the same name replaces the previous provider.

This example registers two providers on the built-in `llm_chat`:

1. **`wall_clock`** — the current local time, proving the block is recomputed each turn.
2. **`deploy_freeze`** — reads the `ZRB_DEPLOY_FROZEN` env var *every turn*, so flipping it mid-session changes the agent's behavior with no restart.

## Quick Start

```bash
cd examples/live-context
zrb llm chat
```

Ask about the time, then toggle the freeze flag from another shell and ask again:

```
> What time is it according to your live context?

# in another terminal:
export ZRB_DEPLOY_FROZEN=true

> Can you deploy right now?
```

The agent sees the freeze line on the very next turn — the cached system prompt never changed.

## Code

```python
import os
from datetime import datetime
from zrb.builtin.llm.chat import llm_chat


def render_wall_clock(ctx) -> str:
    return f"- Current time: {datetime.now():%Y-%m-%d %H:%M:%S}"


def render_deploy_freeze(ctx) -> str:
    frozen = os.environ.get("ZRB_DEPLOY_FROZEN", "").lower() in ("1", "true", "yes")
    if frozen:
        return "- ⚠️ DEPLOY FREEZE ACTIVE: do not run or suggest any deployment."
    return "- Deploys: allowed."


llm_chat.prompt_manager.add_live_context("wall_clock", render_wall_clock)
llm_chat.prompt_manager.add_live_context("deploy_freeze", render_deploy_freeze)
```

> `llm_chat.prompt_manager` is the public accessor on the chat task. The same call works on any `LLMChatTask` or `LLMTask` you build yourself.

## Customization

**Pull from a live source** — a provider is just a function, so read a database, a feature-flag service, or a module global an external thread updates:

```python
llm_chat.prompt_manager.add_live_context(
    "incident", lambda ctx: f"- Active incident: {incident_store.current() or 'none'}"
)
```

**Use the context** — the `ctx` argument is the active `AnyContext`; read `ctx.env.*` or inputs to tailor the line.

**Prefer the system prompt instead?** For content that's stable within a session, use `prompt_manager.register_section(...)` so it joins the cached prefix — see [Programming the Agent](../../docs/advanced-topics/programming-the-agent.md#dynamic-event-driven-prompts).

## See Also

- [`docs/advanced-topics/programming-the-agent.md`](../../docs/advanced-topics/programming-the-agent.md#per-turn-live-context-providers) — Per-turn live context providers
- `src/zrb/llm/prompt/live_context.py` — the built-in live-context rendering
- `src/zrb/llm/prompt/manager.py` — `add_live_context` / `register_section` / `create_live_context`
- `examples/model-tiering/` — another `llm_config` / prompt-manager customization
