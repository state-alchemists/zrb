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

---

## ADR-0057 — Post-todo-change progress visualization in the UI

**Status:** Accepted

**Context.** After every `WriteTodos`, `UpdateTodo`, or `ClearTodos` call, the
user has no immediate visual feedback about overall todo progress — the tool
result is consumed by the LLM and shown only as a terse `🔠 Executed` in the
stream. Users reported wanting a persistent sense of progress (how many done,
how many left) displayed directly in the UI alongside the conversation.

The system already has:
- A `current_ui` ContextVar wired by `run_agent` that tool functions can read
- Three UI backends (terminal TUI, StdUI, web UI) all implementing `append_to_output()` with a `kind` discriminator
- An SSE streaming protocol that passes `{"type": kind, "text": text}` to the web frontend

**Decision.** Tool functions that modify the todo list (`write_todos`,
`update_todo`, `clear_todos`) will push a progress visualization to the active
UI via a **side channel** — a separate `append_to_output()` call using kind
`"todo_progress"` — *in addition to* returning their normal text result to the
LLM. This keeps the LLM-visible contract unchanged.

The visualization:
- **Terminal TUI** (`OutputMixin`): rendered at full opacity (same as `"text"` kind — `stylize_faint` is skipped for `"todo_progress"`)
- **StdUI**: same full-opacity rendering on stderr
- **Web UI**: new handler in `chat.js` for kind `"todo_progress"` that renders a styled card with progress bar and full todo item list

The formatted text shows:
1. A **change description** line (e.g. "▶️ [1] Fix login bug → in_progress")
2. The **full todo list** with per-item status icons (✅/▶️/☐)
3. A `~DATA~` line with JSON payload for the web frontend stats

**Consequences.**
- *Good.* Users see immediate, persistent progress feedback after every todo
  state change, in all three UI backends.
- *Good.* Tool return values are unchanged; the LLM sees exactly the same text.
- *Good.* Zero changes to the tool confirmation, permission, or auto-approval
  pipelines — the visualization is fire-and-forget via `current_ui`.
- *Cost.* The `current_ui` import must be lazy (`# lazy: circular`) to avoid
  circular imports between `plan.py` and `runner.py`.
- *Cost.* The `~DATA~` marker adds a small structural convention that readers
  of the tool output must know about.
- *Cost.* Both `OutputMixin` and `StdUI` need a one-line exclusion for the
  `"todo_progress"` kind to avoid the `stylize_faint` that normally applies to
  non-`"text"` kinds.

**Alternatives rejected.**
1. **Embed progress in tool return value only** — the LLM already sees it, but
   the stream only shows `🔠 Executed`; the user never sees the progress.
2. **Hook into the tool-confirmation pipeline** — todo tools are auto-approved;
   adding a post-approval hook adds ceremony for no benefit.
3. **Dedicated SSE event type** — over-engineering for structured data that
   fits in a single `~DATA~` line alongside human-readable text.
