# #4 — Background / async subagents

## What exists

`DelegateToAgentsParallel` (`tool/delegate.py`) uses `asyncio.gather` but
**awaits all results within the turn**. The whole turn model is synchronous:
`run_agent` runs to completion and returns inline. There is no task registry, no
cross-turn notification, no way to surface a result in a *later* turn.

The ambient state in `agent/run/runner.py` (`current_ui`,
`current_tool_confirmation`, `current_yolo`, `current_approval_channel`, and now
`current_permission_policy`, `current_agent_mode`) is explicitly **per-run** and
reset on exit (`token = var.set(...)` / `var.reset(token)`). A background task
that referenced those live ContextVars after the parent run resets them would be
a use-after-reset hazard.

## Design — separate tools, snapshot, poll

Do **not** modify the existing delegate tools. Add two new ones, so the
synchronous path is untouched (zero regression by construction).

```python
# zrb/llm/tool/delegate_background.py
def create_background_delegate_tool(sub_agent_manager=None):
    async def delegate_to_agent_background(
        agent_name, deliverable, task, non_goals, additional_context=""
    ) -> str:
        """Start a subagent in the background and return a handle immediately.
        Poll with GetDelegationResult(handle). Use for long, independent,
        read-or-isolated work you don't need before continuing."""
        snapshot = _snapshot_ambient_state()          # copy, not live refs
        handle = get_random_name(separator="-", add_random_digit=True)
        coro = _run_with_snapshot(snapshot, agent_name, deliverable, task,
                                  non_goals, additional_context, sub_agent_manager)
        _registry().start(handle, coro)               # creates asyncio.Task
        return f"Started background agent '{agent_name}'. Handle: {handle}. " \
               "Call GetDelegationResult(handle) to collect the result."

def create_get_delegation_result_tool():
    async def get_delegation_result(handle: str) -> str:
        """Return the result of a background delegation, or a 'still running'
        status. Once collected, the handle is consumed."""
        return _registry().poll(handle)
```

### Registry — session-scoped, not ContextVar

```python
# zrb/llm/tool/delegate_background.py
class _BackgroundRegistry:
    # keyed by handle -> asyncio.Task
    def start(self, handle, coro): ...
    def poll(self, handle) -> str:  # "running" | result | error | "unknown handle"
```

A module-level singleton keyed by handle. Tasks are created with
`asyncio.ensure_future`. Because background work outlives the spawning tool
call but lives within the same event loop / process, a process-lifetime
singleton is sufficient for the first iteration (polling model). No persistence
across process restarts — documented.

### Ambient-state snapshot

`_snapshot_ambient_state()` reads the current values of the run ContextVars
**once, eagerly** and `_run_with_snapshot` re-sets them inside the background
task's own context before calling `run_agent`. This avoids reading the parent's
ContextVars after they are reset. The background agent uses a `BufferedUI` (same
as the foreground delegate) so its output does not interleave; on completion the
buffer is attached to the polled result rather than streamed live.

### Permission inheritance

The snapshot includes `current_permission_policy` and `current_agent_mode`, so a
background agent inherits the parent's restrictions exactly like a foreground
sub-agent. A plan-mode parent cannot spawn a mutating background agent (the
`DELEGATE` deny in `PLAN_MODE_POLICY` blocks the background-delegate tool too,
since it is tagged `DELEGATE`).

## Confirmation — inherit and interrupt (critical)

A background agent **inherits the main agent's permissions** and, when a tool
call needs approval, **interrupts the UI to ask the user** — it does not
auto-approve and does not silently deny.

This works by reusing machinery that already exists for concurrent delegation.
The default interactive UI's `ask_user` (`ui/default/confirmation_mixin.py`) is
a **confirmation queue**: its docstring states it is built so "multiple parallel
callers (e.g. delegate sub-agents) can each request user input… queues them so
each waits its turn." A background sub-agent runs with a `BufferedUI` whose
`ask_user` forwards to the parent UI; the parent enqueues the prompt, shows it,
and resolves it on the user's keypress — exactly the path a synchronous delegate
uses. Because the detached task copies the spawning context
(`asyncio.ensure_future`), it inherits the parent's approval channel, yolo flag,
permission policy, and UI; nothing is neutralized.

### Iterations that were wrong

- **Fail-closed (deny anything not pre-approved).** Made background useless: a
  "write a poem to /tmp" delegation had `Write`, then `Bash`, then even `echo`
  denied, and the agent gave up empty-handed.
- **Auto-approve (`yolo=True`).** Worked, but granted the sub-agent *more* than
  a non-yolo main agent has — it could mutate without the approval the main
  agent would have required. Rejected: a sub-agent must not exceed its parent's
  permissions.

The fix was to **delete the guardrails entirely** and let the sub-agent inherit
and route approvals through the queue, rather than short-circuiting them.

### Residual note

If the main agent keeps polling `GetDelegationResult` and gives up before the
user answers the queued prompt, the background agent stays parked on the prompt;
once answered it completes and the result is collectable on a later poll. That's
model-pacing, not a correctness issue — the guidance tells the model to keep
polling.

## Fan-out replaces DelegateToAgentsParallel

The synchronous `DelegateToAgentsParallel` was removed. Concurrency is now
expressed by starting several `DelegateToAgentBackground` agents and collecting
each handle with `GetDelegationResult` — same parallelism, one fewer tool, and
it reuses the (safer) fail-closed background path.

## Why polling, not push

True push-notification-on-complete would have to inject a result into a *future*
turn's context — that touches `run_agent`'s lifecycle and the history model.
Polling keeps the change confined to two new tools + a registry, with no
lifecycle surgery. Push can be a later iteration once the storage model is
proven.

## Regression analysis

| Risk | Mitigation |
|------|------------|
| Changing the synchronous delegate path | Not touched; new tools are separate. |
| Use-after-reset of ambient ContextVars | Eager snapshot + re-set inside the background task's context. |
| Orphaned tasks at session end | Registry exposes a cancel-all hook called from session teardown; documented limitation that results don't persist across process restart. |
| UI interleaving from concurrent agents | Reuse `BufferedUI` + shared-lock machinery already proven for parallel delegation. |
| Background agent bypassing plan-mode restrictions | Tagged `DELEGATE`; snapshot carries policy + mode. |
| Recursion (background agent spawning more) | Background tools, like the sync ones, carry `zrb_is_delegate_tool=True` so sub-agents never receive them. |

## Tests (`test/llm/tool/test_delegate_background.py`)

- `DelegateToAgentBackground` returns a handle immediately (does not block on the
  sub-agent's completion — assert via a slow fake agent + the call returning
  first).
- `GetDelegationResult` returns "running" before completion, the result after.
- Unknown handle → clear error message.
- Snapshot carries policy/mode: a plan-mode parent → background delegate tool is
  denied by the gate (tagged DELEGATE).
- Existing `test_delegate.py` passes unchanged (sync path untouched).
