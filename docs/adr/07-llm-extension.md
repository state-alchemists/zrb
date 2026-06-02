# LLM extension surface

Tools, skills, sub-agents, hooks, MCP, and the permission/mode layer. See the
[ADR index](README.md) for format and tags. Builds on ADR-0034 (pydantic-ai)
and ADR-0035 (prompt sections).

---

## ADR-0041 — Tools as plain functions with PascalCase `__name__`

**Status:** Accepted

**Context.** pydantic-ai derives a tool's schema name from the function's
`__name__`, but zrb's Python convention is snake_case while the LLM-facing
convention (matching Claude/Gemini) is PascalCase.

**Decision.** Built-in tools are ordinary functions whose `__name__` is
explicitly reassigned to PascalCase (`read_file.__name__ = "Read"`,
`run_shell_command.__name__ = "Bash"`). The reassigned name is the single control
point for the LLM-visible identity and the capability/guidance lookup key.

**Consequences.** Clean Python identifiers, familiar tool names for the model,
no wrapper objects. Cost: the name lives in two places (def + reassignment) —
a convention to remember.

**Alternatives rejected.** Wrapper/class tools (indirection; most tools are plain
functions); inferring PascalCase from snake_case (loses control, error-prone).

**Evidence.** **[DOCUMENTED]** every file in `src/zrb/llm/tool/` reassigns
`__name__`; `agent/common.py` uses `func.__name__` as the key.

---

## ADR-0042 — `tool_safe_async` + `[SYSTEM SUGGESTION]` error hints

**Status:** Accepted

**Context.** An unhandled tool exception would dump a traceback into the model's
context and could crash the loop; raw errors rarely tell the model how to
recover.

**Decision.** Tools are wrapped so exceptions become a concise error string,
optionally suffixed with an actionable `[SYSTEM SUGGESTION]: …` hint
(`tool_safe_async`, plus the global wrap in `agent/common.py`).

**Consequences.** Failures are self-describing and recoverable; no tracebacks
leak; the loop survives tool errors. Cost: tool authors should write good hints
for the guidance to pay off.

**Alternatives rejected.** Strict schema validation only (misses runtime
failures); silent failure (loses diagnostics).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/tool/wrapper.py`, `AGENTS.md` ("LLM
tool errors include a `[SYSTEM SUGGESTION]` prefix").

---

## ADR-0043 — Explicit tool-guidance registration + runtime filtering

**Status:** Accepted

**Context.** Per-tool "when to use / key rule" guidance is valuable but
token-expensive, and some tool names are computed from config
(`List<RootGroup>Tasks`).

**Decision.** Guidance is registered explicitly via `add_tool_guidance()` (static
entries + factories for config-dependent names) — there is no auto-derived
catalogue. At render time, guidance is filtered to the *resolved* tool surface,
so the model only reads instructions for tools it actually has.

**Consequences.** Lean prompts; sub-agents don't see guidance for tools they
lack; dynamic names stay correct. Cost: adding a tool means also registering its
guidance (and, for factory-named tools, registering explicitly so the name
filter doesn't drop it).

**Alternatives rejected.** Auto-extract from docstrings (docstrings are
user-facing, not policy); static catalogue (misses config-named tools);
always-render-all (token waste, confuses the model).

**Evidence.** **[DOCUMENTED]** `AGENTS.md` (Configuring Tool Guidance),
`src/zrb/llm/prompt/tool_guidance.py` (name filter), `common_tools.py`
(static + factory registration).

---

## ADR-0044 — Claude-compatible skills (`SKILL.md`/`.py`) + companion files

**Status:** Accepted

**Context.** Reusable domain expertise should be portable with Claude Code's
ecosystem and able to bundle scripts/data alongside instructions.

**Decision.** Skills are `SKILL.md` (YAML frontmatter + body) or `SKILL.py`,
matching Claude's format. They are listed as metadata and loaded in full on
demand via `ActivateSkill`. Companion files in the skill's directory are
auto-discovered and surfaced so the skill can ship scripts/templates/refs.

**Consequences.** Direct portability with Claude setups; self-contained skill
bundles; lazy loading keeps context lean. Cost: a discovery/precedence model to
understand (see ADR-0030).

**Alternatives rejected.** Hardcoded tool list per skill (drifts out of sync);
flat files with no companion discovery (awkward multi-asset skills); a rigid
mandated directory layout (too inflexible).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/claude-compatibility.md`
(SKILL format + companions). **[INFERRED]** `src/zrb/llm/skill/`,
`src/zrb/llm/tool/skill.py`, `src/zrb/llm_plugin/skills/`.

