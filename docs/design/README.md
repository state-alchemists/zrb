# Agent-harness enhancements — design overview

This directory holds the design docs for six enhancements to the zrb LLM
harness, drawn from a comparison with opencode and gemini-cli:

| # | Feature | Doc | Risk |
|---|---------|-----|------|
| 6 | Tool-output truncation | [01-tool-output-truncation.md](01-tool-output-truncation.md) | very low |
| 3 | Dynamic permission-filtered tool descriptions | [02-dynamic-tool-descriptions.md](02-dynamic-tool-descriptions.md) | very low |
| 2 | Permission rulesets | [03-permission-rulesets.md](03-permission-rulesets.md) | medium |
| 1 | Plan mode | [04-plan-mode.md](04-plan-mode.md) | medium |
| 5 | Progress-narration tool | *(removed — see Revisions)* | low |
| 4 | Background subagents | [06-background-subagents.md](06-background-subagents.md) | high |

## Post-review revisions

After implementation, a tool-surface review trimmed the agent's tool count
(~40 → ~30 in the typical case) with no capability loss:

- **#5 Progress-narration — removed.** No UI renders the `kind="progress"`
  channel specially, so the tool added nothing over the model's normal prose
  "update at key moments" narration. `tool/progress.py` deleted.
- **Delegation — `DelegateToAgentsParallel` removed.** Kept `DelegateToAgent`
  (sync) and `DelegateToAgentBackground` + `GetDelegationResult`; fan-out is
  achieved by starting several background agents. See
  [06-background-subagents.md](06-background-subagents.md).
