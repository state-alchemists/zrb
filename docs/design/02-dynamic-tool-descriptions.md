# #3 — Dynamic, permission-filtered tool descriptions

## What already exists

Better than first assumed. `create_delegate_to_agent_tool` in
`tool/delegate.py` already calls `sub_agent_manager.scan()` and builds an
`AVAILABLE AGENTS:` block into the tool docstring. And the delegate tools are
registered as **per-run factories** (`builtin/llm/chat.py`,
`lambda ctx: create_delegate_to_agent_tool()`), so the roster is already rebuilt
each run — it is never stale. The memory note "keep agent descriptions in the
DelegateToAgent docstring" is already honored here.

## The actual gap

The roster is **not permission-filtered**. When a permission policy (#2) or plan
mode (#1) denies `DelegateToAgent`, the tool still advertises the full agent
list — and conversely, an agent the current policy forbids delegating to still
appears. opencode/gemini compute the `task`/`agent` tool description against the
*currently allowed* set.

`ActivateSkill` (`tool/skill.py`) lists no skills in its docstring; skills are
surfaced via the `claude_skills` prompt section instead. That is acceptable, so
this feature scopes to the delegate tools only.

## Design

This feature depends on Primitive B (the `current_permission_policy`
ContextVar), so it lands *after* #2 in code but is trivial once that exists.

In `create_delegate_to_agent_tool` / `create_parallel_delegate_tool`, build the
`AVAILABLE AGENTS` block **at the moment the docstring is composed** (already
per-run) but filter the agent list:

```python
def _delegatable_agents(sub_agent_manager) -> list[Agent]:
    policy = current_permission_policy.get()
    agents = sub_agent_manager.scan()
    if policy is None:
        return agents                      # default: show all (today's behavior)
    # If the policy denies the delegate capability outright, the tool itself
    # won't run, but we still avoid advertising agents the policy forbids.
    return [a for a in agents
            if policy.decide("DelegateToAgent", Capability.DELEGATE,
                             {"agent_name": a.name}) != "deny"]
```

With no policy set, `_delegatable_agents` returns the full list and the
docstring is **identical to today**.

## Regression analysis

| Risk | Mitigation |
|------|------------|
| Hiding an agent the model needs | Default (`policy is None`) shows all agents — byte-identical docstring to today. |
| Description computed once and cached | Factories already rebuild per run; we only add a filter, no caching change. |
| Coupling delegate.py to the permission module | One import of `current_permission_policy` + `Capability`; both are already needed by #2. delegate.py already imports from `agent.run.runtime_state`, so the layering is consistent. |

## Tests (additions to `test/llm/tool/test_delegate.py`)

- No policy → docstring lists every scanned agent (existing behavior preserved).
- Policy denying delegation to agent X → X absent from docstring; others present.
- Policy allowing all → full list (parity with no-policy case).