---

## ADR-0045 — Subagent scope-clamp envelope + section inheritance

**Status:** Accepted

**Context.** Delegation's main failure mode is scope creep — a sub-agent
over-produces against a fuzzy brief — and repeating persona/mandate in every
agent definition is wasteful.

**Decision.** `DelegateToAgent` sends a structured envelope with uppercase,
unmissable delimiters — `DELIVERABLE`, `NON-GOALS`, `TASK`, `CONTEXT`, and a
`BEFORE RETURNING` self-check — forcing the delegator to name concrete artifacts
and adjacent work to avoid. Agent definitions (`*.agent.md`) declare
`inherit-sections` to reuse parent prompt sections while specializing their own
body.

**Consequences.** Tight, auditable delegation briefs; agents share persona/rules
without duplication. Cost: the delegator must articulate deliverable/non-goals
(deliberate friction).

**Alternatives rejected.** Prose-only scope (models expand into adjacent work);
hardcoding all sections per agent (no reuse); no envelope (vague scope doesn't
scale).

**Evidence.** **[DOCUMENTED]** agent definitions in `src/zrb/llm_plugin/agents/`
(`inherit-sections`). **[INFERRED]** `src/zrb/llm/tool/delegate.py`
(`_format_envelope`), `agent/subagent/manager/`.

---

## ADR-0046 — `BufferedUI` + confirmation queue for concurrent agents

**Status:** Accepted

**Context.** Multiple sub-agents (parallel or background) share one terminal UI;
their output and approval prompts must not interleave or deadlock.

**Decision.** Each sub-agent runs behind a `BufferedUI` that buffers output and
forwards approval requests to the parent UI under a lock. The default UI's
`ask_user` is itself a **confirmation queue**: concurrent callers each wait their
turn, and the prompt shows only when a request becomes current.

**Consequences.** Readable, serialized interaction across concurrent agents; the
same machinery powers both foreground parallel delegates and background agents
(ADR-0054). Cost: a sub-agent's buffered output appears at flush/approval/
completion points, not strictly live.

**Alternatives rejected.** No buffering (interleaved, unreadable output);
disallow concurrency (kills the feature); per-agent output files (separate
polling UI).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/ui/default/confirmation_mixin.py`
(queue docstring), `src/zrb/llm/tool/delegate.py` (`BufferedUI`).

---

## ADR-0047 — Lifecycle hooks (Claude-compatible)

**Status:** Accepted

**Context.** Cross-cutting concerns (audit, approval gates, command rewriting,
notifications) shouldn't be hardcoded into the agent loop or per tool.

**Decision.** Hooks fire at lifecycle events (`PreToolUse`, `PostToolUse`,
`SessionStart/End`, `UserPromptSubmit`, `PreCompact`, zrb-specific
`Pre/PostCommand`, …) and can allow / ask / block, or mutate state (e.g., rewrite
tool args). Hook types include shell `command`, LLM `prompt`, and multi-step
`agent`. Config is Claude-Code-compatible.

**Consequences.** Decoupled, configurable governance without code changes;
non-programmers can add gates. Cost: another extension surface and event
contract to learn.

**Alternatives rejected.** Hardcode approval logic (tight coupling); per-tool
middleware (scales poorly); code-only hooks (excludes non-programmers).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/hooks.md`,
`claude-compatibility.md`. **[INFERRED]** `src/zrb/llm/hook/`.

---

## ADR-0048 — MCP (Model Context Protocol) support

**Status:** Accepted

**Context.** A growing ecosystem of MCP servers already exposes useful tools;
reimplementing them would be wasteful.

**Decision.** Load MCP server configs (`mcp-config.json`, Claude-Desktop format)
discovered cwd→home (project overrides home); spawn stdio servers or call
SSE/HTTP ones; wrap their tools with the same safety/truncation/permission layer
as built-in tools.

