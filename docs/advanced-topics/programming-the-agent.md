🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Programming the Agent

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
| Filesystem sandbox | `sandbox=SandboxPolicy(...)` (or `True`/`False`) — contain file/shell access | [Sandbox](sandbox.md) |
| Approval channel | `task.append_approval_channel(...)` — async approval over any transport | [Permission Policy](permission-policy.md) |
| Model routing | `model=lambda ctx: ...` — pick the model per request | [`examples/model-tiering`](../../examples/model-tiering) |
| Prompt (string → template → callable → sections) | `message=`, `system_prompt=`, `prompt_manager=` | [Programming the Prompt](programming-the-prompt.md) |
| History processors | `history_processors=[fn]` — prune / redact / summarize | ↓ below |
| Custom UI | `ui=...` / `ui_factory=...` — TUI, web/SSE, chat bot | [Custom UI](llm-custom-ui.md) |

A custom tool is just a typed function — its signature and docstring are the spec the model sees:

```python
async def get_open_incidents(team: str) -> str:
    """Return the current open incidents for a given team."""
    return my_oncall_db.query(team)  # your code, in-process

chat = LLMChatTask(name="ops-chat", tools=[get_open_incidents])
```

## Programming the prompt

Everything the model reads — the per-turn `message` and the standing `system_prompt` — is a value you supply: a string, a `{ctx…}` template, a Python callable, or a fully composed `PromptManager` with reorderable sections, live-state providers, and model-adaptive profiles. That whole ladder, from the one-line string up to dynamic file-backed sections, has its own page:

👉 **[Programming the Prompt](programming-the-prompt.md)** — the full ladder, including dynamic sections (`register_section`), per-turn live context (`add_live_context`), and profiles.

The short version for the two most common runtime needs:

```python
# The whole system prompt as a callable — evaluated per execution:
LLMTask(
    name="deploy-helper",
    system_prompt=lambda ctx: f"You are deploying to {ctx.env.DEPLOY_TARGET}. Be careful in prod.",
)

# A named section whose content reflects live state, spliced into the section order:
pm.register_section("sprint_context", lambda ctx: f"Active sprint: {load_current_sprint()}")
```

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

**Often you need no tool at all.** When a deterministic step already produced the context, hand it to the model through its `message` template — the command's output *is* the input to the decision:

```python
from zrb import cli, CmdTask, LLMTask, Task

diff = cli.add_task(CmdTask(name="collect-diff", cmd="git diff --staged"))

review = cli.add_task(
    LLMTask(
        name="review",
        upstream=[diff],
        message="Review this staged diff and list concerns, or reply 'LGTM':\n\n"
                "{ctx.xcom['collect-diff'].pop()}",
    )
)

def act(ctx):
    ctx.print(ctx.xcom["review"].pop())  # page, comment on the PR, block the commit…

act_task = cli.add_task(Task(name="act", action=act))

diff >> review >> act_task
```

Fetch with deterministic code, reason with the LLM, act with deterministic code. Reach for a **custom tool** only when the agent must pull *more* data mid-reasoning (query your DB, hit an API) rather than being handed everything up front — see [`examples/agent-in-pipeline`](../../examples/agent-in-pipeline), which combines the pipeline shape with an in-process tool.

For an **interactive** variant, swap `LLMTask` for `LLMChatTask` and seed the command's output into its `system_prompt` so the user can then converse about it — see [Programming the Prompt → Seeding a chat with context](programming-the-prompt.md#seeding-a-chat-with-context).

👉 Runnable end-to-end example: [`examples/agent-in-pipeline`](../../examples/agent-in-pipeline).

## See also

- [Programming the Prompt](programming-the-prompt.md) — string → template → callable → `PromptManager`, and how to feed a `CmdTask`'s output into the model
- [LLM Assistant & AI Tasks](llm-integration.md) — tools, sub-agents, context management
- [LLMChatTask API Reference](../task-types/llmchat-task.md) — the full builder API
- [LLM Chat Request Lifecycle](llm-chat-lifecycle.md) — how a turn flows end to end
- [Hook System](hooks.md) · [Permission Policy](permission-policy.md) · [Custom UI](llm-custom-ui.md)

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Programming the Agent