4. **UI polls TodoManager periodically** — wrong abstraction; the UI shouldn't
   know about todo state or poll interval.

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/tool/plan.py` (side-channel calls);
`src/zrb/llm/agent/run/runtime_state.py::get_current_ui` (typed accessor);
`src/zrb/llm/ui/default/output_mixin.py::append_to_output` (kind dispatch);
`src/zrb/runner/web_route/chat_page/chat.js` (SSE `todo_progress` handler);
`src/zrb/llm/util/stream_response.py::PrintKind` (type union).

## ADR-0060 — `BaseUI` composed from concern mixins (shared-`self` contract)

**Status:** Accepted

**Context.** `BaseUI` had grown into a god-object: `ui.py` was ~1019 lines and
its slash-command companion `commands_mixin.py` ~907 lines, each mixing several
unrelated concerns (history replay, system-info status, and a dozen command
handlers alongside the dispatch core). Two constraints made a "clean"
decomposition into separate collaborator objects costly: (1) `BaseUI` /
`SimpleUI` / `EventDrivenUI` constructors and method surface are **public API**
— users subclass them (see `docs/advanced-topics/llm-custom-ui.md`); (2) the
test suite couples tightly to `BaseUI` internals (~150 accesses to private
attributes/methods such as `_history_manager`, `_handle_save_command`,
`_submit_user_message`). Moving state onto separate objects would change the
constructor signature and break that surface.

**Decision.** Decompose by **mixin composition on a shared `self`**, not by
extracting collaborator objects. Cohesive method clusters move into focused
mixin classes that the concrete UI composes via inheritance; every attribute
and method still lives on the one composed instance. The split:

- `replay_mixin.py::HistoryReplayMixin` — `_replay_*` history rendering.
- `system_info_mixin.py::SystemInfoMixin` — cwd/git status + refresh loop.
- `conversation_commands_mixin.py::ConversationCommandsMixin` — exit/info/
  save/load/rewind/redirect/attach.
- `model_commands_mixin.py::ModelCommandsMixin` — yolo/plan toggles + `/model`.
- `exec_commands_mixin.py::ExecCommandsMixin` — shell exec, `/btw`, custom cmds.

`commands_mixin.py::CommandsMixin` keeps only the dispatch core (`_command_table`,
`classify_input`, `schedule_command`, `dispatch_command`, `_run_command_chain`),
`_get_help_text`, the module-level matchers, and `logger`; it now inherits the
three command-group mixins. `BaseUI` inherits `CommandsMixin`,
`HistoryReplayMixin`, and `SystemInfoMixin`. Each mixin declares a
`TYPE_CHECKING` **host-class contract** block — the attributes/methods it
expects the composed `BaseUI` to provide — exactly as the pre-existing
`CommandsMixin` did, so static type checkers can verify cross-mixin accesses
while the block is a no-op at runtime.

**Consequences.**
- *Good.* `ui.py` 1019→858 and `commands_mixin.py` 907→417; each concern now
  lives in a file small enough to hold in one's head.
- *Good.* Zero public-API change (constructor signatures and method surface
  unchanged) and zero behavior change — verified by the full suite passing
  with only one test-patch-path update (`render_markdown` moved modules).
- *Good.* The host-contract pattern documents each mixin's dependencies
  explicitly.
- *Cost.* State is still **shared**, not encapsulated — mixins can reach any
  `BaseUI` attribute, so this is cohesion-by-file, not true decoupling.
- *Cost.* The host contract is duplicated (per-mixin subsets), and a moved
  symbol can break a test that patched it at the old module path.

**Alternatives rejected.**
1. **Deep collaborator extraction** (a `ConversationManager` / `SystemInfoProvider`
   owning the state, with `BaseUI` delegating) — the genuinely decoupled
   end-state, but it changes the public constructor surface and requires
   rewriting ~150 private-member test accesses; deferred to a future PR now
   that the concern boundaries are drawn.
2. **Leave the files monolithic** — rejected; the size actively impedes
   comprehension and safe change.
3. **Collapse the 34-param `__init__` into config objects** — rejected for now:
   the constructor is public API for subclassers, so changing it is a breaking
   change out of scope for a behavior-preserving refactor.

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/ui/base/ui.py` (`class BaseUI(CommandsMixin,
HistoryReplayMixin, SystemInfoMixin)`); `src/zrb/llm/ui/base/commands_mixin.py`
(`class CommandsMixin(ConversationCommandsMixin, ModelCommandsMixin,
ExecCommandsMixin)` + host-contract block); `replay_mixin.py`,
`system_info_mixin.py`, `conversation_commands_mixin.py`,
`model_commands_mixin.py`, `exec_commands_mixin.py` (each with a
`TYPE_CHECKING` host contract).

---

## ADR-0061 — Config-positioned custom prompt sections (registered provider or markdown file)

**Status:** Accepted

**Context.** ADR-0035 fixed the system prompt as ordered, MECE sections, but the
ordered set was closed: the only downstream extension point (`add_prompt` /
`prompts=`) always lands **last**, after the built-ins. Downstreams that need
an always-on section *positioned among* the built-ins (e.g. company context
before `tool_guidance`, or a live deploy-status block) had no declarative way to
do it. Some such sections are static text; others must reflect runtime state.

**Decision.** A name in `include_sections` (or `ZRB_LLM_INCLUDE_SECTIONS`) that
is not a built-in resolves as a custom section, composed at its configured
position. Resolution precedence is **built-in > registered provider > markdown
file**:
- `register_section(name, provider)` registers a `Callable[[AnyContext], str]`,
  composed by calling it with the active context at compose time — for
  runtime-dynamic content. A built-in name is never shadowed.
- Otherwise the name resolves via `get_prompt(name)` (project-override → env →
  base-prompt-dir → package), with `{PLACEHOLDER}` substitution. A missing file
  resolves to `""`.

Ordering is declarative in config; dynamic *behavior* is registered explicitly
in Python (typically `zrb_init.py`) — config never names a file to execute.

**Consequences.** Downstreams add positioned sections — static or dynamic —
without editing `PromptManager`. The registry mirrors ADR-0043's
`add_tool_guidance` pattern (config selects/orders, code supplies behavior), so
the extension surface stays consistent. Cost: an unknown/misspelled section name
silently resolves to `""` (no error) — a typo'd built-in is an invisible
dropped section.