**Consequences.** Reuse the MCP ecosystem; MCP tools behave consistently with
native ones. Cost: external server processes and their failure modes enter the
loop.

**Alternatives rejected.** Proprietary server spec (incompatible, misses existing
tools); Python-only manual registration (less discoverable); unwrapped MCP tools
(inconsistent error handling).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/mcp-support.md`.
**[INFERRED]** `src/zrb/llm/tool/mcp.py`, `agent/common.py` (`SafeToolsetWrapper`).

---

## ADR-0049 — Tool capability tags (Primitive A)

**Status:** Accepted

**Context.** Plan mode and permission rules need to reason about what a tool
*does* (read vs mutate vs network vs delegate), but zrb tools are bare functions
with no such metadata — only the ad-hoc `zrb_is_delegate_tool` attribute existed.

**Decision.** Generalize that pattern: an optional `zrb_capability` tag
(`READ | EDIT | EXECUTE | NETWORK | DELEGATE | META | UNKNOWN`) on the tool,
applied centrally in `common_tools.py`. Untagged tools resolve to `UNKNOWN`;
each consumer chooses how to treat unknown (the plan-mode gate denies it — safe;
the ruleset matches it via `*`). `DELEGATE` is inferred from the legacy delegate
attribute.

**Consequences.** Fine-grained policy without touching tool signatures; untagged
third-party/MCP tools keep working (conservatively). Cost: built-in tools must be
tagged for accurate behavior.

**Alternatives rejected.** Naming-convention inference (fragile); a parallel
registration file (drifts); docstring parsing (fragile, wrong audience).

**Evidence.** `src/zrb/llm/permission/capability.py`, `common_tools.py` (central
tagging), `agent/common.py` (`tool_capability` lookup).

---

## ADR-0050 — Permission rulesets (Primitive B)

**Status:** Accepted

**Context.** Approval was effectively binary (`yolo` = auto-approve vs ask), with
no hard-deny and no per-argument granularity.

**Decision.** A `PermissionPolicy` is an ordered list of `Rule`s
(`key` = tool name | capability | `*`; `action` = allow | ask | deny; optional
`arg_pattern` glob), evaluated first-match-wins. It is the generalization of
`yolo` (`from_yolo()` expresses the legacy values as rules, characterization-
tested for parity). The policy travels via a `current_permission_policy`
ContextVar; `allow`/`ask` resolve in the existing approval predicate, while
`deny` is enforced by a pre-execution gate in the tool wrapper. **Default
(no policy) reproduces today's `yolo` behavior exactly.**

**Consequences.** Expressive, testable, per-argument permissions; closes a latent
gap where sub-agents didn't inherit edit restrictions. Cost: a policy model and
resolver to maintain.

**Alternatives rejected.** Deny-list only (scales poorly); capability-only (too
coarse for `Bash`); docstring-derived rules (fragile).

**Evidence.** `src/zrb/llm/permission/policy.py`, `permission/state.py`,
`agent/common.py` (`_permission_gate`); parity test
`test/llm/permission/test_policy.py`.

---

## ADR-0051 — Plan mode (read-only discovery)

**Status:** Accepted

**Context.** The mandate's "investigate before you change" loop was prose only —
nothing prevented edits during discovery.

**Decision.** Plan mode is a preset `PermissionPolicy` (READ/NETWORK/META allow;
EDIT/EXECUTE/DELEGATE deny; unknown→deny) selected by a `current_agent_mode`
ContextVar, with `EnterPlanMode`/`ExitPlanMode` tools (tagged `META`, so always
permitted) and a system-context line when active. The same execution gate
(ADR-0050) enforces the denials. Default mode is `DEFAULT` → no-op.

**Consequences.** Enforced read-only discovery the model (or a CLI flag) can
toggle; sub-agents can't mutate from a plan-mode parent (DELEGATE denied). Cost:
shell is dual-use and conservatively denied in plan mode.

**Alternatives rejected.** Hardcoded read-only mode in the runner (no per-tool
overrides); require manual permission rules each time (verbose); no toggle tools
(must restart the session).

**Evidence.** `src/zrb/llm/permission/policy.py` (`PLAN_MODE_POLICY`),
`tool/plan_mode.py`, `prompt/system_context.py`.

---

## ADR-0052 — Tool-output truncation backstop

**Status:** Accepted

**Context.** Only `Read`/`Bash` capped their own output; Grep, AnalyzeCode, web,
and MCP results were uncapped, so a huge result could flood the context window.

**Decision.** A global, deterministic cap (`CFG.LLM_MAX_TOOL_RESULT_CHARS`,
default 100k; `0` disables) applied in the tool wrappers, truncating the
model-facing `content` (head+tail with a re-fetch hint) while leaving the
structured `return_value` whole. A typical result is under the cap and untouched.

**Consequences.** Pathological outputs no longer degrade the model; programmatic
consumers still get full data. Cost: above the cap, the model sees a truncated
view and must narrow its query.

**Alternatives rejected.** Chunked streaming (runner surgery); per-tool caps
(every tool differs); no cap (latent context-flooding bug).

**Evidence.** `src/zrb/llm/agent/truncate.py`, `agent/common.py`
(wrapper integration), `config/mixins/llm_limits.py`.

---

## ADR-0053 — Dynamic, permission-filtered tool descriptions

**Status:** Accepted

**Context.** `DelegateToAgent` advertises the available agents in its docstring,
but a permission policy could forbid delegating to some of them — leaving the
model offered options it can't use.

**Decision.** The delegate tool's agent roster is built per run (factories
already rebuild each turn) and filtered by the active policy; with no policy
(default) the full roster is shown, byte-identical to before.

**Consequences.** The advertised roster matches what's actually permitted; zero
change when no policy is set. Cost: a small coupling of `delegate.py` to the
permission module.

**Alternatives rejected.** Static catalogue (stale); suppress the whole list when
any policy is set (loses context); no filtering (confusing).

**Evidence.** `src/zrb/llm/tool/delegate.py` (`_delegatable_agents`).

---

## ADR-0054 — Background subagents: inherit permissions and interrupt to ask

**Status:** Accepted (after two rejected iterations — recorded below)

**Context.** Long, independent work (research, file generation) shouldn't block
the main agent. But a detached agent has no obvious way to get tool approval,
since the synchronous approval model assumes the *parent blocks* while the UI is
free.

**Decision.** `DelegateToAgentBackground` spawns a detached `asyncio` task and
returns a handle immediately; `GetDelegationResult(handle)` polls (model-driven,
no lifecycle surgery). The task copies the spawning context, so it **inherits the
main agent's permissions** (policy, yolo, approval channel, UI). When a tool
needs approval, its `BufferedUI` forwards to the parent UI's confirmation queue
(ADR-0046), which **interrupts and prompts the user** — exactly like a
synchronous delegate. Fan-out = start several background agents.

**Consequences.** Non-blocking delegation that neither auto-approves nor silently
denies; approvals reach the user. Cost: results aren't durable across process
restart; if the main agent stops polling before the user answers, the agent
parks on the prompt until answered (model-pacing, not a bug).

**Rejected iterations (kept as record).**
1. **Fail-closed** — auto-deny anything not pre-approved. Made the feature
   useless: a "write a poem" delegation had `Write`, then `Bash`, then `echo`
   denied; the agent gave up empty-handed.
2. **Auto-approve (`yolo=True`)** — worked, but granted the sub-agent *more*
   permission than a non-yolo parent has. Rejected: a sub-agent must not exceed
   its parent. The correct design inherits and routes to the existing queue.

**Alternatives rejected.** Push-notification on completion (requires injecting
results into a future turn — lifecycle surgery); true in-call async (pervasive
refactor of the per-turn synchronous model).

**Evidence.** `src/zrb/llm/tool/delegate_background.py`,
`ui/default/confirmation_mixin.py` (queue), `tool/delegate.py` (`BufferedUI`).
Verified working in an interactive session.

---

## ADR-0055 — Approval precedence: permission policy → tool policy → yolo

**Status:** Accepted

**Context.** Three authorization mechanisms accumulated in the codebase with
overlapping and sometimes contradictory logic:

1. **Permission policy** (`LLM_PERMISSIONS`) — system-configured rules returning
   `allow` | `ask` | `deny` per tool/capability/argument, evaluated first-match-wins.
2. **Tool policy** — programmatic rules registered via `add_tool_policy()`:
   `auto_approve("Tool")`, `bash_safe_command_policy`, validation handlers.
3. **Yolo** — session-level toggle (`True` = skip prompts, `False` = prompt,
   `frozenset` = prompt except listed tools).

The current (`origin/main`) implementation evaluated them in an ad-hoc order:
permission policy in `check_yolo` (which maps `allow`→auto-approve,
`ask`/`deny`→defer); tool policy in the approval cascade
(`process_deferred_requests` → `_resolve_approval`); and yolo as a fallback
predicate. The execution gate (`_permission_gate`) caught `deny` after the
cascade, causing wasted prompts for denied tools. The new diff on the branch
introduced `check_yolo` changes that gave permission policy *per-tool* priority
over yolo (`ask` → not auto-approved even if `yolo=True`), but the `check_yolo`
callable was only wired in `LLMChatTask` — bare `LLMTask` with `yolo=True`
bypassed it entirely, creating an inconsistency between the two task classes.

**Decision.** A single, flat delegation chain:

```
perm_policy ──allow──→ ✅ auto-approved
            ├─deny───→ 🚫 blocked (execution gate, always)
            └─ask────→ tool_policy
                         ├─allow──→ ✅ auto-approved
                         ├─deny───→ 🚫 blocked
                         └─ask────→ yolo
                                      ├─True──→ ✅ auto-approved
                                      └─False──→ ❓ prompt user
