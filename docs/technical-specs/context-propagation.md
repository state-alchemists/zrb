🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md) > Context Propagation

# Context Propagation (Technical Specification)

Zrb threads execution state through async coroutines with `contextvars.ContextVar` instead of explicit parameters. Seventeen `ContextVar`s are indexed in `src/zrb/contextvars.py`, split into five layers. Update this page whenever you add, remove, or rename one.

For the design rationale in brief, see [Implicit State via ContextVars](../contributing/architecture.md#implicit-state-via-contextvars); for where the agent-run variables are bound during a chat request, see [LLM Chat Request Lifecycle](../llm/llm-chat-lifecycle.md).

---

## Table of Contents

- [The Five Layers](#the-five-layers)
- [The Scoping Pattern](#the-scoping-pattern)
- [Inheritance Pattern](#inheritance-pattern)
- [Resource Ownership and Cleanup](#resource-ownership-and-cleanup)
- [Why ContextVar (not Globals or Thread-locals)?](#why-contextvar-not-globals-or-thread-locals)
- [Known Inefficiency: env Dict Copy](#known-inefficiency-env-dict-copy)
- [Gotcha: asyncio.create_task() and Context Timing](#gotcha-asynciocreate_task-and-context-timing)
- [Gotcha: ThreadPoolExecutor Does Not Copy the Context](#gotcha-threadpoolexecutor-does-not-copy-the-context)

---

## The Five Layers

**Layer 1 — Task execution** (`src/zrb/context/any_context.py`):

```python
current_ctx: ContextVar[AnyContext | None] = ContextVar("current_ctx", default=None)
```

The active `Context` for the executing task. Set at the start of `execute_task_action()`, reset in its `finally` block.

**Layer 2 — LLM agent execution** (`src/zrb/llm/agent_state.py`, `src/zrb/llm/approval/approval_channel.py`). All nine are set at the start of `run_agent()` and reset in its `finally` block:

| Variable | Type | Purpose |
|---|---|---|
| `current_ui` | `AnyUI \| None` | Active UI for output and user interaction |
| `current_tool_confirmation` | `AnyToolConfirmation` | Tool approval policy |
| `current_yolo` | `bool` | Auto-approve all tool calls |
| `current_approval_channel` | `AnyApprovalChannel \| None` | Remote approval handler |
| `current_hook_manager` | `HookManager \| None` | Hook manager for the run; nested tools (e.g. delegate) fire SubagentStart/Stop on it |
| `current_agent_run_scope` | `str` | Identifies this agent run to nested tools needing per-conversation state (e.g. `file_observation.py`'s read-before-overwrite tracking) — the session name for a top-level run, a fresh per-delegation id for a sub-agent, so a sub-agent never inherits what its parent or siblings observed |
| `current_small_model` | `str \| Model \| None` | The UI's own `small_model` (set by `/model small ...`), so `journal_compliance.py`'s judge model and other small-tier consumers resolve per-session instead of leaking one process-wide value across concurrent chat sessions |
| `current_multimodal_model` | `str \| Model \| None` | The UI's own `multimodal_model` (set by `/model multimodal ...`), read by the attachment-description pipeline and voice engine, per-session for the same reason |
| `current_model` | `str \| Model \| None` | The run's main model, so a helper needing its own model (the summarizer, the journal judge) falls back to it rather than to `CFG.LLM_MODEL` |

**Layer 3 — Permission state** (`src/zrb/llm/permission/state.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_permission_policy` | `PermissionPolicy \| None` | In-force tool ruleset (`None` = legacy yolo behavior). Set by `run_agent()` from the explicit arg or inherited from a parent run; reset in its `finally` block. |
| `current_agent_mode` | `AgentModeState` | Mutable holder whose `.mode` is `AgentMode.BUILD` or `AgentMode.PLAN`. Set by the `EnterPlanMode` / `ExitPlanMode` tools; `PLAN` makes `get_effective_policy()` return the read-only `PLAN_MODE_POLICY`. |

**Layer 4 — Sandbox state** (`src/zrb/llm/sandbox/state.py`):

| Variable | Type | Purpose |
|---|---|---|
| `current_sandbox_policy` | `SandboxPolicy \| None` | In-force filesystem-containment policy (`None` = resolve from `CFG.LLM_SANDBOX_*`, disabled unless the deployment opted in). Set by `run_agent()` from the explicit arg or inherited from a parent run; reset in its `finally` block. Consumed by the `_sandbox_gate` in `agent/common.py` and the shell tools' OS-sandbox wrapper. |

**Layer 5 — Tool ambient state** (`src/zrb/llm/tool/ambient_state.py`). Set and cleared by their owning tools (`src/zrb/llm/tool/worktree.py`, `src/zrb/llm/tool/ask.py`), not at a single entry point:

| Variable | Type | Purpose |
|---|---|---|
| `active_worktree` | `str` | Path of the worktree the agent is operating in (set by `EnterWorktree`, cleared by `ExitWorktree`) |
| `_current_session` | `str` | The active conversation's *display* session name, defaulted by tools (todo tools, `DelegateToAgent`, `BufferedUI`) called without an explicit `session=` — a client-supplied label with no uniqueness guarantee, never a resource-ownership key |
| `interactive_mode` | `bool` | Whether the chat session is interactive — gates `ask_user_question` so non-interactive runs short-circuit instead of blocking on stdin |
| `current_chat_session_id` | `str` | `ChatSessionManager`'s own unique session_id, bound once per message drive in `chat_session_runner.py`. Unlike `_current_session`, it is unique: `shell_background.py` tags background processes with it so `ChatSessionManager.remove_session()` cleans up exactly that session's processes, never a same-named one's |

## The Scoping Pattern

Every `ContextVar` follows the same RAII-style pattern:

```python
token = current_ctx.set(ctx)
try:
    ...task body...
finally:
    current_ctx.reset(token)  # restores the previous value
```

`reset(token)` restores the value from before `set()`, so nested calls (e.g. a sub-agent delegated from a parent) each get their own scope while inheriting the parent's values at entry.

## Inheritance Pattern

Agent context variables fall back to the ambient value, so a child agent without an explicit argument inherits its parent's — this is how YOLO mode, approval channels, and UI handles flow through nested agent calls:

```python
# run_agent.py — resolve effective value
effective_ui = ui_arg or current_ui.get()
effective_yolo = yolo or current_yolo.get()
```

A delayed live-sub-agent continuation starts *after* the original run's scope has ended. `AuthoritySnapshot` captures the original run's effective permission and sandbox authority while the scope is still active, and the continuation explicitly rebinds it, so a later, unrelated ambient context cannot broaden the continuation's authority.

## Resource Ownership and Cleanup

Tie each resource to the narrowest lifetime that can safely clean it up:

| Resource | Owner | Cleanup boundary |
|---|---|---|
| Chat driver task | `ChatSession` | Cancellation or chat-session removal |
| Background shell process | Chat session ID | Session removal or process shutdown |
| Live sub-agent session | Parent chat session ID | Agent completion or session removal |
| Activity-panel entry | Parent chat session ID | Sub-agent completion or session removal |
| Approval wait/future | Approval channel / chat session | Response, cancellation, or session removal |
| Agent run ContextVars | Agent run | `run_agent()` scope exit |
| Conversation history | Display conversation name | History manager persistence/retention |

Client-supplied display names are fine for labels and history files, never for ownership or cleanup keys. A resource that outlives one message must be owned by an opaque, stable identifier that cannot collide with another concurrent session.

## Why ContextVar (not Globals or Thread-locals)?

Zrb is fully asyncio-based, and thread-locals don't work with coroutines (many share a thread). A global dict keyed on task/session ID would work but needs lookups and manual lifecycle management. `ContextVar` integrates with the asyncio scheduler:

- `asyncio.create_task()` automatically copies the current context to the new task (PEP 567).
- `asyncio.gather()` runs coroutines in-place, sharing the caller's context.
- Token-based `reset()` ensures correct cleanup even if exceptions occur.

## Known Inefficiency: `env` Dict Copy

Every task `Context` (`context.py:25`) copies the whole shared env dictionary:

```python
self._env = shared_ctx.env.copy()
```

This is O(n) in env vars, once per task execution — not a bottleneck for typical workloads (< 100 vars, dozens of tasks). Under memory pressure from large fan-out (hundreds of concurrent tasks, large envs), look here first; a lazy/copy-on-write approach would remove the redundant copies.

## Gotcha: `asyncio.create_task()` and Context Timing

`execution.py:97` creates a new asyncio task for action execution:

```python
action_coro = asyncio.create_task(run_async(execute_action_with_retry(task, session)))
```

Python copies the context at `create_task()` time, so if the parent resets `current_ctx` before the task is scheduled, the task still sees the creation-time value. This is safe because `execute_action_with_retry` re-establishes its own `current_ctx` scope — keep it in mind if the execution model changes.

## Gotcha: `ThreadPoolExecutor` Does Not Copy the Context

A pool thread starts with an **empty** context — nothing ambient reaches work submitted to one, which silently turns every per-run value into its static default. `ThreadPoolHookExecutor` (the synchronous hook dispatcher) hit this: the self-review gate's reviewer resolved `CFG.LLM_MODEL` instead of the run's model, since `current_model` was unset in the thread. Anything crossing a thread boundary must copy the caller's context explicitly:

```python
executor.submit(contextvars.copy_context().run, callable, *args)
```

`contextvars.copy_context()` captures the values as they are at submission; the hook's own `current_*` writes stay inside the copy, so the pool thread never mutates the caller's scope. Prefer `asyncio.to_thread`, which copies the context for you, where the call site can be async.

Copy what is safe to use from the other thread, not everything. The hook executor runs each hook in an event loop of its own, so it clears `current_ui`, `current_tool_confirmation` and `current_approval_channel` in the copy (`_copy_context_for_hook`): all three are driven from the caller's loop, and a hook tool reaching one would cross threads.

---

🔖 [Documentation Home](../../README.md) > [Technical Specs](./llm-context.md) > Context Propagation
