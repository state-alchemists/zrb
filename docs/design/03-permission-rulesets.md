# #2 — Permission rulesets

## What exists

Approval is binary-ish. `yolo` (`bool | frozenset[str] | Callable`) resolves
through one of two predicates:

- `LLMChatTask._create_llm_task_core.check_yolo(tool_def)` (`task/chat/task.py`)
  reads `ctx.xcom[yolo_xcom_key]` and returns auto-approve vs ask.
- `make_yolo_inheritance_checker()` (`agent/subagent/yolo.py`) for sub-agents,
  reading the live `current_yolo` ContextVar (+ UI fallback).

Both collapse to **auto-approve vs ask**. There is no per-argument matching and
no deny.

## Key insight

A ruleset is the *generalization* of `yolo`, and `yolo` is a degenerate
ruleset:

| `yolo` value | equivalent ruleset |
|--------------|--------------------|
| `True` | `[Rule("*", "allow")]` |
| `False` | `[Rule("*", "ask")]` |
| `frozenset({"Write"})` | `[Rule("Write", "allow"), Rule("*", "ask")]` |

So we implement a resolver and make the **existing predicates delegate to it**,
with the `policy is None` path hard-coded to reproduce today's truth table.
Because `check_approval` in `create_agent` already receives `args`, rules can
match on a salient argument (`Bash(command=...)`, `Edit(path=...)`) — the data
already flows, currently unused.

## Components

### `zrb/llm/permission/capability.py` (Primitive A)

`Capability` enum + `tool_capability(tool)` (see overview). Central tagging in
`common_tools.py` via a `tag()` helper.

### `zrb/llm/permission/policy.py` (Primitive B)

```python
@dataclass(frozen=True)
class Rule:
    capability_or_tool: str       # Capability value | tool name | "*"
    action: str                   # "allow" | "ask" | "deny"
    arg_pattern: str | None = None

@dataclass(frozen=True)
class PermissionPolicy:
    rules: tuple[Rule, ...]        # first match wins

    def decide(self, tool_name: str, capability: Capability,
               args: dict) -> str:
        for rule in self.rules:
            if not _key_matches(rule, tool_name, capability):
                continue
            if rule.arg_pattern and not _arg_matches(rule, args):
                continue
            return rule.action
        return "ask"               # conservative fallback

    @classmethod
    def from_yolo(cls, yolo) -> "PermissionPolicy | None":
        """Build the ruleset equivalent of a yolo value, or None to mean
        'use the legacy predicate unchanged'."""
```

`_key_matches` matches a rule key against an exact tool name, a capability
value, or `"*"`. `_arg_matches` globs `rule.arg_pattern` against the salient
arg (path-like or `command`). First match wins (opencode's model).

Helper to read user config / per-task param into a policy:

```python
def resolve_policy(raw) -> PermissionPolicy | None: ...
# raw: None | "allow"/"ask"/"deny" shorthand | list[dict] | PermissionPolicy
```

Config surface: `CFG.LLM_PERMISSIONS` (mixin) — default `None`. A per-task
`permissions` param on `LLMChatTask`/`LLMTask`, default `None`.

### Ambient state

```python
current_permission_policy: ContextVar[PermissionPolicy | None]
```

Set in `run_agent` next to `current_yolo` (same `token = var.set(...)` /
`var.reset(token)` discipline). Sub-agents read it live, exactly like yolo.

## Wiring (no signature changes)

1. `check_yolo` and `make_yolo_inheritance_checker`: at the top, read
   `current_permission_policy`. If `None`, run **today's logic unchanged**. If
   set, return `policy.decide(...) != "ask"` for the auto-approve boolean
   (`allow` → don't ask; `ask`/`deny` → defer to ask — `deny` is enforced
   separately in #1's execution wrapper, so here it conservatively asks, which
   is strictly safer than today and never auto-runs a denied tool).
2. `create_agent`: unchanged. It still receives a `yolo: bool | Callable`. The
   policy travels via the ContextVar, not a new parameter — keeping the public
   signature stable.
3. `run_agent`: accept an optional `permission_policy` arg (default `None`),
   set the ContextVar. When `None`, ContextVar stays `None` → legacy path.

## Subagent inheritance — a latent bug this closes

Today `make_yolo_inheritance_checker` propagates the parent's **yolo** to
children but **not** any edit restriction. With the policy in a ContextVar,
sub-agents inherit it automatically (they already read `current_yolo` the same
way). This is the mechanism opencode implements as
`deriveSubagentSessionPermission`. We document it as a fix, not just a feature.

## Regression analysis

| Risk | Mitigation |
|------|------------|
| Changing the `yolo` truth table | **Characterization test first** (below). `policy is None` path is the literal current code. |
| First-match ordering subtly wrong | Adopt opencode's exact order (specific before `*`, first match wins); unit-test the resolver in isolation. |
| `deny` leaking into the approval layer before #1's wrapper exists | In #2, `deny` is treated as `ask` by the predicate — strictly safer than today, never auto-runs. Hard-deny arrives with #1. |
| Sub-agent behavior change when no policy set | Inheritance checker's `policy is None` branch is the unchanged current code. |

## Tests

**Characterization (write first, `test/llm/agent/test_yolo_parity.py`):** assert
`PermissionPolicy.from_yolo(v)` + `decide` reproduces the current `check_yolo` /
inheritance outcomes for `True`, `False`, `frozenset({...})`, and the callable
case, across approve/ask decisions. This locks the truth table before wiring.

**Resolver (`test/llm/permission/test_policy.py`):**
- exact tool match wins over capability match wins over `"*"`.
- first matching rule wins; later rules ignored.
- `arg_pattern` glob matches/var on path and `command`.
- unmatched → `"ask"`.
- `from_yolo` mappings for all three yolo shapes.

**Integration:** `current_permission_policy=None` → existing yolo tests pass
unchanged (no edits to those tests).