```

For background subagents the chain short-circuits at the yolo level:

```
background ──perm_policy──deny──→ 🚫 blocked
            └─anything else──────→ ✅ auto-approved (yolo=True)
```

Background agents auto-approve all tool calls (yolo always True) so they never
block the main agent. Deny rules in the permission policy still block at the
execution gate.

Each level asks three questions in order:

1. Does this level have a rule for this tool? If `allow` → done (approved).
   If `deny` → done (blocked).
2. If `ask` (or no rule) → delegate to the next level.
3. Bottom (yolo `False`) → prompt user.

Semantics per mechanism:

- **Permission policy `deny`** — hard block, enforced at execution time by
  `_permission_gate`. Cannot be overridden by any lower level. Purpose: admin
  safety boundary (e.g., `edit:deny` in plan mode, `Bash:*:deny`).
- **Permission policy `allow`** — unconditional bypass of all lower checks.
  Purpose: known-safe tools that should never prompt.
- **Permission policy `ask`** — "I have no opinion on this tool; check
  tool-level rules." Same semantics as no rule (the default).
- **Tool policy `allow`** — tool-level override (e.g., `auto_approve("Read")`).
- **Tool policy `deny`** — tool-level block (e.g., validation failure).
- **Tool policy `ask`** — delegate to yolo. Same as no tool policy.
- **Yolo `True`** — auto-approve everything that reaches this level.
- **Yolo `False`** — prompt user.

Under this chain, `LLMChatTask` and bare `LLMTask` converge: both resolve the
chain identically — `LLMChatTask` via `check_yolo` in `chat/task.py`,
`LLMTask` via a default policy-aware callable in `llm_task.py`.

**Validation tool policies** (`bash_safe_command_policy`,
`replace_in_file_validation_policy`) run at execution time, orthogonal to the
approval chain. They are argument-level technical checks, not policy decisions.
A validation failure returns a `[SYSTEM SUGGESTION]` hint. They block even
when the permission policy says `allow` (e.g., `read_file_validation_policy`
rejects paths outside the worktree regardless of `LLM_PERMISSIONS=read:allow`).

**Consequences.** A single, predictable decision path; no wasted prompts
(deny stops at the permission gate before the cascade); yolo controls only
the last-resort default (prompt vs skip). Validation always runs, regardless
of the approval chain. Background agents never block the main agent for
approval. Cost: some existing tool-policy rules that assumed they ran *before*
the permission layer now come second; validation-only tool policies must be
registered as execution-time handlers, not approval handlers.

**Alternatives rejected.**
1. **Flat last-match-wins (openCode model):** permission, tool, and yolo rules
   merged into a single ruleset with `findLast`. Rejected because it conflates
   different-authority rules (admin vs code vs session) into one namespace,
   making audit harder (who set this rule?).
2. **Yolo overrides permission policy entirely:** `yolo=True` would bypass
   permission `deny`. Rejected: `deny` is the admin's safety boundary and
   must be absolute. The accepted Model B (yolo overrides `ask` only) preserves
   this.
3. **Permission policy `ask` = prompt immediately** (no delegation to tool
   policy): too rigid; tool policies like `auto_approve("Read")` would be
   skipped whenever the permission policy says `ask` (or has no rule).

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/task/chat/task.py` (`check_yolo`
closure — perm_policy → yolo cascade); `src/zrb/llm/agent/subagent/yolo.py`
(`check_yolo_inheritance` — same cascade for sub-agents);
`src/zrb/llm/task/llm_task.py` (`_create_agent` — default policy-aware
callable for bare LLMTask); `src/zrb/llm/agent/run/deferred_calls.py`
(`_resolve_approval` — denials before prompting, yolo shortcut, tool-policy
layer); `src/zrb/llm/tool/delegate_background.py` (passes `yolo=True`).
**[INFERRED]** `src/zrb/llm/agent/common.py` (`_permission_gate` enforces
deny at execution time).