- **Background confirmation — inherit & interrupt.** A background sub-agent
  inherits the main agent's permissions; when a tool needs approval it
  interrupts the UI and prompts the user via the existing concurrent-confirmation
  queue (the same path foreground delegates use). Earlier fail-closed (denied
  everything → useless) and auto-approve (exceeded the parent's permissions)
  iterations were both wrong. See 06's "Confirmation" section.
- **Todos collapsed 4 → 2.** Only `WriteTodos` (replace-by-default) and
  `GetTodos` are exposed; `UpdateTodo`/`ClearTodos` are subsumed (rewrite the
  list / write `[]`) and remain importable for direct use only.
- **LSP made conditional.** The 8 LSP tools register only when
  `detect_available_lsp_servers()` finds an installed server (cheap
  `shutil.which` scan); otherwise they're omitted, since their own guidance
  already says to fall back to Read + Grep.
- **Kept as-is:** AnalyzeFile / AnalyzeCode (LSP-less fallback), LS + Glob.

They are implemented in **risk-ascending order** (the order above), so each
later, riskier change can build on primitives the earlier ones introduce.

## The non-negotiable invariant: default-off

**Every new behavior is reachable only when a new, explicitly-set switch is
on.** With all switches at their defaults, `create_agent` and `run_agent` must
produce behavior identical to today. Concretely:

- No permission policy configured → approval resolves exactly as the current
  `yolo` truth table (`bool | frozenset[str] | Callable`).
- Mode unset / `"default"` → no tool is denied; the working loop is prose-only
  guidance as it is now.
- Output cap disabled (or output below the cap) → tool results pass through
  byte-for-byte.
- Background / narration tools are *additional* tools; existing tools and the
  synchronous delegate path are untouched.

The guard for the riskiest parity claim (the `yolo` truth table) is a
**characterization test** written *before* the permission resolver is wired in
— see [03-permission-rulesets.md](03-permission-rulesets.md).

## Two shared primitives

Five of the six features lean on two new primitives. They are introduced once,
here, and reused.

### Primitive A — tool capability tags

zrb tools are bare callables identified only by `__name__`. The only existing
classifier is the ad-hoc `zrb_is_delegate_tool` attribute (set in
`tool/delegate.py`, read in `agent/subagent/manager/manager.py`). We generalize
that exact pattern: an **optional attribute** naming a tool's capability.

```python
# zrb/llm/permission/capability.py
class Capability(str, Enum):
    READ = "read"        # pure reads: Read, LS, Glob, Grep, AnalyzeCode/File, ListWorktrees, SearchJournal
    EDIT = "edit"        # filesystem mutation: Write, Edit, RM, MV, EnterWorktree, ExitWorktree
    EXECUTE = "execute"  # arbitrary side effects: Bash, RunZrbTask
    NETWORK = "network"  # outbound network: SearchInternet, OpenWebPage
    DELEGATE = "delegate"# spawns sub-agents: DelegateToAgent[sParallel], ...Background
    META = "meta"        # harness control, no external effect: WriteTodos, ActivateSkill, AskUserQuestion, UpdateProgress, Enter/ExitPlanMode

def tool_capability(tool) -> Capability:
    """Best-effort capability of a tool; UNKNOWN tools default to the most
    conservative *safe* answer for the asking layer (see below)."""
```

**Defaults and regression safety.** A tool with no tag is `UNKNOWN`. Each
consuming layer chooses how to treat `UNKNOWN`:

- The **truncation** layer ignores capability entirely.
- The **plan-mode deny** layer treats `UNKNOWN` as *mutating* (deny in
  read-only mode) — conservative; never silently runs something destructive in
  a "read-only" phase. This is the only place `UNKNOWN` is treated as unsafe,
  and it only matters once plan mode is explicitly entered.
- The **ruleset** layer treats an unmatched tool by its `"*"` rule, whose
  default is `allow`/`ask` exactly mirroring today.

Tags are attached centrally where tools are registered (`common_tools.py`) via
a small `tag(fn, Capability.X)` helper, so untagged third-party / MCP tools
keep working unchanged.

### Primitive B — permission policy + ambient state

The current approval seam already does most of the work. In
`agent/common.py::create_agent`, `yolo` is converted to a per-tool predicate:

```python
def check_approval(ctx, tool_def, args) -> bool:   # True == needs approval
    return not yolo(tool_def)
effective_toolsets = [ts.approval_required(check_approval) for ts in ...]
```

`check_approval` **already receives `args`** — only the public `yolo` callable
is narrowed to `(tool_def)`. So a richer policy can be layered *inside* the
predicate without changing `create_agent`'s public `yolo: bool | Callable`
contract.

The approval system has exactly two outcomes today: **auto-run** or **ask the
user** (the `DeferredToolRequests` → `_process_deferred_requests` path). It has
no hard-**deny**. We add deny without touching that machinery:

```
                       ┌─────────────────────────────────────────┐
   tool call  ─────────▶  PermissionPolicy.decide(tool, args)     │
                       └───────────────┬─────────────────────────┘
                              allow / ask / deny
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           ▼                            ▼                           ▼
   approval predicate           approval predicate          execution wrapper
   returns "don't ask"          returns "ask user"          short-circuits with
   (existing path)              (existing DeferredTool path) a [SYSTEM SUGGESTION]
```

- `allow` vs `ask` is resolved by the **existing** approval predicate — zero
  change to the deferred-request flow.
- `deny` is enforced by a thin **execution wrapper** that reads the policy from
  a ContextVar and returns a blocked-message `ToolReturn` instead of running —
  additive, modeled on `active_worktree` in `tool/worktree.py`.

```python
# zrb/llm/permission/policy.py
@dataclass(frozen=True)
class Rule:
    capability_or_tool: str   # a Capability value, a tool name, or "*"
    action: str               # "allow" | "ask" | "deny"
    arg_pattern: str | None = None  # optional glob on a salient arg (path/command)

@dataclass(frozen=True)
class PermissionPolicy:
    rules: tuple[Rule, ...]            # first match wins
    def decide(self, tool_name, capability, args) -> str: ...

# ambient, scoped exactly like current_yolo:
current_permission_policy: ContextVar[PermissionPolicy | None] = ContextVar(
    "current_permission_policy", default=None
)
```

When `current_permission_policy` is `None` (the default), the approval predicate
falls back to the **unchanged** `yolo` logic and the execution wrapper denies
nothing. This is the mechanism that keeps the default-off invariant true.

## How the features compose

```
#6 truncation ──────────────── independent, no primitives
#3 descriptions ───── reads Primitive A (capability) + B (policy), filter-only
#2 rulesets ───────── defines Primitive A + B; reproduces yolo when policy=None
#1 plan mode ──────── a preset PermissionPolicy + Enter/ExitPlanMode + mode line
#5 narration ──────── independent additive tool (META capability)
#4 background ─────── new tools; inherit Primitive B policy via snapshot
```

## Testing posture

- Public API only (per `AGENTS.md`): test `create_agent`, the policy resolver,
  the tool wrappers' observable returns, and the new tools' returns — never
  `_private` members.
- Each feature adds tests to the relevant existing `test/` mirror file; no
  `_extra` / `_coverage` sibling files.
- Coverage target ≥ 90%; `flake8 src/zrb --select=F` clean.
- The cross-cutting guard is the `yolo`-parity characterization test in #2.
