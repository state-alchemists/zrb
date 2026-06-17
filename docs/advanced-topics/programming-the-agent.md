# Programming the Agent

`zrb llm chat` is a turnkey AI coding assistant — file tools, an interactive TUI, permission prompts, and conversation history all work out of the box. But Zrb does not stop at configuration. Every behavior of the agent is a value you can supply or a Python callable you can register, **in the same file where you define the rest of your automation** — no separate SDK, no plugin runtime, no JSON schema.

This page is the map. Each capability links to its dedicated guide; the two that have no other home — **dynamic prompts** and **history processors** — are documented in full below.

## When do you actually need this?

For "chat with my codebase," you never touch any of it. You reach for Python when behavior must depend on **runtime state**, integrate **in-process with your own code**, or live **inside a larger program**:

- The agent needs an ability only your code provides (query your DB, hit an internal API) → **custom tool**.
- A model decision should depend on the task at hand (cost, sensitivity, length) → **model callable**.
- Approvals must flow through your own channel (Slack, a web UI, company auth) → **approval channel**.
- The system prompt must carry live facts (current sprint, deploy target, schema) → **dynamic prompt section**.
- Long conversations must stay affordable or redact secrets → **history processor**.
- The agent is one step in a pipeline, between deterministic tasks → **agent as a pipeline node**.

## The capabilities at a glance

| Capability | How | Guide |
|---|---|---|
| Custom tools | `tools=[fn]` / `task.add_tool(fn)` — a plain Python function, in-process | [LLM Integration](llm-integration.md) |
| Lifecycle hooks | `task.add_hook_factory(...)` — fire on tool calls, prompts, session start/end | [Hook System](hooks.md) |
| Permission policy | `permissions=PermissionPolicy(...)` — allow / ask / deny per tool | [Permission Policy](permission-policy.md) |
| Approval channel | `task.append_approval_channel(...)` — async approval over any transport | [Permission Policy](permission-policy.md) |
| Model routing | `model=lambda ctx: ...` — pick the model per request | [`examples/model-tiering`](../../examples/model-tiering) |
| Dynamic prompt sections | `prompt_manager.register_section(name, provider)` | ↓ below |
| History processors | `history_processors=[fn]` — prune / redact / summarize | ↓ below |
| Custom UI | `ui=...` / `ui_factory=...` — TUI, web/SSE, chat bot | [Custom UI](llm-custom-ui.md) |

A custom tool is just a typed function — its signature and docstring are the spec the model sees:

```python
async def get_open_incidents(team: str) -> str:
    """Return the current open incidents for a given team."""
    return my_oncall_db.query(team)  # your code, in-process

chat = LLMChatTask(name="ops-chat", tools=[get_open_incidents])
```

## Dynamic (event-driven) prompts

A static `system_prompt` is fine until the prompt must reflect something that changes at runtime. Two mechanisms cover that.

**1. The whole system prompt as a callable** — evaluated per execution with the active context:

```python
LLMTask(
    name="deploy-helper",
    system_prompt=lambda ctx: f"You are deploying to {ctx.env.DEPLOY_TARGET}. Be careful in prod.",
)
```

**2. A named, composable section** — better when you want to *add* live context to the standard prompt without replacing it. Register a provider on a `PromptManager` and include its name in the section order:

```python
from zrb import LLMChatTask
from zrb.llm.prompt.manager import PromptManager

pm = PromptManager(
    # the built-in default order, with your section spliced in
    include_sections=[
        "persona", "mandate", "git_mandate", "journal_mandate",
        "system_context", "project_context",
        "sprint_context",        # ← your section
        "tool_guidance", "claude_skills",
    ],
)

# provider: Callable[[AnyContext], str]  — return "" to emit nothing this turn
pm.register_section("sprint_context", lambda ctx: f"Active sprint: {load_current_sprint()}")

chat = LLMChatTask(name="sprint-chat", prompt_manager=pm)
```

The provider runs at prompt-compose time, every request, so the section always reflects current state. If a name in `include_sections` has no registered provider, Zrb looks for a `<name>.md` prompt file instead (project override → env → package), so static and dynamic sections share one ordering mechanism. See the *LLM Prompt System* notes in `AGENTS.md` and ADR-0061 for the full resolution order.

## History processors

A history processor is an async callable that receives the running message history and returns a (possibly modified) one. They run between tool-call iterations — use them to keep the context window affordable, strip sensitive data, or inject retrieved context.

```python
HistoryProcessor = Callable[..., Awaitable[list[ModelMessage]]]
```

Register one or more — they run in sequence:

```python
async def redact_secrets(messages):
    for m in messages:
        ...  # scrub tokens / keys from message parts
    return messages

LLMTask(name="safe-agent", history_processors=[redact_secrets])
# or, post-construction:  task.append_history_processor(redact_secrets)
```

For the common case — automatic summarization once the conversation grows past a token threshold — Zrb ships a factory so you don't write the windowing logic yourself:

```python
from zrb.llm.summarizer.history_summarizer import create_summarizer_history_processor

summarizer = create_summarizer_history_processor(
    conversational_token_threshold=40_000,  # summarize older turns past this
    summary_window=6,                        # keep this many recent turns verbatim
)
LLMTask(name="long-chat", history_processors=[summarizer])
```

A processor that raises is logged and skipped — a broken processor degrades gracefully rather than killing the run.

## The agent as a pipeline node

This is the capability that has no equivalent in a config-driven assistant: because an `LLMTask` is an ordinary Zrb task, it sits in a DAG between deterministic steps. Its final answer is pushed to [XCom](../core-concepts/session-and-context.md) under the task's name, and downstream tasks consume it like any other task output:

```python
fetch_ticket >> triage_with_llm >> route_to_team
```

Combine that with a custom tool that calls into your codebase, and the agent becomes a reasoning step wired directly into your systems — fetch with deterministic code, reason with the LLM, act with deterministic code.

👉 Runnable end-to-end example: [`examples/agent-in-pipeline`](../../examples/agent-in-pipeline).

## See also

- [LLM Assistant & AI Tasks](llm-integration.md) — tools, sub-agents, context management
- [LLMChatTask API Reference](../task-types/llmchat-task.md) — the full builder API
- [LLM Chat Request Lifecycle](llm-chat-lifecycle.md) — how a turn flows end to end
- [Hook System](hooks.md) · [Permission Policy](permission-policy.md) · [Custom UI](llm-custom-ui.md)