---

## ADR-0056 — Shell as primary execution tool, Bash as backward-compat alias

**Status:** Accepted

**Context.** The `Bash` tool (`run_shell_command`) was zrb's only shell execution
tool, but its name and docstring were Claude/ChatGPT-specific — the model's
strong prior for "Bash" is a Bourne-again shell on Linux, while the tool
actually ran any command the host shell supported. The name also carried no
semantic distinction between interactive and background execution, and the
single monolithic function mixed concerns (streaming, truncation, timeout,
approval).

**Decision.** Three-way decomposition:

1. **`Shell`** (`shell.py`) — the primary execution tool. Takes `command`, `cwd`,
   `timeout`, and truncation params. Streams stdout/stderr live and returns
   truncated output. Named generically so it works regardless of the host shell
   (bash, zsh, PowerShell, cmd).
2. **`Bash`** (`bash.py`) — reduced to a thin backward-compat alias that imports
   and re-exports `run_shell_command` from `shell.py` under `__name__ = "Bash"`.
   The model sees Bash and Shell as separate tools; both resolve to the same
   implementation, so existing agent conversations that call `Bash` keep working.
3. **`ShellBackground`** (`shell_background.py`) — non-blocking variant that
   returns a handle; `GetDelegationResult(handle)` polls for completion. Shares
   the same execution core but runs in a background task and routes approval
   through the confirmation queue (ADR-0054).

