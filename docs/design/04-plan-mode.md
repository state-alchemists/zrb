# #1 — Plan mode (read-only discovery + approval gate)

## What exists

The Frame → Understand → Plan → Execute loop is **prose only** in
`prompt/markdown/mandate.md` ("Working Loop"). Nothing enforces read-only.
`yolo` is the only mode axis today.

## Design

Plan mode is a *preset* `PermissionPolicy` (from #2) plus a small amount of
glue: ambient mode state, two tools, and a prompt line.

### Mode state

```python
# zrb/llm/permission/mode.py
class AgentMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"

current_agent_mode: ContextVar[AgentMode] = ContextVar(
    "current_agent_mode", default=AgentMode.DEFAULT
)
```

Modeled exactly on `active_worktree` in `tool/worktree.py`. **Default is
`DEFAULT`** → every path below is a no-op until plan mode is explicitly entered.

### The plan-mode policy

```python
PLAN_MODE_POLICY = PermissionPolicy(rules=(
    Rule(Capability.READ.value,     "allow"),
    Rule(Capability.META.value,     "allow"),   # todos, skills, AskUser, Exit/EnterPlanMode
    Rule(Capability.EDIT.value,     "deny"),
    Rule(Capability.EXECUTE.value,  "deny"),     # Bash, RunZrbTask — conservative
    Rule(Capability.NETWORK.value,  "allow"),    # research is part of discovery
    Rule(Capability.DELEGATE.value, "deny"),     # children could mutate; deny in plan
    Rule("*",                       "deny"),     # UNKNOWN tools → deny (safe default)
))
```

Network is allowed because read-only discovery legitimately includes web
research (gemini's plan phase does the same). `EXECUTE`/`DELEGATE` are denied:
shell and sub-agents are dual-use and we cannot prove read-only, so we err
toward the conservative gemini-style read-only discovery phase.

### Enforcing `deny` — the execution wrapper

The approval layer only does allow/ask. We add a thin execution wrapper that
reads mode+policy and short-circuits denied tools **before they run**:

```python
# inside agent/common.py tool wrapping (create_safe_wrapper / SafeToolsetWrapper)
def _permission_gate(tool_name, capability, args) -> ToolReturn | None:
    policy = _active_policy()              # PLAN_MODE_POLICY if mode==PLAN else current_permission_policy
    if policy is None:
        return None                        # default-off: nothing denied
    if policy.decide(tool_name, capability, args) == "deny":
        return ToolReturn(
            return_value=None,
            content=(f"Blocked: '{tool_name}' is not permitted in "
                     f"{current_agent_mode.get().value} mode (read-only). "
                     "[SYSTEM SUGGESTION]: finish discovery, then call "
                     "ExitPlanMode to present your plan for approval before "
                     "making changes."),
            metadata={"blocked": True},
        )
    return None
```

`create_safe_wrapper`'s `wrapper` calls `_permission_gate` first; if it returns
a `ToolReturn`, that is returned instead of executing `func`. Same for
`SafeToolsetWrapper.call_tool`. This reuses the existing blocked-message shape
the model already understands and **does not touch** the
`DeferredToolRequests` / `_process_deferred_requests` machinery.

> The gate needs the tool name + capability at call time. `create_safe_wrapper`
> wraps `func`, whose `__name__` is the PascalCase tool name; capability comes
> from `tool_capability(func)`. For `SafeToolsetWrapper`, `name` is passed to
> `call_tool` and capability is looked up from the resolved tool. Both are
> available without new plumbing.

### Tools

```python
# zrb/llm/tool/plan_mode.py — pattern copied from tool/worktree.py
@tool_safe_async
async def enter_plan_mode(reason: str = "") -> str:
    """Switch to read-only PLAN mode: edits, shell, and delegation are blocked
    until ExitPlanMode is called. Use for discovery before risky changes."""
    current_agent_mode.set(AgentMode.PLAN)
    return "Entered PLAN mode (read-only). ..."

@tool_safe_async
async def exit_plan_mode(plan: str) -> str:
    """Present the completed plan and leave PLAN mode so execution can begin.
    `plan` is the concrete change list shown to the user for approval."""
    # Approval to leave plan mode is gated by the normal approval flow because
    # ExitPlanMode itself is a META tool the user can be asked to confirm.
    current_agent_mode.set(AgentMode.DEFAULT)
    return f"Plan presented; resuming DEFAULT mode.\n\n{plan}"

enter_plan_mode.__name__ = "EnterPlanMode"
exit_plan_mode.__name__ = "ExitPlanMode"
```

Both are tagged `META`, so they are always allowed (even inside plan mode — you
must be able to leave). They are registered in `common_tools.py` alongside the
worktree tools, and given tool guidance entries.

### Prompt surfacing

`system_context` already injects worktree path + pending todos live. Add a line
when mode is non-default:

```
Active mode: PLAN (read-only — edits/shell/delegation blocked; call ExitPlanMode
to present your plan and resume).
```

When mode is `DEFAULT`, **emit nothing** — the section is unchanged from today.
A short tool-guidance entry explains when to use Enter/ExitPlanMode.

### Entry points

- A `mode` / `plan` input on `LLMChatTask` (default `DEFAULT`) and a CLI flag,
  setting `current_agent_mode` before the run — symmetric with `yolo`.
- The model can also `EnterPlanMode` mid-conversation.

## Subagent propagation

`current_agent_mode` is a ContextVar; sub-agents inherit it the same way they
inherit yolo/policy. A plan-mode parent's delegate children are denied at spawn
because `DELEGATE` is denied in `PLAN_MODE_POLICY` — so a plan-mode session
cannot mutate via a child. (Belt and suspenders: the mode also propagates, so
even a manually-spawned child stays read-only.)

## Regression analysis

| Risk | Mitigation |
|------|------------|
| Mode defaults to something other than DEFAULT | ContextVar default is `DEFAULT`; `_permission_gate` returns `None` → no behavior change unless plan mode is explicitly entered. |
| Misclassifying a read tool as mutating → blocks discovery | Capability tags default UNKNOWN→deny *only in plan mode*; the known read tools are explicitly tagged READ. Tag list reviewed against `common_tools.py`. |
| Shell is dual-use | Denied in plan mode (conservative). Documented; rulesets (#2) can later allow specific safe commands. |
| Can't leave plan mode | Enter/ExitPlanMode are META → always allowed. |
| Touching the approval/deferred flow | Not touched — deny is a separate pre-execution short-circuit. |

## Tests (`test/llm/tool/test_plan_mode.py`, `test/llm/agent/test_permission_gate.py`)

- Default mode → gate denies nothing; a Write executes (parity).
- Plan mode → Write/RM/Bash/Delegate return blocked `ToolReturn`
  (`metadata["blocked"]`), func not called.
- Plan mode → Read/Glob/Grep/SearchInternet/WriteTodos execute normally.
- `EnterPlanMode` sets the ContextVar; `ExitPlanMode` clears it and echoes the
  plan; both runnable while in plan mode.
- `system_context` includes the mode line only when mode != DEFAULT.
- A spawned sub-agent observes the parent's plan mode (ContextVar inheritance).