**Alternatives rejected.**
1. **Exec a `.py` file named by the section** (resolve `company_context.py` and
   run it) — rejected: turns a declarative, widely-copied config string
   (`ZRB_LLM_INCLUDE_SECTIONS`) into a code-execution trigger, with the file
   sourced via `get_prompt`'s parent-directory walk. Couples "what to include"
   to "what code runs." The `SKILL.md`/`.py` precedent (ADR-0044) is
   defensible only because skills resolve from a project-controlled dir with a
   fixed entrypoint; not worth that machinery here when a registry suffices.
2. **Markdown-only custom sections** — rejected: cannot express runtime state
   (current sprint, live schema), the motivating case.
3. **Keep `add_prompt` (last-position only)** — rejected: position is the whole
   point; "always last" cannot sit before `tool_guidance`.

**Evidence.** **[DOCUMENTED]** `AGENTS.md` ("LLM Prompt System");
`src/zrb/llm/prompt/manager.py` (`register_section`, `_section_providers`, the
provider-vs-`get_prompt` branch in `_get_composed_middlewares`);
`test/llm/prompt/test_manager.py` (registered-section + custom-file-backed
tests). Refines ADR-0035; mirrors ADR-0043; contrasts ADR-0044.

## ADR-0062 — Intrinsic always-auto-approve for interaction tools (AskUserQuestion)

**Status:** Accepted

**Context.** `AskUserQuestion` *is* the user interaction: the model proposes a
multiple-choice question and the tool renders it via `ui.ask_user`, blocking
until the user answers. Yet, like every tool, it was a *deferred* tool subject
to the approval cascade (ADR-0055). Approving it is meaningless — the user is
asked "Allow tool execution?" *before* the question they would approve has
rendered. The `🎰 Executing tool 'AskUserQuestion'? (Y/n/e)` banner shows only
the raw `questions:` YAML; the formatted question appears only *after* approval.

It was kept tolerable in the builtin CLI by a single `auto_approve(
"AskUserQuestion")` entry in `builtin/llm/chat.py`'s tool-policy list. But that
list is per-runner: delegated sub-agents, the web/API runner, and any bare
`LLMTask` built without those policies still gated the question behind a
redundant approval prompt — or, worse, left the question un-surfaced after the
deferred round-trip. The auto-approval did not travel with the tool.

**Decision.** Make auto-approval *intrinsic to the tool*. A dependency-free leaf
registry (`src/zrb/llm/tool_call/always_approve.py`) exposes
`register_always_auto_approve(*names)` / `is_always_auto_approve(name)`. The
tool registers its own LLM-visible name at definition time
(`zrb.llm.tool.ask` calls `register_always_auto_approve("AskUserQuestion")`).
The approval cascade consults this set as **Priority 0** in `_resolve_approval`
(`agent/run/deferred_calls.py`), before the tool-policy check — and since
`_resolve_approval` is the single choke point for *every* path (main agent,
sub-agents, web), the guarantee holds everywhere. The now-redundant
`auto_approve("AskUserQuestion")` is removed from `chat.py` (single source of
truth). The non-interactive guard inside the tool still short-circuits with a
`[SYSTEM SUGGESTION]` so it never blocks on stdin when there is no user.

**Consequences.** AskUserQuestion never renders an approval prompt; the question
surfaces directly, in any runner. Auto-approval is discoverable next to the tool
and immune to a per-runner policy list omitting it. Cost: a tool that
self-registers bypasses *all* approval layers including an explicit `deny`
permission policy — acceptable because an interaction tool has no external side
effect and self-disables when non-interactive. The registry is global process
state (a module-level set), so registration is idempotent and order-independent.

**Alternatives rejected.**
1. **Keep relying on `chat.py`'s `auto_approve("AskUserQuestion")`** — rejected:
   it is per-runner and silently absent for sub-agents / web / bare `LLMTask`,
   which is exactly the reported bug.
2. **Auto-approve the whole `META` capability** (AskUserQuestion is tagged
   `META`) — rejected: too broad; `ExitPlanMode` is also harness-control but
   must stay `ASK` (PLAN_MODE_POLICY). Per-tool opt-in is precise.
3. **Render the formatted question inside the approval banner** — rejected:
   still asks the user to approve a question they then answer anyway (two
   interactions for one), and does not fix the missing-question case in
   non-CLI runners.

**Evidence.** **[DOCUMENTED]** `src/zrb/llm/tool_call/always_approve.py`;
`src/zrb/llm/tool/ask.py` (self-registration); `src/zrb/llm/agent/run/deferred_calls.py`
(`_resolve_approval` Priority 0); `src/zrb/builtin/llm/chat.py` (entry removed,
comment added); `test/llm/tool_call/test_always_approve.py`,
`test/llm/tool/test_ask.py`, `test/llm/agent/run/test_deferred_calls.py`
(`test_process_deferred_requests_always_auto_approve_bypasses_handler`).
Refines ADR-0055.