The capabilities are: `Bash` → `EXECUTE`, `Shell` → `EXECUTE`,
`ShellBackground` → `EXECUTE`.

**Consequences.** Clear naming that matches the model's expectations regardless
of host OS; backward compatibility via the alias; background execution gets its
own tool rather than an ad-hoc parameter. Cost: the model sees two tools
(Bash + Shell) that do the same thing, which may cause redundant choices —
mitigated by tool guidance that clarifies "Bash is an alias; prefer Shell."

**Alternatives rejected.**
1. **Rename Bash in-place** — would break existing agent sessions mid-conversation
   (the model's prior turn mentioned `Bash`; the next turn would get
   `ToolUnknownError`).
2. **Single tool with a `background` parameter** — pydantic-ai's tool schema
   can't express "call this, get a handle, call that to poll" as one tool; the
   polling pattern needs a separate tool.
3. **Keep Bash as-is** — the name mismatch persists; no background execution path.

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/tool/shell.py` (new primary
implementation, 281 lines); `src/zrb/llm/tool/bash.py` (alias, 10 lines);
`src/zrb/llm/tool/shell_background.py` (background variant, 204 lines);
`common_tools.py` (Bash/Shell/ShellBackground capability tags + guidance).
`test/llm/tool/test_bash.py` (alias assertions);
`test/llm/tool/test_shell.py` (19 lines);
`test/llm/tool/test_shell_background.py` (79 lines).
